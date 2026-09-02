# -*- coding: utf-8 -*-
"""主窗口：无边框置顶透明窗 + 鼠标交互 + 主循环。"""
import math
import random
import time
import tkinter as tk

from . import config as C
from .behavior import Behavior
from .sprites import draw_frame


class PetApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title('桌面橘猫')
        size = C.WINDOW_SIZE
        self.size = size

        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        # “地面” = 窗口脚底贴着屏幕底边时窗口顶部的 y 坐标
        self.ground_y = screen_h - size
        self.min_x, self.max_x = 0, screen_w - size

        self.x = self.max_x - 40
        self.y = self.ground_y
        self.root.geometry(f'{size}x{size}+{self.x}+{self.y}')
        self.root.overrideredirect(True)                    # 无边框
        self.root.attributes('-topmost', True)              # 置顶
        self.root.configure(bg=C.KEY_COLOR)
        self.root.attributes('-transparentcolor', C.KEY_COLOR)  # 键色抠透明

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

    # ---------------- 生命周期 ----------------
    def run(self):
        self.root.mainloop()

    def _schedule_tick(self):
        self._after_id = self.root.after(int(1000 / C.FPS), self._tick)

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

        # 走路位移 + 边缘掉头
        if b.moving:
            self.x += C.WALK_SPEED * b.facing
            if self.x <= self.min_x or self.x >= self.max_x:
                self.x = min(max(self.x, self.min_x), self.max_x)
                b.turn_around()

        # 悬空下落 + 落地反弹
        if b.state == 'fall':
            self.vy += C.GRAVITY
            self.y += self.vy
            if self.y >= self.ground_y:
                self.y = self.ground_y
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

