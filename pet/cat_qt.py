# -*- coding: utf-8 -*-
"""橘猫逐帧绘制的 QPainter 移植版（pet/sprites.py 的 Qt 对应层）。

做法：给 sprites.py 用的 tk Canvas 图元（oval / line / poly）做一个
QPainter 最小适配层（create_oval / create_line / create_polygon），
绘制主体与 sprites.draw_frame 一一对应搬过来；眼睛与睡姿直接复用
sprites 的私有助手（它们只依赖那几个闭包）。坐标系仍是 160x160
（C.WINDOW_SIZE），由调用方先把 painter 缩放到窗口边长。

tk smooth 样条用"中点二次贝塞尔"近似：相邻中点连线、原点作控制点，
视觉上与 Canvas smooth 足够接近。
"""
import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainterPath, QPen, QPolygonF

from . import config as C
from . import sprites as _tk_sprites
from .drawutil import make_mirror


class QtCanvas:
    """tk Canvas 图元 → QPainter 的适配层（只实现 sprites.py 用到的）。"""

    def __init__(self, painter):
        self.p = painter

    # ---- tk 图元签名 ----
    def delete(self, _tag):        # 每帧全清由 Qt 重绘机制天然完成
        pass

    @staticmethod
    def _color(name):
        return QColor(name)

    def create_oval(self, x1, y1, x2, y2, fill='', outline='', width=1):
        p = self.p
        p.setPen(QPen(self._color(outline), width) if outline
                 else Qt.NoPen)
        p.setBrush(self._color(fill) if fill else Qt.NoBrush)
        p.drawEllipse(QRectF(QPointF(x1, y1), QPointF(x2, y2)))

    def create_line(self, pts, fill='', width=1, smooth=False,
                    capstyle='round'):
        p = self.p
        cap = Qt.RoundCap if capstyle == 'round' else Qt.FlatCap
        p.setPen(QPen(self._color(fill), width, Qt.SolidLine, cap,
                      Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        p.drawPath(_smooth_path(pts, closed=False) if smooth
                   else _poly_path(pts))

    def create_polygon(self, pts, fill='', outline='', width=1,
                       smooth=False):
        p = self.p
        p.setPen(QPen(self._color(outline), width, Qt.SolidLine,
                      Qt.RoundCap, Qt.RoundJoin) if outline else Qt.NoPen)
        p.setBrush(self._color(fill) if fill else Qt.NoBrush)
        path = _smooth_path(pts, closed=True) if smooth else _poly_path(pts)
        path.closeSubpath()
        p.drawPath(path)


def _poly_path(pts):
    path = QPainterPath(QPointF(*pts[0]))
    for x, y in pts[1:]:
        path.lineTo(x, y)
    return path


def _smooth_path(pts, closed):
    """中点二次贝塞尔平滑：每段曲线由相邻中点连成，原顶点作控制点。"""
    n = len(pts)
    if n < 3:
        return _poly_path(pts)
    mid = lambda a, b: QPointF((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    if closed:
        path = QPainterPath(mid(pts[-1], pts[0]))
        for i in range(n):
            cur, nxt = pts[i], pts[(i + 1) % n]
            path.quadTo(QPointF(*cur), mid(cur, nxt))
    else:
        path = QPainterPath(QPointF(*pts[0]))
        for i in range(1, n - 1):
            cur, nxt = pts[i], pts[i + 1]
            path.quadTo(QPointF(*cur), mid(cur, nxt))
        path.lineTo(pts[-1][0], pts[-1][1])
    return path


def draw_frame(cv, *, state, t, facing):
    """绘制一帧橘猫（Qt 版）。参数含义同 sprites.draw_frame；
    粒子与气泡由 qt_render 统一绘制，这里不画。"""
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
        _tk_sprites._draw_sleep_loaf(cv, oval, line, poly)
        return

    # ---------- 尾巴（画在身体后面）：上翘的 S 形 + 奶油尾尖 + 深色尾环 ----------
    wag = math.sin(walk) * 3.0 if state == 'walk' else math.sin(t * 2.6) * 6.0
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
    poly([(60, 49 + hy), (54, 33 + hy), (72, 44 + hy)],
         fill=C.EAR_INNER, outline='')
    poly([(100, 49 + hy), (106, 33 + hy), (88, 44 + hy)],
         fill=C.EAR_INNER, outline='')
    # 耳内绒毛
    both(lambda X, _s: (line([(X(60), 43 + hy), (X(64), 37 + hy)],
                             fill=C.CREAM, width=2),
                        line([(X(64), 45 + hy), (X(69), 39 + hy)],
                             fill=C.CREAM, width=2)))

    oval(54, 46 + hy, 106, 98 + hy, fill=C.BODY, outline=C.OUTLINE, width=2)
    # 额头条纹
    for pts in ([(72, 48), (75, 55)], [(80, 47), (80, 55)],
                [(88, 48), (85, 55)]):
        line([(x, y + hy) for x, y in pts], fill=C.BODY_DARK, width=3,
             capstyle='round')

    # 口鼻部（奶油色小椭圆，鼻子嘴巴都落在上面）
    oval(68, 74 + hy, 92, 92 + hy, fill=C.CREAM, outline='')

    _tk_sprites._draw_eyes(cv, state, t, hy, line=line, oval=oval)

    # 鼻子
    poly([(76, 78 + hy), (84, 78 + hy), (80, 83 + hy)], fill=C.NOSE,
         outline='')

    # 嘴
    if state == 'happy':
        line([(72, 84 + hy), (76, 90 + hy), (84, 90 + hy), (88, 84 + hy)],
             smooth=True, width=2, fill=C.OUTLINE)
        oval(77, 88 + hy, 83, 94 + hy, fill='#E8837E', outline='')
    elif state == 'drag':
        oval(76, 84 + hy, 84, 92 + hy, fill='', outline=C.OUTLINE, width=2)
    else:
        line([(74, 84 + hy), (77, 87 + hy), (80, 84 + hy), (83, 87 + hy),
              (86, 84 + hy)],
             smooth=True, width=2, fill=C.OUTLINE)

    # 胡须（从口鼻两侧出发，带弧度）
    both(lambda X, _s: [line([(X(66), y1 + hy), (X(44), y2 + hy)],
                             fill=C.OUTLINE, width=1, smooth=True)
                        for y1, y2 in ((74, 70), (78, 78), (82, 86))])

    # 开心时的脸颊红晕
    if state == 'happy':
        oval(56, 78 + hy, 66, 86 + hy, fill=C.BLUSH, outline='')
        oval(94, 78 + hy, 104, 86 + hy, fill=C.BLUSH, outline='')
