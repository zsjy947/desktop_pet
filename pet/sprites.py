# -*- coding: utf-8 -*-
"""橘猫的逐帧绘制：不依赖任何图片素材，全部用 Canvas 图元程序化画出。

每帧整体重绘一次（delete('all') 后重画），160x160 画布、约 40 个图元，
30fps 下开销可忽略。
"""
import math

from . import config as C
from .drawutil import make_mirror, draw_bubble, draw_particles


def draw_frame(cv, *, state, t, facing, bubble_text, particles):
    """绘制一帧橘猫。

    state: idle | walk | sleep | drag | fall | happy
    t:     动画时间（秒）
    facing: 1 朝右 / -1 朝左
    bubble_text: 气泡文字（空串则不画）
    particles: 粒子列表（爱心 / Zzz）
    """
    cv.delete('all')
    mx, bx, oval, line, poly, both = make_mirror(cv, facing)

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

    if state == 'sleep':
        _draw_sleep_loaf(cv, oval, line, poly)
        draw_particles(cv, particles)
        if bubble_text:
            draw_bubble(cv, bubble_text, C.WINDOW_SIZE)
        return

    # ---------- 尾巴（画在身体后面）：上翘的 S 形 + 奶油尾尖 + 深色尾环 ----------
    if state == 'walk':
        wag = math.sin(walk) * 3.0
    else:
        wag = math.sin(t * 2.6) * 6.0
    tail_pts = [(102, 124), (122, 116), (128, 98), (118 + wag, 86 + wag * 0.4)]
    line(tail_pts, fill=C.OUTLINE, width=13, smooth=True, capstyle='round')
    line(tail_pts, fill=C.BODY, width=9, smooth=True, capstyle='round')
    line([(123, 112), (129, 106)], fill=C.BODY_DARK, width=9, capstyle='round')
    line([(126, 102), (131, 97)], fill=C.BODY_DARK, width=8, capstyle='round')
    oval(113 + wag, 81 + wag * 0.4, 123 + wag, 91 + wag * 0.4,
         fill=C.CREAM, outline='')

    # ---------- 四条腿（圆爪 + 奶油爪垫）----------
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
        else:
            lift = 0.0
        leg_bottom = C.PET_FOOT_Y - lift
        oval(lx - 5 + sway, 128, lx + 5 + sway, leg_bottom,
             fill=C.BODY, outline=C.OUTLINE, width=2)
        oval(lx - 5 + sway, leg_bottom - 8, lx + 5 + sway, leg_bottom,
             fill=C.CREAM, outline=C.OUTLINE, width=1)

    # ---------- 身体（后宽前窄的流线形 + 后腿弧线）----------
    poly([(78, 95), (96, 97), (109, 107), (112, 124), (106, 139),
          (88, 142), (64, 142), (51, 134), (47, 117), (55, 102), (67, 96)],
         smooth=True, fill=C.BODY, outline=C.OUTLINE, width=2)
    line([(58, 110), (50, 122), (57, 134)], smooth=True,
         fill=C.OUTLINE, width=2)
    oval(60, 106, 100, 138, fill=C.CREAM, outline='')
    # 胸口绒毛
    poly([(66, 94), (72, 104), (78, 96), (84, 104), (90, 96), (95, 103),
          (97, 94)], smooth=True, fill=C.CREAM, outline='')
    # 背部条纹（带弧度）
    line([(92, 99), (100, 115)], fill=C.BODY_DARK, width=4,
         capstyle='round', smooth=True)
    line([(103, 102), (109, 118)], fill=C.BODY_DARK, width=4,
         capstyle='round', smooth=True)

    # ---------- 头部 ----------
    # 耳朵（先画，让头盖住耳根）
    poly([(58, 54 + hy), (46, 24 + hy), (78, 44 + hy)],
         fill=C.BODY, outline=C.OUTLINE, width=2)
    poly([(102, 54 + hy), (114, 24 + hy), (82, 44 + hy)],
         fill=C.BODY, outline=C.OUTLINE, width=2)
    poly([(60, 49 + hy), (54, 33 + hy), (72, 44 + hy)], fill=C.EAR_INNER, outline='')
    poly([(100, 49 + hy), (106, 33 + hy), (88, 44 + hy)], fill=C.EAR_INNER, outline='')
    # 耳内绒毛
    both(lambda X, _s: (line([(X(60), 43 + hy), (X(64), 37 + hy)],
                             fill=C.CREAM, width=2),
                        line([(X(64), 45 + hy), (X(69), 39 + hy)],
                             fill=C.CREAM, width=2)))

    oval(54, 46 + hy, 106, 98 + hy, fill=C.BODY, outline=C.OUTLINE, width=2)
    # 额头条纹
    for pts in ([(72, 48), (75, 55)], [(80, 47), (80, 55)], [(88, 48), (85, 55)]):
        line([(x, y + hy) for x, y in pts], fill=C.BODY_DARK, width=3, capstyle='round')

    # 口鼻部（奶油色小椭圆，鼻子嘴巴都落在上面）
    oval(68, 74 + hy, 92, 92 + hy, fill=C.CREAM, outline='')

    _draw_eyes(cv, state, t, hy, line=line, oval=oval)

    # 鼻子
    poly([(76, 78 + hy), (84, 78 + hy), (80, 83 + hy)], fill=C.NOSE, outline='')

    # 嘴
    if state == 'happy':
        line([(72, 84 + hy), (76, 90 + hy), (84, 90 + hy), (88, 84 + hy)],
             smooth=True, width=2, fill=C.OUTLINE)
        oval(77, 88 + hy, 83, 94 + hy, fill='#E8837E', outline='')
    elif state == 'drag':
        oval(76, 84 + hy, 84, 92 + hy, fill='', outline=C.OUTLINE, width=2)
    else:
        line([(74, 84 + hy), (77, 87 + hy), (80, 84 + hy), (83, 87 + hy), (86, 84 + hy)],
             smooth=True, width=2, fill=C.OUTLINE)

    # 胡须（从口鼻两侧出发，带弧度）
    both(lambda X, _s: [line([(X(66), y1 + hy), (X(44), y2 + hy)],
                             fill=C.OUTLINE, width=1, smooth=True)
                        for y1, y2 in ((74, 70), (78, 78), (82, 86))])

    # 开心时的脸颊红晕
    if state == 'happy':
        oval(56, 78 + hy, 66, 86 + hy, fill=C.BLUSH, outline='')
        oval(94, 78 + hy, 104, 86 + hy, fill=C.BLUSH, outline='')

    # ---------- 粒子（爱心 / Zzz）----------
    draw_particles(cv, particles)

    # ---------- 气泡 ----------
    if bubble_text:
        draw_bubble(cv, bubble_text, C.WINDOW_SIZE)


def _draw_sleep_loaf(cv, oval, line, poly):
    """睡觉时蜷成一张“猫面包”，头搁在身前、尾巴绕过来。"""
    # 尾巴从身后绕到胸前
    tail_pts = [(116, 142), (127, 133), (123, 120)]
    line(tail_pts, fill=C.OUTLINE, width=12, smooth=True, capstyle='round')
    line(tail_pts, fill=C.BODY, width=8, smooth=True, capstyle='round')
    oval(118, 115, 128, 125, fill=C.CREAM, outline='')

    # 蜷起的身体
    oval(38, 116, 124, 148, fill=C.BODY, outline=C.OUTLINE, width=2)
    # 露出的前爪
    oval(58, 134, 76, 148, fill=C.CREAM, outline=C.OUTLINE, width=1)
    oval(80, 134, 98, 148, fill=C.CREAM, outline=C.OUTLINE, width=1)

    # 搁在身前的头
    poly([(58, 102), (50, 80), (76, 94)], fill=C.BODY, outline=C.OUTLINE, width=2)
    poly([(102, 102), (110, 80), (84, 94)], fill=C.BODY, outline=C.OUTLINE, width=2)
    poly([(60, 98), (55, 87), (72, 95)], fill=C.EAR_INNER, outline='')
    poly([(100, 98), (105, 87), (88, 95)], fill=C.EAR_INNER, outline='')
    oval(50, 94, 110, 138, fill=C.BODY, outline=C.OUTLINE, width=2)

    # 额头条纹
    line([(72, 96), (74, 103)], fill=C.BODY_DARK, width=3, capstyle='round')
    line([(88, 96), (86, 103)], fill=C.BODY_DARK, width=3, capstyle='round')

    # 口鼻部 + 闭眼
    oval(70, 112, 94, 130, fill=C.CREAM, outline='')
    line([(62, 116), (68, 119), (74, 116)], smooth=True, width=2,
         fill=C.EYE, capstyle='round')
    line([(86, 116), (92, 119), (98, 116)], smooth=True, width=2,
         fill=C.EYE, capstyle='round')
    poly([(77, 118), (85, 118), (81, 122)], fill=C.NOSE, outline='')
    line([(78, 125), (84, 125)], width=2, fill=C.OUTLINE)
    for x1, y1, x2, y2 in ((68, 118, 48, 114), (68, 122, 48, 124),
                           (94, 118, 114, 114), (94, 122, 114, 124)):
        line([(x1, y1), (x2, y2)], fill=C.OUTLINE, width=1)


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
