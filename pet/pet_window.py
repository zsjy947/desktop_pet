# -*- coding: utf-8 -*-
"""主窗口：无边框置顶透明窗 + 多显示器漫游 + 鼠标交互 + 主循环。"""
import math
import random
import sys
import time
import tkinter as tk

from . import config as C
from . import screens
from .behavior import Behavior
from .sprites import draw_frame

# Win32 SetWindowPos 参数：HWND_TOPMOST + 不改位置/大小/不抢焦点
_HWND_TOPMOST = -1
_SWP_NOSIZE = 0x0001
_SWP_NOMOVE = 0x0002
_SWP_NOACTIVATE = 0x0010


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


class PetApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title('桌面橘猫')
        self.size = C.WINDOW_SIZE
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

    # ---------------- 鼠标交互 ----------------
    def _on_press(self, event):
        if self.behavior.state == 'sleep':
            self.behavior.wake()
            self._say(random.choice(C.WAKE_PHRASES))
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
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label='🍪 喂食', command=self._feed)
        menu.add_command(label='🖐 摸摸头', command=self._pet)
        sleep_label = '☀ 叫醒' if self.behavior.state == 'sleep' else '😴 让它打盹'
        menu.add_command(label=sleep_label, command=self._toggle_sleep)
        menu.add_command(label='💬 说句话', command=self._chat)
        menu.add_separator()
        menu.add_command(label='🚪 退出', command=self.root.destroy)
        menu.tk_popup(event.x_root, event.y_root)

    # ---------------- 菜单动作 ----------------
    def _feed(self):
        if self.behavior.state == 'sleep':
            self.behavior.wake()
        self.behavior.happy()
        self._spawn_hearts(8)
        self._say(random.choice(C.FEED_PHRASES))

    def _pet(self):
        if self.behavior.state == 'sleep':
            self.behavior.wake()
        self.behavior.happy()
        self._spawn_hearts(5)
        self._say(random.choice(C.PET_PHRASES))

    def _toggle_sleep(self):
        if self.behavior.state == 'sleep':
            self.behavior.wake()
            self._say(random.choice(C.WAKE_PHRASES))
        else:
            self.behavior.sleep()
            self._say(random.choice(C.SLEEP_PHRASES))

    def _chat(self):
        self._say(random.choice(C.PHRASES))

    # ---------------- 气泡与粒子 ----------------
    def _say(self, text):
        self.bubble_text = text
        self.talk_until = time.monotonic() + C.SAY_DURATION

    def _spawn_hearts(self, n):
        for _ in range(n):
            self.particles.append({
                'kind': 'heart',
                'x': self.size / 2 + random.uniform(-30, 30),
                'y': 70 + random.uniform(-15, 15),
                'vx': random.uniform(-8, 8),
                'vy': random.uniform(-55, -35),
                'age': 0.0,
                'life': random.uniform(1.2, 1.8),
                'size': random.randint(10, 16),
            })

    def _spawn_zzz(self):
        self.particles.append({
            'kind': 'zzz',
            'x': 108 + random.uniform(-6, 6),
            'y': 60,
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

        self._ensure_topmost()

        # 走路位移 + 虚拟桌面边缘掉头 + 跨屏地面处理
        if b.moving:
            self.x += C.WALK_SPEED * b.facing
            if self.x <= self.min_x or self.x >= self.max_x:
                self.x = min(max(self.x, self.min_x), self.max_x)
                b.turn_around()
            gy = self.ground_y_at(self.x, self.y)
            if gy < self.y - 1:      # 前方地面更高（如隔壁屏位置偏上）：走不过去，掉头
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
                    self._say(random.choice(C.DROP_PHRASES))
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
            self._say(random.choice(C.PHRASES))
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

        # 移动窗口并重绘
        self.root.geometry(f'+{int(self.x)}+{int(self.y)}')
        draw_frame(self.cv, state=b.state, t=t, facing=b.facing,
                   bubble_text=self.bubble_text, particles=self.particles)

        self._schedule_tick()
