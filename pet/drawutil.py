# -*- coding: utf-8 -*-
"""绘制共享工具：带镜像的图元助手、头顶气泡、粒子。

猫（sprites.py）和 Q 版少女（girl_sprites.py）共用这里的东西，
保证两个角色有同样的交互观感（气泡、爱心、Zzz）。
"""
import math

import tkinter as tk
from tkinter import font as tkfont

from . import config as C


def make_mirror(cv, facing, fx=None):
    """返回一组带水平镜像的绘图闭包。

    传入“角色朝右”的坐标即可，facing=-1 时自动绕 fx 翻转。
    """
    if fx is None:
        fx = C.WINDOW_SIZE / 2

    def mx(x):
        return fx + (x - fx) * facing

    def bx(x1, x2):
        a, b = mx(x1), mx(x2)
        return (min(a, b), max(a, b))

    def oval(x1, y1, x2, y2, **kw):
        a, b = bx(x1, x2)
        cv.create_oval(a, y1, b, y2, **kw)

    def line(pts, **kw):
        cv.create_line([(mx(x), y) for x, y in pts], **kw)

    def poly(pts, **kw):
        cv.create_polygon([(mx(x), y) for x, y in pts], **kw)

    def both(fn):
        """对左右对称的部件各画一次：fn(xmap, side)。

        xmap 把“朝右”坐标映射到当前侧，side=1 左侧 / -1 右侧
        （需要左右反向摆动的部件用 side 取反偏移量）。
        """
        fn(lambda v: v, 1)
        fn(lambda v: C.WINDOW_SIZE - v, -1)

    return mx, bx, oval, line, poly, both


def _font_for(cv):
    """按画布缓存气泡字体，避免每帧新建 tkfont 对象。"""
    cache = getattr(cv, '_drawutil_fonts', None)
    if cache is None:
        cache = {}
        cv._drawutil_fonts = cache
    f = cache.get(C.FONT)
    if f is None:
        f = tkfont.Font(root=cv, font=C.FONT)
        cache[C.FONT] = f
    return f


def wrap_text(cv, text, max_width):
    """按像素宽度贪心折行。"""
    f = _font_for(cv)
    lines, cur = [], ''
    for ch in text:
        if f.measure(cur + ch) > max_width and cur:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


def draw_bubble(cv, text, size=None):
    """头顶圆角气泡，按文字自动换行并调整高度。size 为窗口边长
    （图片精灵窗口更大，气泡按比例放大）。"""
    k = (size or C.WINDOW_SIZE) / C.WINDOW_SIZE
    max_w = 118 * k
    lines = wrap_text(cv, text, max_w)[:3]  # 最多三行，台词应尽量短
    f = _font_for(cv)
    lh = f.metrics('linespace')
    w = max(f.measure(s) for s in lines) + 24 * k
    h = len(lines) * lh + 14 * k
    x1 = min(16 * k, C.WINDOW_SIZE * k / 2 - w / 2)
    x2 = x1 + w
    y1 = 2 * k
    y2 = y1 + h
    r = 8 * k
    pts = [(x1 + r, y1), (x2 - r, y1), (x2, y1 + r), (x2, y2 - r),
           (x2 - r, y2), (x1 + r, y2), (x1, y2 - r), (x1, y1 + r)]
    cx = (x1 + x2) / 2
    cv.create_polygon(pts, smooth=True, fill=C.BUBBLE_BG,
                      outline=C.BUBBLE_EDGE, width=2)
    cv.create_polygon([(cx - 8 * k, y2 - k), (cx + 8 * k, y2 - k),
                       (cx, y2 + 9 * k)],
                      fill=C.BUBBLE_BG, outline='')
    cv.create_line([(cx - 7 * k, y2), (cx, y2 + 8 * k), (cx + 7 * k, y2)],
                   fill=C.BUBBLE_BG, width=2)
    cv.create_text(cx, y1 + h / 2, text='\n'.join(lines), font=C.FONT,
                   fill=C.BUBBLE_FG, width=max_w, justify='center')


def draw_particles(cv, particles):
    """爱心 / Zzz 粒子。"""
    for p in particles:
        ratio = 1.0 - p['age'] / p['life']
        color = C.HEART if ratio > 0.45 else C.HEART_FADED
        if p['kind'] == 'heart':
            cv.create_text(p['x'], p['y'], text='♥',
                           font=('Segoe UI', int(p['size']), 'bold'), fill=color)
        else:
            cv.create_text(p['x'], p['y'], text='Z',
                           font=('Comic Sans MS', int(p['size']), 'bold'),
                           fill='#9FB4C7')


def sway(t, period=2.6, amp=6.0):
    """通用摇摆辅助。"""
    return math.sin(t * period) * amp
