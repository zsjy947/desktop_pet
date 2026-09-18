# -*- coding: utf-8 -*-
"""应用组合根：无边框置顶透明窗 + 主循环 + 鼠标交互 + 角色切换。

职责边界（重构后）：
    windowing   Win32 细节（DPI/置顶/单实例锁）
    prefs       用户偏好与跨实例退出标志
    registry    角色表合并（内置 + 自定义 + 图集）
    renderers   按角色类型分发绘制 + 状态归一化
    menu        右键菜单组装与定位
    fx          粒子生成/推进
    startup     开机自启
本模块只保留窗口生命周期、交互事件与每帧协调。
"""
import math
import os
import random
import time
import tkinter as tk
from tkinter import font as tkfont

from . import config as C
from . import drawutil
from . import fx
from . import menu as menu_mod
from . import prefs
from . import registry as registry_mod
from . import renderers
from . import screens
from . import startup
from . import windowing
from .behavior import Behavior

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class PetApp:
    def __init__(self, desired_char=None):
        self.root = tk.Tk()

        # 当前角色：偏好文件恢复，可被 --char 覆盖；图集角色窗口更大
        self.registry = registry_mod.full_registry()
        self.char_id = desired_char or prefs.load_pref() or 'cat'
        if self.char_id not in self.registry:
            self.char_id = 'cat'
        self.char = self.registry[self.char_id]
        self._char_var = tk.StringVar(value=self.char_id)
        self.root.title(f'桌面宠物 · {self.char["name"]}')
        self.size = self._size_for(self.char)
        size = self.size

        # 多显示器：虚拟桌面边界 + 每块屏各自的“地面”
        self.monitors = screens.get_monitors(
            (self.root.winfo_screenwidth(), self.root.winfo_screenheight()))
        self.virtual = screens.union(self.monitors)
        self.min_x = self.virtual.x
        self.max_x = self.virtual.x + self.virtual.w - size

        # 窗口在宠物区上方加高“对话区”：气泡画在那里，不遮挡人物
        self._bubble_extra = self._bubble_area_height()
        self._init_position()
        self.root.geometry(
            f'{size}x{size + self._bubble_extra}+{int(self.x)}+{int(self.y)}')
        self.root.overrideredirect(True)                    # 无边框
        self.root.attributes('-topmost', True)              # 置顶（基础手段）
        self.root.configure(bg=C.KEY_COLOR)
        self.root.attributes('-transparentcolor', C.KEY_COLOR)  # 键色抠透明

        # 任务栏本身也是 topmost，被点击后会盖住宠物：记录句柄，
        # 主循环里周期性压回最顶层
        self._user32 = windowing.get_user32()
        self._hwnd = windowing.hwnd_of(self.root, self._user32)

        self.cv = tk.Canvas(self.root, width=size, height=size,
                            bg=C.KEY_COLOR, highlightthickness=0, bd=0,
                            cursor='hand2')
        self.cv.place(x=0, y=self._bubble_extra)   # 宠物区贴在窗口下部

        # 对话区画布：只画气泡，永远不覆盖宠物
        self.cv_bubble = tk.Canvas(self.root, width=size,
                                   height=self._bubble_extra,
                                   bg=C.KEY_COLOR, highlightthickness=0,
                                   bd=0)
        self.cv_bubble.place(x=0, y=0)

        self.behavior = Behavior(tricks=self._tricks())
        self.particles = []          # 爱心 / Zzz / 特效粒子
        self.vy = 0.0                # 下落速度
        self.bubble_text = ''
        self.talk_until = 0.0
        self.next_talk = time.monotonic() + random.uniform(
            C.IDLE_TALK_MIN, C.IDLE_TALK_MAX)
        self._menu_open = False      # 右键菜单是否正在显示
        self._prev_bstate = None     # 上一帧行为状态（trick 进入检测用）
        self._ticks = 0              # 主循环计数（低频任务用）
        self._autostart_var = tk.BooleanVar(
            value=startup.is_enabled())

        # 拖拽偏移（按下点相对窗口左上角）
        self._drag_off = (0, 0)

        self.cv.bind('<ButtonPress-1>', self._on_press)
        self.cv.bind('<B1-Motion>', self._on_drag)
        self.cv.bind('<ButtonRelease-1>', self._on_release)
        self.cv.bind('<Double-Button-1>', self._on_double_click)
        self.cv.bind('<ButtonPress-3>', self._on_menu)

        self._t0 = time.monotonic()
        self._after_id = None
        self._schedule_tick()

    # ---------------- 位置与屏幕 ----------------
    def _bubble_area_height(self, size=None):
        """窗口顶部对话区高度：两行台词的气泡 + 尾巴，贴住头顶。"""
        k = (size or self.size) / 160
        ls = tkfont.Font(root=self.root, font=C.FONT).metrics('linespace')
        return int(2 * ls + 12 * k + 8 + 10 * k)

    def _size_for(self, char):
        """角色的窗口边长：图集/照片精灵用构建时的更大窗口。"""
        if char.get('kind') == 'hatch' and char.get('photo'):
            from . import hatch_sprites
            return hatch_sprites.window_size(char['photo'])
        if (char.get('kind') == 'girl' and char.get('photo')):
            from . import photo_sprites
            if photo_sprites.has_assets(char['photo']):
                return photo_sprites.window_size(char['photo'])
        return C.WINDOW_SIZE

    def _init_position(self):
        """出生在主屏右下角（窗口底边=脚底，落在工作区底边=任务栏上沿）。"""
        p = screens.primary(self.monitors)
        self.x = min(p.x + p.w - self.size - 40, self.max_x)
        self.y = p.wy + p.wh - self.size - self._bubble_extra

    def ground_y_at(self, x, y):
        """脚底所在位置 (x, y) 处的地面（窗口顶边应对齐到的 y）。

        地面取所属显示器的工作区（扣掉任务栏等 appbar）底边，且对齐的
        是窗口底边：宠物脚底正好站在任务栏上沿。任务栏高度、DPI 缩放、
        对话区加高有多少都自适应，不会落到屏幕外。
        """
        cx = x + self.size / 2
        m = screens.at(self.monitors, cx, y + self.size / 2)
        if m is None:
            m = screens.at_x(self.monitors, cx)
        return m.wy + m.wh - (self.size + self._bubble_extra)

    @property
    def ground_y(self):
        return self.ground_y_at(self.x, self.y)

    def _clamp_to_virtual(self):
        """拖拽时把窗口限制在虚拟桌面范围内。"""
        self.x = min(max(self.x, self.min_x), self.max_x)
        self.y = min(max(self.y, self.virtual.y),
                     self.virtual.y + self.virtual.h - self.size)

    # ---------------- 生命周期 ----------------
    def run(self):
        self.root.mainloop()

    def _schedule_tick(self):
        self._after_id = self.root.after(int(1000 / C.FPS), self._tick)

    # ---------------- 角色表与能力查询 ----------------
    def _registry(self):
        return registry_mod.full_registry()

    def _tricks(self):
        """当前角色的专属随机动作（宝可梦）：行号 + 播放时长 +
        特效粒子 + 叫声。普通角色返回空列表。"""
        if not (self.char.get('kind') == 'hatch'
                and self.char.get('photo')):
            return []
        out = []
        for t in self.char.get('tricks') or []:
            from . import hatch_sprites
            out.append({**t,
                        'duration': hatch_sprites.row_duration(t['row']) * 2})
        return out

    def _is_pokemon(self):
        """宝可梦：只有叫声（无对话/随机碎碎念），菜单不带聊聊天。"""
        return self.char.get('species') == 'pokemon'

    def _is_cat(self):
        """猫科（橘猫 / 芒果等）用喂食摸头，其余用打招呼/送礼物。"""
        c = self.char
        return c.get('kind') == 'cat' or c.get('species') == 'cat'

    # ---------------- 台词 ----------------
    def _p(self, key):
        """当前角色的某类台词列表。"""
        return self.char['phrases'][key]

    # ---------------- 鼠标交互 ----------------
    def _on_press(self, event):
        if self.behavior.state == 'sleep':
            self.behavior.wake()
            self._say(random.choice(self._p('wake')))
        self.behavior.start_drag()
        self.vy = 0.0
        self._drag_off = (event.x_root - self.x, event.y_root - self.y)

    def _on_drag(self, event):
        if self.behavior.state != 'drag':
            return
        self.x = event.x_root - self._drag_off[0]
        self.y = event.y_root - self._drag_off[1]
        self._clamp_to_virtual()

    def _on_release(self, event):
        if self.behavior.state != 'drag':
            return
        if self.y >= self.ground_y:
            # 落到地面或更低（比如拖进了任务栏区域）：贴回地面站好
            self.y = self.ground_y
            self.behavior.release_drag(True)
        else:
            self.behavior.release_drag(False)
            self.vy = 0.0

    def _on_double_click(self, event):
        if self._is_cat():
            self._pet()
        else:
            self._greet()

    def _on_menu(self, event):
        """右键菜单：弹在宠物上方（底边贴住头顶），不遮挡宠物。"""
        if self._menu_open:
            return
        self.registry = registry_mod.full_registry()
        menu = menu_mod.build(self)

        n_items = menu.index('end') + 1
        n_seps = sum(1 for i in range(n_items)
                     if menu.type(i) == 'separator')
        m = screens.at(self.monitors, self.x + self.size / 2,
                       self.y + self.size / 2) or self.virtual
        mx, my = menu_mod.menu_origin(self.x, self.y, self.size, m,
                                      n_items, n_seps, self._bubble_extra)

        # 菜单显示期间原地站好，菜单就会一直悬在宠物头顶
        self.behavior.pause()
        self._menu_open = True
        try:
            menu.tk_popup(mx, my)
        finally:
            menu.grab_release()
        self.root.after(150, lambda: self._watch_menu(menu))

    def _watch_menu(self, menu):
        """菜单关闭后恢复动画。"""
        if not self._menu_open:
            return
        if menu.winfo_ismapped():
            self.root.after(120, lambda: self._watch_menu(menu))
        else:
            self._menu_open = False
            try:
                menu.destroy()
            except Exception:
                pass

    def _switch_character(self):
        """切换角色：换外观 + 换台词包，并记住选择。"""
        new_id = self._char_var.get()
        if new_id not in self.registry:
            return
        self.char_id = new_id
        self.char = self.registry[new_id]
        prefs.save_pref(new_id)
        self.root.title(f'桌面宠物 · {self.char["name"]}')
        self.behavior.tricks = self._tricks()
        # 切走时结束旧角色的瞬态状态，防止行为层带着旧状态跑
        if self.behavior.state in ('trick', 'happy', 'excited'):
            self.behavior._idle()

        # 图集/照片精灵角色窗口更大：窗口底边（脚底）保持不动
        new_size = self._size_for(self.char)
        if new_size != self.size:
            self.y = self.y + self.size + self._bubble_extra - (
                new_size + self._bubble_area_height(new_size))
            self.size = new_size
            self._bubble_extra = self._bubble_area_height(self.size)
            self.max_x = self.virtual.x + self.virtual.w - self.size
            self.x = min(max(self.x, self.min_x), self.max_x)
            self._clamp_to_virtual()
            self.cv.config(width=self.size, height=self.size)
            self.cv.place(x=0, y=self._bubble_extra)
            self.cv_bubble.config(width=self.size, height=self._bubble_extra)
        self.root.geometry(
            f'{self.size}x{self.size + self._bubble_extra}'
            f'+{int(self.x)}+{int(self.y)}')
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
        """打招呼：挥手 + 角色的出场台词。"""
        if self.behavior.state == 'sleep':
            self.behavior.wake()
        self.behavior.happy()
        self._say(random.choice(self._p('switch')))

    def _gift(self):
        """送礼物：开心到跳起来 + 爱心雨 + 收礼台词。"""
        if self.behavior.state == 'sleep':
            self.behavior.wake()
        self.behavior.excited()
        self._spawn_hearts(10)
        self._say(random.choice(self._p('feed')))

    def _feed_berry(self):
        """喂宝可梦树果：开心 + 树果/爱心特效 + 叫声。"""
        if self.behavior.state == 'sleep':
            self.behavior.wake()
        self.behavior.happy()
        self._spawn_fx('berry', 4)
        self._spawn_hearts(6)
        self._say(random.choice(self._p('feed')))

    def _perform_trick(self):
        """手动让宝可梦表演一个专属动作（菜单触发）。"""
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

    def _toggle_autostart(self):
        """开机自启开关（右键菜单）。失败时回滚勾选。"""
        try:
            if self._autostart_var.get():
                startup.enable(ROOT)
            else:
                startup.disable()
        except (OSError, RuntimeError):
            self._autostart_var.set(not self._autostart_var.get())

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
        t = now - self._t0
        b = self.behavior
        self._ticks += 1

        # 低频任务：响应另一实例的 --quit 请求（每 ~2s 查一次标志文件）
        if self._ticks % 90 == 0 and prefs.quit_pending():
            self.root.destroy()
            return

        if not self._menu_open:
            # 菜单显示期间保持原样，不要每帧动窗口（会干扰弹出菜单）
            windowing.ensure_topmost(self._user32, self._hwnd)

            # 走路位移 + 虚拟桌面边缘掉头 + 跨屏地面处理
            if b.moving:
                self.x += C.WALK_SPEED * b.facing
                if self.x <= self.min_x or self.x >= self.max_x:
                    self.x = min(max(self.x, self.min_x), self.max_x)
                    b.turn_around()
                gy = self.ground_y_at(self.x, self.y)
                if gy < self.y - 1:      # 前方地面更高：走不过去，掉头
                    b.turn_around()
                    self.x += C.WALK_SPEED * b.facing
                elif gy > self.y + 1:    # 前方地面更低：顺势掉下去
                    b.fall()
                    self.vy = 0.0

            # 悬空下落 + 落地反弹
            if b.state == 'fall':
                self.vy += C.GRAVITY
                self.y += self.vy
                gy = self.ground_y_at(self.x, self.y)
                if self.y >= gy:
                    self.y = gy
                    if self.vy > 3.0:
                        self.vy = -self.vy * C.BOUNCE
                        self._say(random.choice(self._p('drop')))
                    else:
                        b.land()
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

        # 粒子推进
        self.particles = fx.advance(self.particles, 1.0 / C.FPS, t)

        # 移动窗口并重绘（菜单显示期间窗口原地不动）
        if not self._menu_open:
            self.root.geometry(f'+{int(self.x)}+{int(self.y)}')
        # 气泡画在顶部对话区画布上，不遮挡宠物
        self.cv_bubble.delete('all')
        if self.bubble_text:
            drawutil.draw_bubble(self.cv_bubble, self.bubble_text,
                                 self.size, self._bubble_extra)
        renderers.draw(self.cv, char=self.char, state=b.state, t=t,
                       facing=b.facing, particles=self.particles,
                       trick_row=(trick['row'] if trick else None))

        self._schedule_tick()
