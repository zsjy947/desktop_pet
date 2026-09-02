# -*- coding: utf-8 -*-
"""主窗口：无边框置顶透明窗 + 多显示器漫游 + 鼠标交互 + 主循环。

支持多角色（橘猫 / 参考图转化的 Q 版少女们），右键菜单弹出在宠物
上方（菜单底边贴住宠物头顶，绝不压住宠物），同时宠物保持最顶层、
不被任务栏遮挡。
"""
import json
import math
import os
import random
import sys
import time
import tkinter as tk

from . import config as C
from . import girl_sprites
from . import photo_sprites
from . import screens
from . import sprites
from .behavior import Behavior
from .characters import CHARACTERS, get as get_character

# Win32 SetWindowPos 参数：HWND_TOPMOST + 不改位置/大小/不抢焦点
_HWND_TOPMOST = -1
_SWP_NOSIZE = 0x0001
_SWP_NOMOVE = 0x0002
_SWP_NOACTIVATE = 0x0010

_PREF_FILE = os.path.join(os.path.expanduser('~'), '.desktop_pet.json')

# 右键菜单高度估算（实测 Windows 9pt 菜单项约 22px，含 emoji 留了余量）
_MENU_ITEM_H = 26
_MENU_SEP_H = 8
_MENU_PAD = 10


def _win32_user32():
    """返回配置好参数类型的 user32；非 Windows 或失败时返回 None。"""
    if sys.platform != 'win32':
        return None
    try:
        import ctypes
        import ctypes.wintypes as wt
        user32 = ctypes.windll.user32
        user32.GetParent.argtypes = [wt.HWND]
        user32.GetParent.restype = wt.HWND
        user32.SetWindowPos.argtypes = [wt.HWND, wt.HWND,
                                        ctypes.c_int, ctypes.c_int,
                                        ctypes.c_int, ctypes.c_int, wt.UINT]
        user32.SetWindowPos.restype = wt.BOOL
        return user32
    except Exception:
        return None


def load_pref():
    """读取上次选择的角色 id；没有或损坏时返回 None。"""
    try:
        with open(_PREF_FILE, encoding='utf-8') as f:
            return json.load(f).get('char')
    except Exception:
        return None


def save_pref(char_id):
    try:
        with open(_PREF_FILE, 'w', encoding='utf-8') as f:
            json.dump({'char': char_id}, f)
    except Exception:
        pass


def menu_origin(pet_x, pet_y, size, monitor, n_items, n_seps):
    """右键菜单弹出位置：菜单底边贴在宠物头顶上方，不压住宠物。

    monitor 为宠物当前所在显示器，用于把菜单夹回屏幕内。
    返回菜单左上角应出现的位置 (x, y)。
    """
    est = n_items * _MENU_ITEM_H + n_seps * _MENU_SEP_H + _MENU_PAD
    x = pet_x + size / 2 - 70
    x = min(max(x, monitor.x + 2), monitor.x + monitor.w - 150)
    y = pet_y + 14 - est          # 14 ≈ 宠物头顶在窗口内的起始高度
    y = max(y, monitor.y + 2)     # 屏幕上方放不下时至少贴住顶边
    return int(x), int(y)


class PetApp:
    def __init__(self):
        self.root = tk.Tk()

        # 当前角色：从用户目录的偏好文件恢复；图片精灵角色窗口更大
        self.char_id = load_pref() or 'cat'
        self.char = get_character(self.char_id)
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

        self._init_position()
        self.root.geometry(f'{size}x{size}+{int(self.x)}+{int(self.y)}')
        self.root.overrideredirect(True)                    # 无边框
        self.root.attributes('-topmost', True)              # 置顶（基础手段）
        self.root.configure(bg=C.KEY_COLOR)
        self.root.attributes('-transparentcolor', C.KEY_COLOR)  # 键色抠透明

        # 任务栏本身也是 topmost 窗口，被点击后会盖住宠物，
        # 因此记录原生句柄，主循环里周期性用 SetWindowPos 压回最顶层。
        self._user32 = _win32_user32()
        self._hwnd = None
        if self._user32 is not None:
            try:
                self.root.update_idletasks()
                self._hwnd = (self._user32.GetParent(self.root.winfo_id())
                              or self.root.winfo_id())
            except Exception:
                self._hwnd = None

        self.cv = tk.Canvas(self.root, width=size, height=size,
                            bg=C.KEY_COLOR, highlightthickness=0, bd=0,
                            cursor='hand2')
        self.cv.pack()

        self.behavior = Behavior()
        self.particles = []          # 爱心 / Zzz 粒子
        self.vy = 0.0                # 下落速度
        self.bubble_text = ''
        self.talk_until = 0.0
        self.next_talk = time.monotonic() + random.uniform(
            C.IDLE_TALK_MIN, C.IDLE_TALK_MAX)
        self._menu_open = False      # 右键菜单是否正在显示

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
    def _size_for(self, char):
        """角色的窗口边长：图片精灵角色用构建时的更大窗口。"""
        if (char.get('kind') == 'girl' and char.get('photo')
                and photo_sprites.has_assets(char['photo'])):
            return photo_sprites.window_size(char['photo'])
        return C.WINDOW_SIZE

    def _use_photo(self, char):
        return (char.get('kind') == 'girl' and bool(char.get('photo'))
                and photo_sprites.has_assets(char['photo']))

    def _init_position(self):
        """出生在主屏右下角（任务栏上方）。"""
        p = screens.primary(self.monitors)
        self.x = min(p.x + p.w - self.size - 40, self.max_x)
        self.y = p.y + p.h - self.size

    def ground_y_at(self, x, y):
        """脚底所在位置 (x, y) 处的地面高度（所属显示器的底边）。"""
        cx = x + self.size / 2
        m = screens.at(self.monitors, cx, y + self.size / 2)
        if m is None:
            m = screens.at_x(self.monitors, cx)
        return m.y + m.h - self.size

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

    def _ensure_topmost(self):
        """周期性把窗口顶回最顶层，保证不被任务栏等 topmost 窗口挡住。"""
        if self._hwnd is None:
            return
        try:
            self._user32.SetWindowPos(self._hwnd, _HWND_TOPMOST, 0, 0, 0, 0,
                                      _SWP_NOSIZE | _SWP_NOMOVE | _SWP_NOACTIVATE)
        except Exception:
            pass

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
        on_ground = self.y >= self.ground_y
        self.behavior.release_drag(on_ground)
        if not on_ground:
            self.vy = 0.0

    def _on_double_click(self, event):
        self._pet()

    def _on_menu(self, event):
        """右键菜单：弹在宠物上方（底边贴住头顶），不遮挡宠物。"""
        if self._menu_open:
            return
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label='🍪 喂食', command=self._feed)
        menu.add_command(label='🖐 摸摸头', command=self._pet)
        sleep_label = '☀ 叫醒' if self.behavior.state == 'sleep' else '😴 让它打盹'
        menu.add_command(label=sleep_label, command=self._toggle_sleep)
        menu.add_command(label='💬 说句话', command=self._chat)
        menu.add_separator()
        menu.add_radiobutton(label='🐱 橘猫', variable=self._char_var,
                             value='cat', command=self._switch_character)
        for preset in CHARACTERS.values():
            if preset['kind'] != 'girl':
                continue
            menu.add_radiobutton(label=f'🧚 {preset["name"]}',
                                 variable=self._char_var, value=preset['id'],
                                 command=self._switch_character)
        menu.add_separator()
        menu.add_command(label='🚪 退出', command=self.root.destroy)

        n_items = menu.index('end') + 1
        n_seps = sum(1 for i in range(n_items)
                     if menu.type(i) == 'separator')
        m = screens.at(self.monitors, self.x + self.size / 2,
                       self.y + self.size / 2) or self.virtual
        mx, my = menu_origin(self.x, self.y, self.size, m, n_items, n_seps)

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
        if new_id not in CHARACTERS:
            return
        self.char_id = new_id
        self.char = CHARACTERS[new_id]
        save_pref(new_id)
        self.root.title(f'桌面宠物 · {self.char["name"]}')

        # 图片精灵角色窗口更大：窗口底边（脚底）保持不动
        new_size = self._size_for(self.char)
        if new_size != self.size:
            self.y = self.y + self.size - new_size
            self.size = new_size
            self.max_x = self.virtual.x + self.virtual.w - self.size
            self.x = min(max(self.x, self.min_x), self.max_x)
            self._clamp_to_virtual()
            self.cv.config(width=self.size, height=self.size)
        self.root.geometry(f'{self.size}x{self.size}+{int(self.x)}+{int(self.y)}')
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

    def _toggle_sleep(self):
        if self.behavior.state == 'sleep':
            self.behavior.wake()
            self._say(random.choice(self._p('wake')))
        else:
            self.behavior.sleep()
            self._say(random.choice(self._p('sleep')))

    def _chat(self):
        self._say(random.choice(self._p('talk')))

    # ---------------- 气泡与粒子 ----------------
    def _say(self, text):
        self.bubble_text = text
        self.talk_until = time.monotonic() + C.SAY_DURATION

    def _spawn_hearts(self, n):
        k = self.size / 160
        for _ in range(n):
            self.particles.append({
                'kind': 'heart',
                'x': self.size / 2 + random.uniform(-30 * k, 30 * k),
                'y': 70 * k + random.uniform(-15 * k, 15 * k),
                'vx': random.uniform(-8, 8),
                'vy': random.uniform(-55, -35),
                'age': 0.0,
                'life': random.uniform(1.2, 1.8),
                'size': random.randint(10, 16),
            })

    def _spawn_zzz(self):
        k = self.size / 160
        self.particles.append({
            'kind': 'zzz',
            'x': 108 * k + random.uniform(-6 * k, 6 * k),
            'y': 60 * k,
            'vx': random.uniform(2, 8),
            'vy': -22.0,
            'age': 0.0,
            'life': 2.4,
            'size': 10,
        })

    # ---------------- 主循环 ----------------
    def _tick(self):
        now = time.monotonic()
        t = now - self._t0
        b = self.behavior

        if not self._menu_open:
            # 菜单显示期间保持原样，不要每帧动窗口（会干扰弹出菜单）
            self._ensure_topmost()

        if not self._menu_open:
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
                elif gy > self.y + 1:    # 前方地面更低（走下台阶）：顺势掉下去
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

            # 状态机随机切换（happy 到期回落等也在其中处理）
            b.update()

        # 睡觉时冒 Zzz
        if b.state == 'sleep' and random.random() < 0.05:
            self._spawn_zzz()

        # 随机碎碎念
        if b.state in ('idle', 'walk') and now >= self.next_talk:
            self._say(random.choice(self._p('talk')))
            self.next_talk = now + random.uniform(C.IDLE_TALK_MIN, C.IDLE_TALK_MAX)
        if self.talk_until <= now:
            self.bubble_text = ''

        # 粒子推进
        dt = 1.0 / C.FPS
        for p in self.particles:
            p['age'] += dt
            p['x'] += (p['vx'] + 12 * math.sin(t * 2 + p['y'])) * dt
            p['y'] += p['vy'] * dt
        self.particles = [p for p in self.particles if p['age'] < p['life']]

        # 移动窗口并重绘（菜单显示期间窗口原地不动）
        if not self._menu_open:
            self.root.geometry(f'+{int(self.x)}+{int(self.y)}')
        if self.char['kind'] == 'cat':
            sprites.draw_frame(self.cv, state=b.state, t=t, facing=b.facing,
                               bubble_text=self.bubble_text,
                               particles=self.particles)
        elif self._use_photo(self.char):
            photo_sprites.draw_frame(self.cv, char=self.char, state=b.state,
                                     t=t, facing=b.facing,
                                     bubble_text=self.bubble_text,
                                     particles=self.particles)
        else:
            girl_sprites.draw_frame(self.cv, char=self.char, state=b.state,
                                    t=t, facing=b.facing,
                                    bubble_text=self.bubble_text,
                                    particles=self.particles)

        self._schedule_tick()
