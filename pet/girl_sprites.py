# -*- coding: utf-8 -*-
"""Q 版少女的逐帧绘制：按角色预设参数化画出，不依赖图片素材。

形象特征来自 reference/pictures：发色发型、瞳色、服装、腿袜、
头饰（蝴蝶结/宽檐帽/毛线帽/花环/头纱……）一一对应参考图。
"""
import math

from . import characters as CH
from . import config as C
from .drawutil import make_mirror, draw_bubble, draw_particles

EYE_LINE = '#3A2E2A'      # 睫毛/眼线
MOUTH = '#B06055'
MOUTH_OPEN = '#B85B5B'
BLUSH_SOFT = '#F6C6C6'
BLUSH_STRONG = '#F2A9A9'
WHITE_OUT = '#C9C4B4'     # 白色衣物/帽子的描边
GLASSES = '#4A4A52'


def draw_frame(cv, *, char, state, t, facing, bubble_text, particles):
    """绘制一帧 Q 版少女。参数含义同 sprites.draw_frame。"""
    cv.delete('all')
    mx, bx, oval, line, poly, both = make_mirror(cv, facing)

    walk = t * 9.0 if state == 'walk' else 0.0
    breathing = math.sin(t * 2.2) * 1.2 if state in ('idle', 'sleep') else 0.0
    if state == 'walk':
        bob = abs(math.sin(walk)) * 2.0
    elif state == 'happy':
        bob = abs(math.sin(t * 7.0)) * 4.0
    elif state in ('idle', 'sleep'):
        bob = breathing * 0.5
    else:
        bob = 0.0
    hy = bob  # 头部组整体上下偏移

    _back_hair(cv, char, oval, line, both, state, t, walk, hy)
    _neck(cv, oval)
    _legs_shoes(cv, char, oval, line, state, t, walk)
    _outfit(cv, char, oval, line, poly)
    _arms(cv, char, oval, line, state, t)
    _head(cv, char, oval, hy)
    _face(cv, char, oval, line, poly, state, t, hy)
    _front_hair(cv, char, oval, poly, line, both, hy)
    _headwear(cv, char, oval, poly, line, both, hy)
    _extras(cv, char, oval, line, poly)

    draw_particles(cv, particles)
    if bubble_text:
        draw_bubble(cv, bubble_text)


# ---------- 分层部件 ----------

def _back_hair(cv, ch, oval, line, both, state, t, walk, hy):
    """脑后的头发：先画，被身体和脸盖住。"""
    h, hd = ch['hair'], ch['hair_dark']
    style = ch['style']

    if style == 'twin':
        oval(44, 30 + hy, 116, 96 + hy, fill=h, outline=hd, width=2)
        amp = 5.0 if state == 'walk' else 3.0
        s1 = math.sin(walk) * amp if state == 'walk' else math.sin(t * 2.2) * amp

        def tail(X, side):
            pts = [(X(50), 42 + hy),
                   (X(34) + side * s1 * 0.5, 60 + hy),
                   (X(28) + side * s1, 86 + hy)]
            line(pts, fill=hd, width=20, smooth=True, capstyle='round')
            line(pts, fill=h, width=15, smooth=True, capstyle='round')
            tx = X(28) + side * s1
            oval(tx - 5, 82 + hy, tx + 5, 92 + hy, fill=h, outline=hd, width=1)
        both(tail)
        return

    if style == 'ponytail':
        oval(44, 30 + hy, 116, 94 + hy, fill=h, outline=hd, width=2)
        s1 = math.sin(walk) * 5.0 if state == 'walk' else math.sin(t * 2.2) * 3.0
        pts = [(98, 34 + hy), (116, 52 + hy), (118 + s1, 82 + hy)]
        line(pts, fill=hd, width=19, smooth=True, capstyle='round')
        line(pts, fill=h, width=14, smooth=True, capstyle='round')
        oval(114 + s1 - 5, 80 + hy, 114 + s1 + 5, 90 + hy,
             fill=h, outline=hd, width=1)
    else:
        # bob 短发 / long 长发 / xlong 超长发 / buns 侧发髻
        bottom = {'bob': 100, 'long': 106, 'xlong': 108, 'buns': 106}[style]
        oval(42, 30 + hy, 118, bottom + hy, fill=h, outline=hd, width=2)
        if style in ('long', 'xlong', 'buns'):
            tip = 132 if style == 'xlong' else (120 if style == 'long' else 112)
            oval(40, 60 + hy, 54, tip + hy, fill=h, outline=hd, width=2)
            oval(106, 60 + hy, 120, tip + hy, fill=h, outline=hd, width=2)
        if style == 'buns':
            # 竹兰式黑色侧发髻 + 金色发带
            for cx in (44, 116):
                oval(cx - 15, 42 + hy, cx + 15, 66 + hy,
                     fill='#35323E', outline='#211F26', width=2)
                line([(cx - 10, 54 + hy), (cx + 10, 54 + hy)],
                     fill='#D9BE7A', width=3)


def _neck(cv, oval):
    oval(76, 84, 84, 97, fill=CH.SKIN, outline='')


def _legs_shoes(cv, ch, oval, line, state, t, walk):
    """两条腿 + 鞋。先画，裙摆会盖住大腿根。"""
    leg, shoe = ch['leg'], ch['shoes']
    for i, lx in enumerate((71, 89)):
        if state == 'walk':
            ph = walk + (0.0 if i == 0 else math.pi)
            sway = 3.0 * math.sin(ph)
            lift = max(0.0, math.sin(ph)) * 4.0
        elif state in ('drag', 'fall'):
            sway = 2.5 * math.sin(t * 3.0 + i * 1.6)
            lift = -2.0 + 2.0 * math.sin(t * 3.0 + i * 1.6)
        else:
            sway, lift = 0.0, 0.0
        hip, foot = 124, C.PET_FOOT_Y - lift
        line([(lx, hip), (lx + sway, foot - 4)],
             fill=leg, width=8, capstyle='round')
        # 鞋（脚尖朝前）
        oval(lx + sway - 8, foot - 8, lx + sway + 9, foot,
             fill=shoe, outline=WHITE_OUT if _is_light(shoe) else _shade(shoe),
             width=1)


def _outfit(cv, ch, oval, line, poly):
    """服装主体：按 outfit 类型分派。"""
    c1, c2 = ch['c1'], ch['c2']
    kind = ch['outfit']
    o1 = WHITE_OUT if _is_light(c1) else _shade(c1)
    o2 = WHITE_OUT if _is_light(c2) else _shade(c2)

    if kind == 'dress':
        poly([(62, 92), (98, 92), (100, 112), (60, 112)],
             fill=c1, outline=o1, width=1)
        _skirt(cv, poly, line, c1, c2, o1, top=106, hem=130, spread=11)
        line([(66, 96), (94, 96)], fill=c2, width=3)
    elif kind == 'shirt_skirt':
        poly([(61, 92), (99, 92), (101, 112), (59, 112)],
             fill=c1, outline=o1, width=1)
        line([(80, 94), (72, 101)], fill=_shade(c1), width=2)
        line([(80, 94), (88, 101)], fill=_shade(c1), width=2)
        oval(79, 104, 82, 107, fill=o1, outline='')
        _skirt(cv, poly, line, c2, _shade(c2), o2, top=110, hem=127, spread=9)
    elif kind == 'shorts':
        poly([(61, 92), (99, 92), (101, 112), (59, 112)],
             fill=c1, outline=o1, width=1)
        line([(80, 94), (72, 101)], fill=_shade(c1), width=2)
        line([(80, 94), (88, 101)], fill=_shade(c1), width=2)
        poly([(57, 110), (103, 110), (106, 126), (54, 126)],
             fill=c2, outline=o2, width=1)
        line([(80, 126), (80, 117)], fill=o2, width=2)
    elif kind == 'top_skirt':
        poly([(61, 92), (99, 92), (101, 112), (59, 112)],
             fill=c1, outline=o1, width=1)
        _skirt(cv, poly, line, c2, _shade(c2), o2, top=110, hem=128, spread=10)
    elif kind == 'coat':
        poly([(60, 92), (100, 92), (103, 120), (57, 120)],
             fill=c1, outline=o1, width=1)
        _skirt(cv, poly, line, c1, c2, o1, top=116, hem=132, spread=11)
        # 毛领
        poly([(63, 90), (69, 99), (75, 91), (81, 99), (87, 91), (93, 99),
              (97, 90), (97, 85), (63, 85)],
             smooth=True, fill=c2, outline='')
        oval(78, 106, 82, 110, fill='#8A8A94', outline='')
        oval(78, 116, 82, 120, fill='#8A8A94', outline='')
    elif kind == 'kimono':
        # 广袖
        oval(42, 94, 68, 118, fill=c1, outline=o1, width=1)
        oval(92, 94, 118, 118, fill=c1, outline=o1, width=1)
        oval(48, 115, 55, 121, fill=CH.SKIN, outline='')
        oval(105, 115, 112, 121, fill=CH.SKIN, outline='')
        poly([(60, 92), (100, 92), (102, 114), (58, 114)],
             fill=c1, outline=o1, width=1)
        # 交领
        poly([(74, 92), (80, 92), (76, 106)], fill=CH.SKIN, outline='')
        poly([(86, 92), (80, 92), (84, 106)], fill=CH.SKIN, outline='')
        line([(77, 94), (74, 106)], fill=c2, width=2)
        line([(83, 94), (86, 106)], fill=c2, width=2)
        # 腰封 + 长裙
        poly([(57, 106), (103, 106), (103, 115), (57, 115)],
             fill=c2, outline=o2, width=1)
        poly([(59, 115), (101, 115), (107, 140), (53, 140)],
             fill=c1, outline=o1, width=1)
        line([(62, 132), (98, 132)], fill=_shade(c1), width=2)
    elif kind == 'tutu':
        poly([(62, 92), (98, 92), (98, 110), (62, 110)],
             fill=c1, outline=o1, width=1)
        # 两层纱裙
        poly([(50, 112), (110, 112), (119, 130), (41, 130)],
             fill=c2, outline=o2, width=1)
        poly([(55, 108), (105, 108), (114, 125), (46, 125)],
             fill=c1, outline=o1, width=1)
        line([(62, 109), (98, 109)], fill=c2, width=3)


def _skirt(cv, poly, line, c1, band, outline, top, hem, spread):
    """百褶短裙：梯形 + 锯齿下摆 + 裙摆阴影线。"""
    n = 8
    pts = [(80 - spread - 5, top), (80 + spread + 5, top)]
    xs = [80 - spread - 5 + i * (2 * spread + 10) / n for i in range(n + 1)]
    hem_pts = [(x, hem + (4 if i % 2 else 0)) for i, x in enumerate(xs)]
    poly(pts + hem_pts[::-1], fill=c1, outline=outline, width=1)
    line([(80 - spread, hem - 3), (80 + spread, hem - 3)],
         fill=band, width=2)


def _arms(cv, ch, oval, line, state, t):
    """手臂：袖子用服装主色，末端露出手。"""
    if ch['outfit'] == 'kimono':
        return  # 广袖已画，不单独画手臂
    sleeve = ch['c1']
    walk = t * 9.0 if state == 'walk' else 0.0
    for i, sx in enumerate((64, 96)):
        if state == 'walk':
            dy = 2.0 * math.sin(walk + (0.0 if i == 0 else math.pi))
        elif state in ('drag', 'fall'):
            dy = -4.0 + 1.5 * math.sin(t * 3.0 + i * 1.3)
        elif state == 'happy':
            dy = -5.0
        else:
            dy = 0.0
        hx = sx - 9 if i == 0 else sx + 9
        line([(sx, 96), (hx, 112 + dy)], fill=sleeve, width=7, capstyle='round')
        oval(hx - 3, 110 + dy, hx + 3, 116 + dy,
             fill=CH.SKIN, outline=CH.SKIN_DARK, width=1)


def _head(cv, ch, oval, hy):
    oval(48, 34 + hy, 112, 92 + hy, fill=CH.SKIN, outline=CH.SKIN_DARK,
         width=2)


def _face(cv, ch, oval, line, poly, state, t, hy):
    """眼睛（大瞳孔 + 高光）、眉毛、腮红、嘴巴。"""
    ex1, ex2, ey = 67, 93, 66 + hy
    eye = ch['eye']

    def brow(ex):
        line([(ex - 5, ey - 14), (ex + 1, ey - 15), (ex + 6, ey - 14)],
             smooth=True, width=1, fill=ch['hair_dark'])

    def normal(ex):
        oval(ex - 7, ey - 8, ex + 7, ey + 8, fill='white',
             outline=CH.FACE_LINE, width=1)
        oval(ex - 4, ey - 6, ex + 4, ey + 6, fill=eye, outline='')
        oval(ex - 2, ey - 1, ex + 2, ey + 5, fill='#2A2028', outline='')
        oval(ex - 4, ey - 5, ex - 0.5, ey - 1, fill='white', outline='')
        oval(ex + 2, ey + 1, ex + 3.5, ey + 2.5, fill='white', outline='')
        line([(ex - 7, ey - 7), (ex, ey - 10), (ex + 7, ey - 7)],
             smooth=True, width=2, fill=EYE_LINE)

    def wide(ex):
        oval(ex - 8, ey - 9, ex + 8, ey + 9, fill='white',
             outline=CH.FACE_LINE, width=1)
        oval(ex - 4, ey - 5, ex + 4, ey + 6, fill=eye, outline='')
        oval(ex - 1.5, ey, ex + 1.5, ey + 4, fill='#2A2028', outline='')
        oval(ex - 4, ey - 5, ex - 0.5, ey - 1, fill='white', outline='')

    def closed(ex):
        line([(ex - 6, ey + 1), (ex, ey + 4), (ex + 6, ey + 1)],
             smooth=True, width=2, fill=EYE_LINE, capstyle='round')

    def smiling(ex):
        line([(ex - 6, ey + 3), (ex, ey - 4), (ex + 6, ey + 3)],
             smooth=True, width=2, fill=EYE_LINE, capstyle='round')

    if state == 'sleep':
        closed(ex1), closed(ex2)
    elif state == 'happy':
        smiling(ex1), smiling(ex2)
    elif state in ('drag', 'fall'):
        wide(ex1), wide(ex2)
    elif (t % C.BLINK_PERIOD) < C.BLINK_DURATION:
        closed(ex1), closed(ex2)
    else:
        normal(ex1), normal(ex2)
    brow(ex1), brow(ex2)

    blush = BLUSH_STRONG if state == 'happy' else BLUSH_SOFT
    oval(53, ey + 5, 63, ey + 12, fill=blush, outline='')
    oval(97, ey + 5, 107, ey + 12, fill=blush, outline='')

    my = 80 + hy
    if state == 'happy':
        poly([(75, my - 2), (85, my - 2), (80, my + 6)],
             fill=MOUTH_OPEN, outline='#8E4040', width=1)
    elif state == 'sleep':
        line([(77, my), (83, my)], width=2, fill=MOUTH)
    elif state in ('drag', 'fall'):
        oval(77, my - 4, 83, my + 2, fill='', outline=MOUTH, width=2)
    else:
        line([(76, my - 1), (80, my + 3), (84, my - 1)],
             smooth=True, width=2, fill=MOUTH)


def _front_hair(cv, ch, oval, poly, line, both, hy):
    """刘海 + 侧发 + 前发饰。"""
    h, hd = ch['hair'], ch['hair_dark']
    poly([(48, 62), (45, 48), (50, 38), (60, 32), (80, 29), (100, 32),
          (110, 38), (115, 48), (112, 62), (108, 52), (100, 58), (92, 50),
          (82, 57), (72, 50), (62, 58), (54, 51)],
         smooth=True, fill=h, outline=hd, width=1)
    line([(70, 33), (66, 47)], fill=hd, width=1)
    line([(88, 33), (92, 47)], fill=hd, width=1)
    lock_bottom = 84 if ch['style'] == 'bob' else 94
    both(lambda X, _s: oval(X(44), 50 + hy, X(57), lock_bottom + hy,
                            fill=h, outline=hd, width=2))
    if ch.get('braid'):
        # 莉莉艾式侧编发
        for cx, cy in ((110, 96), (111, 106), (110, 116)):
            oval(cx - 5, cy - 5, cx + 5, cy + 5, fill=h, outline=hd, width=1)
    if ch['id'] == 'dawn':
        # 小光的黄色发饰
        both(lambda X, _s: poly([(X(44), 54 + hy), (X(53), 58 + hy),
                                 (X(46), 66 + hy)],
                                fill='#F2C94C', outline=''))


def _headwear(cv, ch, oval, poly, line, both, hy):
    acc = ch.get('acc')
    ac = ch.get('acc_color', '#3A3440')
    if not acc:
        return

    if acc == 'bow':
        # 二乃式蝴蝶结 + 白色发箍线
        line([(52, 42 + hy), (108, 42 + hy)], fill='#F5F2EA', width=3)

        def bow(X, _s):
            poly([(X(36), 36 + hy), (X(20), 27 + hy), (X(23), 45 + hy)],
                 fill=ac, outline=_shade(ac), width=1)
            poly([(X(36), 36 + hy), (X(50), 26 + hy), (X(52), 43 + hy)],
                 fill=ac, outline=_shade(ac), width=1)
            oval(X(33), 32 + hy, X(39), 40 + hy, fill=_shade(ac), outline='')
        both(bow)
    elif acc == 'hat':
        oval(32, 34 + hy, 128, 52 + hy, fill='#FBFBF4',
             outline=WHITE_OUT, width=2)
        oval(52, 14 + hy, 108, 42 + hy, fill='#FBFBF4',
             outline=WHITE_OUT, width=2)
        line([(56, 34 + hy), (104, 34 + hy)], fill=ac, width=4)
        poly([(100, 32 + hy), (112, 26 + hy), (113, 40 + hy)],
             fill=ac, outline=_shade(ac), width=1)
    elif acc == 'beanie':
        oval(52, 18 + hy, 108, 46 + hy, fill='#F7F5EF', outline=WHITE_OUT, width=2)
        oval(50, 36 + hy, 110, 52 + hy, fill='#F7F5EF',
             outline=WHITE_OUT, width=2)
        line([(56, 44 + hy), (104, 44 + hy)], fill=WHITE_OUT, width=1)
        oval(90, 26 + hy, 104, 38 + hy, fill='#E88A9A', outline='#D0677C', width=1)
        oval(94, 29 + hy, 100, 34 + hy, fill='#F7F5EF', outline='')
    elif acc == 'flowerband':
        line([(50, 40 + hy), (80, 31 + hy), (110, 40 + hy)],
             smooth=True, fill=ac, width=3)
        both(lambda X, _s: _flower(cv, X(58), 33 + hy, ac, '#F2D067', oval))
    elif acc == 'headband':
        line([(48, 42 + hy), (80, 32 + hy), (112, 42 + hy)],
             smooth=True, fill=ac, width=3)
        # 头顶小蝴蝶结 + 飘带头纱
        poly([(80, 30 + hy), (68, 24 + hy), (70, 36 + hy)],
             fill=ac, outline='#D9D4CA', width=1)
        poly([(80, 30 + hy), (92, 24 + hy), (90, 36 + hy)],
             fill=ac, outline='#D9D4CA', width=1)
        line([(88, 34 + hy), (98, 58 + hy)], fill=ac, width=2)
    elif acc == 'flowers':
        both(lambda X, _s: (_flower(cv, X(102), 30 + hy, ac, '#F2D067', oval),
                            _flower(cv, X(94), 36 + hy, ac, '#F2D067', oval)))


def _flower(cv, cx, cy, petal, center, oval):
    for dx, dy in ((-3.5, 0), (3.5, 0), (0, -3.5), (0, 3.5)):
        oval(cx + dx - 3, cy + dy - 3, cx + dx + 3, cy + dy + 3,
             fill=petal, outline='')
    oval(cx - 1.5, cy - 1.5, cx + 1.5, cy + 1.5, fill=center, outline='')


def _extras(cv, ch, oval, line, poly):
    """围巾 / 领带 / 项链 / 眼镜等小件。"""
    if ch.get('scarf'):
        s = ch['scarf']
        oval(62, 86, 98, 98, fill=s, outline=_shade(s), width=1)
        poly([(74, 94), (86, 94), (84, 112), (76, 112)],
             fill=s, outline=_shade(s), width=1)
        oval(78, 92, 82, 96, fill=_shade(s), outline='')
    if ch.get('tie'):
        t = ch['tie']
        poly([(77, 95), (83, 95), (82, 114), (78, 114)],
             fill=t, outline=_shade(t), width=1)
        poly([(77, 95), (83, 95), (80, 100)], fill=_shade(t), outline='')
    if ch.get('necklace'):
        for x, y in ((70, 96), (74, 99), (80, 100), (86, 99), (90, 96)):
            oval(x - 1.5, y - 1.5, x + 1.5, y + 1.5,
                 fill='#FFFFFF', outline='#D9D4CA', width=1)
    if ch.get('glasses'):
        oval(59, 58, 75, 74, fill='', outline=GLASSES, width=2)
        oval(85, 58, 101, 74, fill='', outline=GLASSES, width=2)
        line([(75, 65), (85, 65)], fill=GLASSES, width=2)
        line([(59, 65), (48, 60)], fill=GLASSES, width=2)
        line([(101, 65), (112, 60)], fill=GLASSES, width=2)


# ---------- 小工具 ----------

def _is_light(hex_color):
    r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
    return (r * 299 + g * 587 + b * 114) / 1000 > 160


def _shade(hex_color, k=0.72):
    r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
    return '#%02X%02X%02X' % (int(r * k), int(g * k), int(b * k))
