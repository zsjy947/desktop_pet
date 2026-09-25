# -*- coding: utf-8 -*-
"""Qt 运行时组合根：逐像素透明置顶窗 + dt 主循环 + 鼠标交互 + 角色切换。

与 tk 版（app.py，键色窗口）的对应关系与差异：
    * 透明 = WA_TranslucentBackground（真逐像素 alpha），蒙版 setMask
      负责点击穿透（透明区点回桌面），erode/二值化约束全部退役；
    * 主循环 QTimer(1000/FPS)，位移/下落按实际 dt 步进（不随 tick 漂移）；
    * 多显示器地面用 QScreen.availableGeometry()（逻辑坐标与窗口一致，
      任务栏/DPI 自适应），screens.py 的 union/primary/at 复用；
    * 菜单 = QMenu，结构来自 menu.spec()（与 tk build 同一套分组）；
      QMenu.exec 的嵌套事件循环里 QTimer 照常触发，_menu_open 语义与
      tk 相同（菜单期间不移动窗口/不压置顶）；
    * 行为机 behavior.py、粒子 fx.py、偏好/单实例/自启 全复用。

支持的渲染后端：anim（v2 资产）/ hatch（图集）/ cat（Canvas 橘猫移植）。
"""
import math
import os
import random
import sys
import time

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QPainter, QRegion
from PySide6.QtWidgets import QApplication, QMenu, QWidget

from . import config as C
from . import fx
from . import hatch_sprites
from . import menu as menu_mod
from . import prefs
from . import qt_render
from . import registry as registry_mod
from . import screens
from . import startup
from . import windowing
from .anims import loop_seconds, meta as anim_meta
from .behavior import Behavior

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# tk 版常量按 30fps"每帧"定义；Qt 主循环按实际 dt 换算成每秒
_SPEED = C.WALK_SPEED * C.FPS          # 走路速度 px/s
_GRAVITY = C.GRAVITY * C.FPS * C.FPS   # 下落加速度 px/s^2
_BOUNCE_V = 3.0 * C.FPS                # 反弹阈值 px/s


class PetAppQt(QWidget):
    def __init__(self, desired_char=None, app=None):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                         | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.app = app

        # 当前角色：偏好文件恢复，可被 --char 覆盖；anims 优先于图集。
        # 偏好里的角色可能已不存在（如已移除的橘猫）：回落默认皮卡丘
        self.registry = registry_mod.full_registry(include_anims=True)
        self.char_id = desired_char or prefs.load_pref() or 'pikachu'
        if self.char_id not in self.registry:
            self.char_id = ('pikachu' if 'pikachu' in self.registry
                            else next(iter(self.registry), 'pikachu'))
        self.char = self.registry[self.char_id]
        self.setWindowTitle(f'桌面宠物 · {self.char["name"]}')

        self.renderer = qt_render.Renderer()
        self.renderer.set_char(self.char)
        self.size = self.renderer.window_size()

        # 多显示器：QScreen 逻辑坐标（与窗口坐标系一致）+ 工作区
        self.monitors = _qt_monitors()
        self.virtual = screens.union(self.monitors)
        self.min_x = self.virtual.x
        self.max_x = self.virtual.x + self.virtual.w - self.size

        # 窗口在宠物区上方加高"对话区"：气泡画在那里，不遮挡人物
        self._bubble_extra = self._bubble_area_height()
        self._init_position()
        self.resize(self.size, self.size + self._bubble_extra)
        self.move(int(self.x), int(self.y))

        self.behavior = Behavior(tricks=self._tricks())
        self.particles = []          # 爱心 / Zzz / 特效粒子
        self.vy = 0.0                # 下落速度 px/s
        self.bubble_text = ''
        self.talk_until = 0.0
        self.next_talk = time.monotonic() + random.uniform(
            C.IDLE_TALK_MIN, C.IDLE_TALK_MAX)
        self._menu_open = False
        self._prev_bstate = None
        self._ticks = 0
        self._t0 = time.monotonic()
        self._t = 0.0                # 动画时间（渲染用）
        self._last = self._t0
        self._drag_off = (0, 0)
        self._bubble_path = None
        self._last_mask = None
        self._last_pos = (int(self.x), int(self.y))

        self._user32 = windowing.get_user32()
        self._hwnd = None

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(int(1000 / C.FPS))

        self.show()
        self._hwnd = int(self.winId())
        windowing.ensure_topmost(self._user32, self._hwnd)

    # ---------------- 位置与屏幕 ----------------
    def _bubble_area_height(self, size=None):
        """窗口顶部对话区高度：两行台词的气泡 + 尾巴，贴住头顶。"""
        k = (size or self.size) / 160
        ls = qt_render.bubble_metrics().height()
        return int(2 * ls + 12 * k + 8 + 10 * k)

    def _size_for(self, char):
        self.renderer.set_char(char)
        return self.renderer.window_size()

    def _init_position(self):
        """出生在主屏右下角（窗口底边=脚底，落在工作区底边=任务栏上沿）。"""
        p = screens.primary(self.monitors)
        self.x = min(p.x + p.w - self.size - 40, self.max_x)
        self.y = p.wy + p.wh - self.size - self._bubble_extra

    def ground_y_at(self, x, y):
        """脚底所在位置 (x, y) 处的地面（窗口顶边应对齐到的 y）。"""
        cx = x + self.size / 2
        m = screens.at(self.monitors, cx, y + self.size / 2)
        if m is None:
            m = screens.at_x(self.monitors, cx)
        return m.wy + m.wh - (self.size + self._bubble_extra)

    @property
    def ground_y(self):
        return self.ground_y_at(self.x, self.y)

    def _clamp_to_virtual(self):
        self.x = min(max(self.x, self.min_x), self.max_x)
        self.y = min(max(self.y, self.virtual.y),
                     self.virtual.y + self.virtual.h - self.size)

    # ---------------- 角色能力查询 ----------------
    @property
    def kind(self):
        return self.char.get('kind')

    def _tricks(self):
        """专属随机动作（宝可梦）：anims 用 state + 动画时长，
        hatch 沿用图集行时长。普通角色返回空列表。"""
        out = []
        c = self.char
        if c.get('kind') == 'anim':
            for t in c.get('tricks') or []:
                loop = loop_seconds(anim_meta(c['photo']), t['state'])
                # 短循环播两轮，长循环播一轮
                out.append({**t, 'duration': loop if loop >= 2.0
                            else loop * 2.0})
        elif c.get('kind') == 'hatch':
            for t in c.get('tricks') or []:
                out.append({**t,
                            'duration': hatch_sprites.row_duration(t['row'])
                            * 2})
        return out

    def _is_pokemon(self):
        return self.char.get('species') == 'pokemon'

    def _p(self, key):
        return self.char['phrases'][key]

    # ---------------- 鼠标交互 ----------------
    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            if self.behavior.state == 'sleep':
                self.behavior.wake()
                self._say(random.choice(self._p('wake')))
            self.behavior.start_drag()
            self.vy = 0.0
            g = ev.globalPosition().toPoint()
            self._drag_off = (g.x() - self.x, g.y() - self.y)
        elif ev.button() == Qt.RightButton:
            self._open_menu()

    def mouseDoubleClickEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            self._greet()

    def mouseMoveEvent(self, ev):
        if self.behavior.state != 'drag':
            return
        g = ev.globalPosition().toPoint()
        self.x = g.x() - self._drag_off[0]
        self.y = g.y() - self._drag_off[1]
        self._clamp_to_virtual()
        self._apply_window_pos(force=True)      # 拖拽要跟手

    def mouseReleaseEvent(self, ev):
        if self.behavior.state != 'drag':
            return
        if self.y >= self.ground_y:
            # 落到地面或更低（比如拖进了任务栏区域）：贴回地面站好
            self.y = self.ground_y
            self.behavior.release_drag(True)
        else:
            self.behavior.release_drag(False)
            self.vy = 0.0

    # ---------------- 右键菜单 ----------------
    def _open_menu(self):
        if self._menu_open:
            return
        self.registry = registry_mod.full_registry(include_anims=True)
        menu = self._build_qmenu(menu_mod.spec(self))

        # 菜单显示期间原地站好，菜单就会一直悬在宠物头顶
        self.behavior.pause()
        self._menu_open = True
        try:
            sh = menu.sizeHint()
            m = screens.at(self.monitors, self.x + self.size / 2,
                           self.y + self.size / 2) or self.virtual
            x = int(self.x + self.size / 2 - sh.width() / 2)
            x = min(max(x, m.x + 2), m.x + m.w - sh.width() - 2)
            bottom = int(self.y + self._bubble_extra + self.size * 0.15)
            y = max(bottom - sh.height(), m.y + 2)
            menu.exec(QPoint(x, y))
        finally:
            self._menu_open = False
            menu.deleteLater()

    def _build_qmenu(self, items):
        """menu.spec() → QMenu。"""
        menu = QMenu(self)
        char_group = QActionGroup(menu)
        char_group.setExclusive(True)
        for it in items:
            t = it['type']
            if t == 'sep':
                menu.addSeparator()
            elif t == 'command':
                act = QAction(it['label'], menu)
                act.triggered.connect(it['cmd'])
                menu.addAction(act)
            elif t == 'check':
                act = QAction(it['label'], menu)
                act.setCheckable(True)
                act.setChecked(startup.is_enabled())
                act.toggled.connect(self._set_autostart)
                menu.addAction(act)
            elif t == 'cascade':
                sub = menu.addMenu(it['label'])
                subgroup = QActionGroup(sub)
                subgroup.setExclusive(True)
                for c in it['items']:
                    if c['type'] == 'sep':
                        sub.addSeparator()
                    elif c['type'] == 'radio':
                        act = QAction(c['label'], sub)
                        act.setCheckable(True)
                        act.setChecked(c['value'] == self.char_id)
                        subgroup.addAction(act)
                        act.triggered.connect(
                            lambda _=False, v=c['value']:
                            self._select_char(v))
                        sub.addAction(act)
        return menu

    def _select_char(self, char_id):
        self.char_id = char_id
        self._switch_character()

    def _set_autostart(self, enable):
        """开机自启开关。失败时回滚勾选。"""
        try:
            if enable:
                startup.enable(ROOT)
            else:
                startup.disable()
        except (OSError, RuntimeError):
            act = self.sender()
            if isinstance(act, QAction):
                act.setChecked(not enable)

    # ---------------- 角色切换 ----------------
    def _switch_character(self):
        new_id = self.char_id
        if new_id not in self.registry:
            return
        self.char = self.registry[new_id]
        prefs.save_pref(new_id)
        self.setWindowTitle(f'桌面宠物 · {self.char["name"]}')
        self.behavior.tricks = self._tricks()
        if self.behavior.state in ('trick', 'happy', 'excited'):
            self.behavior._idle()

        new_size = self._size_for(self.char)
        if new_size != self.size:
            # 窗口底边（脚底）保持不动
            self.y = self.y + self.size + self._bubble_extra - (
                new_size + self._bubble_area_height(new_size))
            self.size = new_size
            self._bubble_extra = self._bubble_area_height(self.size)
            self.max_x = self.virtual.x + self.virtual.w - self.size
            self.x = min(max(self.x, self.min_x), self.max_x)
            self._clamp_to_virtual()
            self.resize(self.size, self.size + self._bubble_extra)
        self.renderer.set_char(self.char)
        self._say(random.choice(self._p('switch')))

    # ---------------- 菜单动作 ----------------
    def _feed(self):
        if self.behavior.state == 'sleep':
            self.behavior.wake()
        self.behavior.happy()
        self._spawn_hearts(8)
        self._say(random.choice(self._p('feed')))

    def _pet(self):
        if self.behavior.state == 'sleep':
            self.behavior.wake()
        self.behavior.happy()
        self._spawn_hearts(5)
        self._say(random.choice(self._p('pet')))

    def _greet(self):
        if self.behavior.state == 'sleep':
            self.behavior.wake()
        self.behavior.happy()
        self._say(random.choice(self._p('switch')))

    def _gift(self):
        if self.behavior.state == 'sleep':
            self.behavior.wake()
        self.behavior.excited()
        self._spawn_hearts(10)
        self._say(random.choice(self._p('feed')))

    def _feed_berry(self):
        if self.behavior.state == 'sleep':
            self.behavior.wake()
        self.behavior.happy()
        self._spawn_fx('berry', 4)
        self._spawn_hearts(6)
        self._say(random.choice(self._p('feed')))

    def _perform_trick(self):
        self.behavior.perform_trick()

    def _toggle_sleep(self):
        if self.behavior.state == 'sleep':
            self.behavior.wake()
            self._say(random.choice(self._p('wake')))
        else:
            self.behavior.sleep()
            self._say(random.choice(self._p('sleep')))

    def _chat(self):
        self._say(random.choice(self._p('talk')))

    def _quit(self):
        self.close()
        QApplication.instance().quit()

    def _autostart_checked(self):
        return startup.is_enabled()

    # ---------------- 气泡与粒子 ----------------
    def _say(self, text):
        self.bubble_text = text
        self.talk_until = time.monotonic() + C.SAY_DURATION

    def _spawn_hearts(self, n):
        self.particles.extend(fx.hearts(n, self.size / 160))

    def _spawn_fx(self, kind, n):
        self.particles.extend(fx.burst(kind, n, self.size / 160))

    def _spawn_zzz(self):
        self.particles.extend(fx.zzz(self.size / 160))

    # ---------------- 主循环 ----------------
    def _tick(self):
        now = time.monotonic()
        dt = min(now - self._last, 0.1)
        self._last = now
        self._t = now - self._t0
        t = self._t
        b = self.behavior
        self._ticks += 1

        # 低频任务：响应另一实例的 --quit 请求（每 ~2s 查一次标志文件）
        if self._ticks % 90 == 0 and prefs.quit_pending():
            self._quit()
            return

        if not self._menu_open:
            # 菜单显示期间保持原样，不要每帧动窗口（会干扰弹出菜单）
            if self._ticks % 90 == 0:
                windowing.ensure_topmost(self._user32, self._hwnd)

            # 走路位移 + 虚拟桌面边缘掉头 + 跨屏地面处理
            if b.moving:
                self.x += _SPEED * dt * b.facing
                if self.x <= self.min_x or self.x >= self.max_x:
                    self.x = min(max(self.x, self.min_x), self.max_x)
                    b.turn_around()
                gy = self.ground_y_at(self.x, self.y)
                if gy < self.y - 1:      # 前方地面更高：走不过去，掉头
                    b.turn_around()
                    self.x += _SPEED * dt * b.facing
                elif gy > self.y + 1:    # 前方地面更低：顺势掉下去
                    b.fall()
                    self.vy = 0.0

            # 悬空下落 + 落地反弹
            if b.state == 'fall':
                self.vy += _GRAVITY * dt
                self.y += self.vy * dt
                gy = self.ground_y_at(self.x, self.y)
                if self.y >= gy:
                    self.y = gy
                    if self.vy > _BOUNCE_V:
                        self.vy = -self.vy * C.BOUNCE
                        self._say(random.choice(self._p('drop')))
                    else:
                        b.land()
                        self.renderer.pulse()       # 落地 squash 挤压
                        self.vy = 0.0

            # 状态机随机切换（happy/trick 到期回落等）
            b.update()

        # 睡觉时冒 Zzz
        if b.state == 'sleep' and random.random() < 0.05:
            self._spawn_zzz()

        # 进入专属动作（宝可梦）：叫声气泡 + 对应特效粒子
        trick = b.current_trick
        if b.state != self._prev_bstate and b.state == 'trick' and trick:
            self._say(trick['cry'])
            if trick.get('fx'):
                self._spawn_fx(trick['fx'], 6)
        self._prev_bstate = b.state

        # 随机碎碎念（宝可梦只有叫声：不碎碎念）
        if (b.state in ('idle', 'walk') and not self._is_pokemon()
                and now >= self.next_talk):
            self._say(random.choice(self._p('talk')))
            self.next_talk = now + random.uniform(C.IDLE_TALK_MIN,
                                                  C.IDLE_TALK_MAX)
        if self.talk_until <= now:
            self.bubble_text = ''

        # 粒子推进（真实 dt）
        self.particles = fx.advance(self.particles, dt, t)

        # 推进动画播放头并移动窗口（菜单显示期间窗口原地不动）
        trick_arg = None
        if trick:
            trick_arg = (trick.get('state') if self.kind == 'anim'
                         else trick.get('row'))
        self.renderer.advance(b.state, trick_arg, b.facing, dt * 1000.0)
        if not self._menu_open:
            self._apply_window_pos()

        self.update()               # 触发 paintEvent 重绘

    def _apply_window_pos(self, force=False):
        pos = (int(self.x), int(self.y))
        if force or pos != self._last_pos:
            self._last_pos = pos
            self.move(*pos)

    # ---------------- 绘制 ----------------
    def paintEvent(self, _ev):
        p = QPainter(self)
        self.renderer.paint(p, state=self.behavior.state, t=self._t,
                            facing=self.behavior.facing,
                            particles=self.particles,
                            bubble_extra=self._bubble_extra)
        self._bubble_path = None
        if self.bubble_text:
            self._bubble_path = qt_render.draw_bubble(
                p, self.bubble_text, self.size, self._bubble_extra)
        p.end()
        self._update_mask()

    def _update_mask(self):
        """蒙版 = 本体 alpha ∪ 气泡轮廓 ∪ 粒子方块：蒙版外点击穿透回桌面。"""
        off = self._bubble_extra
        body = self.renderer.body_region()
        if body is not None and not body.isEmpty():
            # 本体区域是宠物区坐标（y 0..window），平移到窗口坐标
            full = body.translated(0, off)
        else:
            full = QRegion(0, off, self.size, self.size)
        if self._bubble_path is not None:
            # PySide6 的 QRegion 不接受 QPainterPath（C++ 有、绑定缺），
            # 走填充多边形转 QPolygon
            full = full.united(
                QRegion(self._bubble_path.toFillPolygon().toPolygon()))
        for pr in self.particles:
            s = int(pr.get('size', 12))
            full = full.united(QRegion(
                int(pr['x']) - s, off + int(pr['y']) - s, 2 * s, 2 * s))
        if full == self._last_mask:
            return
        self._last_mask = full
        self.setMask(full)

    # ---------------- 生命周期 ----------------
    def run(self):
        QApplication.instance().exec()


def _qt_monitors():
    """QScreen → screens.Monitor（逻辑坐标 + 工作区），复用 screens.py
    的 union/primary/at 几何助手。"""
    out = []
    for scr in QApplication.instance().screens():
        g = scr.geometry()
        a = scr.availableGeometry()
        out.append(screens.Monitor(g.x(), g.y(), g.width(), g.height(),
                                   a.x(), a.y(), a.width(), a.height()))
    if not out:
        out.append(screens.Monitor(0, 0, 1920, 1080))
    return out


def main(desired_char=None):
    app = QApplication.instance() or QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    win = PetAppQt(desired_char, app=app)
    try:
        win.run()
    finally:
        win.setMask(QRegion())      # 退出前清掉蒙版，避免残留残影
    return 0
