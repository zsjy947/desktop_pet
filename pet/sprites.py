# -*- coding: utf-8 -*-
"""橘猫的逐帧绘制：不依赖任何图片素材，全部用 Canvas 图元程序化画出。

每帧整体重绘一次（delete('all') 后重画），160x160 画布、约 30 个图元，
30fps 下开销可忽略。
"""
import math

from . import config as C

# 状态 -> 眼睛样式的映射在 _draw_eyes 中处理


def draw_frame(cv, *, state, t, facing, bubble_text, particles):
    """绘制一帧。

    state: idle | walk | sleep | drag | fall | happy
    t:     动画时间（秒）
    facing: 1 朝右 / -1 朝左
    bubble_text: 气泡文字（空串则不画）
    particles: 粒子列表（爱心 / Zzz）
    """
    cv.delete('all')

    fx = C.WINDOW_SIZE / 2  # 水平镜像中心

    # ---- 带镜像的绘图小工具：传“朝右”的坐标，自动按 facing 翻转 ----
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

    # ---------- 姿态参数 ----------
    walk = t * 9.0 if state == 'walk' else 0.0
    breathing = math.sin(t * 2.2) * 1.4 if state in ('idle', 'sleep') else 0.0
    if state == 'walk':
        bob = abs(math.sin(walk)) * 2.5
    elif state == 'happy':
        bob = abs(math.sin(t * 7.0)) * 5.0
    elif state in ('idle', 'sleep'):
        bob = breathing * 0.6
    else:
        bob = 0.0
    hy = bob  # 头部组整体上下偏移

    # ---------- 尾巴（画在身体后面）----------
    if state == 'walk':
        wag = math.sin(walk) * 3.0
    else:
        wag = math.sin(t * 2.6) * 6.0
    tail_pts = [(106, 122), (124, 110), (120 + wag, 90 + wag * 0.6)]
    line(tail_pts, fill=C.OUTLINE, width=13, smooth=True, capstyle='round')
    line(tail_pts, fill=C.BODY, width=9, smooth=True, capstyle='round')

    # ---------- 四条腿 ----------
    phases = (0.0, math.pi, math.pi, 2 * math.pi)  # 后外、后内、前内、前外
    xs = (62, 74, 86, 98)
    for i, (lx, ph) in enumerate(zip(xs, phases)):
        sway = 0.0
        if state == 'walk':
            lift = max(0.0, math.sin(walk + ph)) * 5.0
            sway = 2.0 * math.sin(walk + ph)
        elif state in ('drag', 'fall'):
            lift = -3.0 + 3.0 * math.sin(t * 3.0 + i * 1.3)  # 悬空晃腿
            sway = 2.5 * math.sin(t * 3.0 + i * 1.3)
        elif state == 'sleep':
            lift = 0.0
        else:
            lift = 0.0
        leg_bottom = C.PET_FOOT_Y - lift
        oval(lx - 5 + sway, 128, lx + 5 + sway, leg_bottom,
             fill=C.BODY, outline=C.OUTLINE, width=2)

    # ---------- 身体 ----------
    oval(48, 96 + breathing * 0.5, 112, 140,
         fill=C.BODY, outline=C.OUTLINE, width=2)
    oval(60, 106 + breathing * 0.5, 100, 138, fill=C.CREAM, outline='')
    # 背部条纹
    line([(94, 100), (101, 116)], fill=C.BODY_DARK, width=4, capstyle='round')
    line([(104, 103), (109, 119)], fill=C.BODY_DARK, width=4, capstyle='round')

    # ---------- 头部 ----------
    # 耳朵（先画，让头盖住耳根）
    poly([(60, 54 + hy), (50, 26 + hy), (76, 46 + hy)],
         fill=C.BODY, outline=C.OUTLINE, width=2)
    poly([(100, 54 + hy), (110, 26 + hy), (84, 46 + hy)],
         fill=C.BODY, outline=C.OUTLINE, width=2)
    poly([(62, 49 + hy), (56, 34 + hy), (72, 44 + hy)], fill=C.EAR_INNER, outline='')
    poly([(98, 49 + hy), (104, 34 + hy), (88, 44 + hy)], fill=C.EAR_INNER, outline='')

    oval(56, 48 + hy, 104, 96 + hy, fill=C.BODY, outline=C.OUTLINE, width=2)
    # 额头条纹
    for pts in ([(72, 48), (75, 55)], [(80, 47), (80, 55)], [(88, 48), (85, 55)]):
        line([(x, y + hy) for x, y in pts], fill=C.BODY_DARK, width=3, capstyle='round')

    _draw_eyes(cv, state, t, hy, line=line, oval=oval)

    # 鼻子
    poly([(76, 78 + hy), (84, 78 + hy), (80, 83 + hy)], fill=C.NOSE, outline='')

    # 嘴
    if state == 'happy':
        line([(72, 84 + hy), (76, 90 + hy), (84, 90 + hy), (88, 84 + hy)],
             smooth=True, width=2, fill=C.OUTLINE)
    elif state == 'sleep':
        line([(77, 86 + hy), (83, 86 + hy)], width=2, fill=C.OUTLINE)
    elif state == 'drag':
        oval(76, 84 + hy, 84, 92 + hy, fill='', outline=C.OUTLINE, width=2)
    else:
        line([(74, 84 + hy), (77, 87 + hy), (80, 84 + hy), (83, 87 + hy), (86, 84 + hy)],
             smooth=True, width=2, fill=C.OUTLINE)

    # 胡须
    for y1, y2 in ((72, 68), (76, 76), (80, 84)):
        line([(50, y1 + hy), (30, y2 + hy)], fill=C.OUTLINE, width=1)
        line([(110, y1 + hy), (130, y2 + hy)], fill=C.OUTLINE, width=1)

    # 开心时的脸颊红晕
    if state == 'happy':
        oval(58, 80 + hy, 68, 87 + hy, fill=C.BLUSH, outline='')
        oval(92, 80 + hy, 102, 87 + hy, fill=C.BLUSH, outline='')

    # ---------- 粒子（爱心 / Zzz）----------
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

    # ---------- 气泡 ----------
    if bubble_text:
        _draw_bubble(cv, bubble_text)


def _draw_eyes(cv, state, t, hy, *, line, oval):
    """根据状态画眼睛：正常 / 眨眼 / 眯眼睡 / 眯眼笑 / 瞪大。"""
    ex1, ex2, ey = 70, 90, 70 + hy

    def normal(ex):
        oval(ex - 4, ey - 5, ex + 4, ey + 5, fill=C.EYE, outline='')
        oval(ex + 1, ey - 3, ex + 3, ey - 1, fill='white', outline='')

    def wide(ex):
        oval(ex - 5, ey - 6, ex + 5, ey + 6, fill=C.EYE, outline='')
        oval(ex + 1, ey - 4, ex + 4, ey - 1, fill='white', outline='')

    def closed(ex):
        line([(ex - 5, ey), (ex, ey + 3), (ex + 5, ey)],
             smooth=True, width=2, fill=C.EYE, capstyle='round')

    def smiling(ex):
        line([(ex - 5, ey + 2), (ex, ey - 3), (ex + 5, ey + 2)],
             smooth=True, width=2, fill=C.EYE, capstyle='round')

    if state == 'sleep':
        closed(ex1), closed(ex2)
    elif state == 'happy':
        smiling(ex1), smiling(ex2)
    elif state == 'drag' or state == 'fall':
        wide(ex1), wide(ex2)
    elif (t % C.BLINK_PERIOD) < C.BLINK_DURATION:
        line([(ex1 - 4, ey), (ex1 + 4, ey)], width=2, fill=C.EYE)
        line([(ex2 - 4, ey), (ex2 + 4, ey)], width=2, fill=C.EYE)
    else:
        normal(ex1), normal(ex2)


def _draw_bubble(cv, text):
    """头顶圆角气泡。"""
    x1, y1, x2, y2, r = 16, 2, 144, 36, 8
    pts = [(x1 + r, y1), (x2 - r, y1), (x2, y1 + r), (x2, y2 - r),
           (x2 - r, y2), (x1 + r, y2), (x1, y2 - r), (x1, y1 + r)]
    cv.create_polygon(pts, smooth=True, fill=C.BUBBLE_BG,
                      outline=C.BUBBLE_EDGE, width=2)
    cv.create_polygon([(72, 34), (88, 34), (80, 45)],
                      fill=C.BUBBLE_BG, outline='')
    cv.create_line([(73, 35), (80, 44), (87, 35)],
                   fill=C.BUBBLE_BG, width=2)
    cv.create_text(80, 19, text=text, font=C.FONT, fill=C.BUBBLE_FG, width=120)
