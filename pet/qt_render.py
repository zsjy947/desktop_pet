# -*- coding: utf-8 -*-
"""Qt 渲染层：逐像素 alpha 播放器（v2 anims 资产 / hatched 图集）。

与 tk 键色窗口的区别（也是动效根治点）：
    * alpha 不必二值——软边/抗锯齿直接呈现，erode 去边整条链退役；
    * 帧推进用「时长累加器 + 实际 dt」，帧边界与 tick 严格对齐，
      根治绝对时间取模造成的跳帧/重复帧；
    * 呼吸 = 整帧 scaleY(±0.8%) 锚定脚底的正弦变换（替代 1px 位移），
      走路颠步/开心跳用平滑位移，落地有 squash 挤压脉冲；
    * 朝向翻转 = 运行时 QTransform 镜像（anims 资产不再烘焙左右两行）；
    * 粒子为 QPainterPath 自绘软粒子（连续淡出），气泡为真半透明圆角矩形。

蒙版（点击穿透）：body_region() 从帧 alpha 生成 QRegion（numpy 行扫描 +
QBitmap 阈值），app 层再并上气泡/粒子矩形后 setMask——透明区点击穿回桌面，
与键色窗口的穿透体验一致。
"""
import math
import os
import time

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QColor, QFont, QFontMetrics,
                           QImage, QPainter, QPainterPath, QPen,
                           QRegion)

import numpy as np

from . import anims
from . import config as C
from . import hatch_sprites

_PULSE_T = 0.4          # 落地挤压脉冲时长（秒）
_BREATH_AMP = 0.008     # 呼吸 scaleY 幅度


# ---------------------------------------------------------------------------
# alpha → QRegion（点击穿透蒙版）
# ---------------------------------------------------------------------------
def region_from_image(img, thresh=16):
    """QImage 的 alpha 通道 → QRegion（alpha>thresh 为命中区）。

    实现：numpy 按行求不透明行程 → 相同行程的相邻行合并成条带矩形 →
    QRegion.united。不走 QBitmap.fromImage——它在 PySide6 6.11/offscreen
    下会 access violation（实测），且对暗色像素的取向依赖平台实现。
    """
    a = img.convertToFormat(QImage.Format_ARGB32)
    h, w = a.height(), a.width()
    arr = np.frombuffer(a.constBits(), dtype=np.uint8).reshape(
        h, a.bytesPerLine())
    alpha = arr[:, 3::4][:, :w] > thresh     # ARGB32 内存序 alpha 恒第 4 字节

    def _runs(row):
        d = np.diff(np.concatenate(([0], row.astype(np.int8), [0])))
        idx = np.flatnonzero(d)
        return tuple(zip(idx[0::2].tolist(), idx[1::2].tolist()))

    reg = QRegion()
    prev, y0 = None, 0
    for y in range(h + 1):
        runs = _runs(alpha[y]) if y < h else ()
        if runs != prev:
            if prev:
                for x0, x1 in prev:
                    reg = reg.united(QRegion(x0, y0, x1 - x0, y - y0))
            prev, y0 = runs, y
    return reg


# ---------------------------------------------------------------------------
# 粒子（QPainterPath 自绘，数据来自 pet/fx.py）
# ---------------------------------------------------------------------------
_FX_COLORS = {
    'spark': ('#FFE066', '#F5A623'),
    'leaf': ('#7FC97F', '#4E9A4E'),
    'flower': ('#F8BBD0', '#E48AB4'),
    'fire': ('#FF8C42', '#D95B1E'),
    'star': ('#FFD700', '#E6B800'),
    'berry': ('#E74C3C', '#58B368'),
}


def _heart_path():
    p = QPainterPath(QPointF(8, 14))
    p.cubicTo(2, 9, 0, 6.5, 0, 4.5)
    p.cubicTo(0, 1.8, 2.2, 0, 4.5, 0)
    p.cubicTo(6, 0, 7.3, 0.8, 8, 2.2)
    p.cubicTo(8.7, 0.8, 10, 0, 11.5, 0)
    p.cubicTo(13.8, 0, 16, 1.8, 16, 4.5)
    p.cubicTo(16, 6.5, 14, 9, 8, 14)
    return p


def _spark_path():
    p = QPainterPath(QPointF(9, 0))
    for pt in ((4, 9), (7.5, 9), (5.5, 16), (12, 6), (8, 6), (11, 0)):
        p.lineTo(QPointF(*pt))
    p.closeSubpath()
    return p


def _star_path():
    p = QPainterPath()
    pts = []
    for i in range(10):
        r = 8.0 if i % 2 == 0 else 3.4
        a = math.pi / 2 + i * math.pi / 5
        pts.append((8 - r * math.cos(a), 8 - r * math.sin(a)))
    p.moveTo(QPointF(*pts[0]))
    for pt in pts[1:]:
        p.lineTo(QPointF(*pt))
    p.closeSubpath()
    return p


def _fire_path():
    p = QPainterPath(QPointF(8, 0))
    p.cubicTo(11, 4, 14, 6.5, 14, 10)
    p.cubicTo(14, 13.5, 11.3, 16, 8, 16)
    p.cubicTo(4.7, 16, 2, 13.5, 2, 10)
    p.cubicTo(2, 7.5, 3.6, 6.2, 5, 4.5)
    p.cubicTo(5.8, 6.8, 7, 7.2, 7.4, 5.6)
    p.cubicTo(7.7, 4.2, 7.6, 2, 8, 0)
    return p


def _leaf_path():
    p = QPainterPath(QPointF(8, 0))
    p.cubicTo(13, 3, 14, 9, 8, 16)
    p.cubicTo(2, 9, 3, 3, 8, 0)
    return p


def _berry_path():
    p = QPainterPath(QPointF(8, 16))          # 草莓身体（圆三角）
    p.cubicTo(3, 12, 2, 8, 3.5, 5.5)
    p.cubicTo(5, 3.5, 11, 3.5, 12.5, 5.5)
    p.cubicTo(14, 8, 13, 12, 8, 16)
    return p


_PATHS = {'heart': _heart_path, 'spark': _spark_path, 'star': _star_path,
          'fire': _fire_path, 'leaf': _leaf_path, 'berry': _berry_path}


def _draw_flower(p, x, y, s):
    r = s / 5.0
    p.save()
    p.translate(x, y)
    p.setPen(QPen(QColor(_FX_COLORS['flower'][1]), 1))
    p.setBrush(QColor(_FX_COLORS['flower'][0]))
    for i in range(5):
        a = i * 2 * math.pi / 5
        p.drawEllipse(QRectF(r * math.cos(a) - r, r * math.sin(a) - r,
                             2 * r, 2 * r))
    p.setPen(Qt.NoPen)
    p.setBrush(QColor('#F6D55C'))
    p.drawEllipse(QRectF(-r * 0.8, -r * 0.8, 1.6 * r, 1.6 * r))
    p.restore()


def _draw_zzz(p, x, y, s, color, opacity):
    p.save()
    p.setOpacity(opacity)
    f = QFont('Comic Sans MS', 1)
    f.setBold(True)
    f.setPixelSize(max(8, int(s)))
    p.setFont(f)
    p.setPen(QColor(color))
    p.drawText(QRectF(x - s, y - s, 2 * s, 2 * s),
               Qt.AlignCenter | Qt.AlignVCenter, 'Z')
    p.restore()


def draw_particles(p, particles, dy=0.0):
    """爱心 / Zzz / 特效（宝可梦 trick）——连续淡出的软粒子。"""
    for pr in particles:
        kind = pr.get('kind', 'heart')
        x, y = pr['x'], pr['y'] + dy
        s = float(pr.get('size', 12))
        ratio = 1.0 - pr['age'] / pr['life']
        opacity = max(0.0, min(1.0, ratio * 2.5))
        if opacity <= 0.01:
            continue
        if kind == 'zzz':
            _draw_zzz(p, x, y, s, '#9FB4C7', opacity)
            continue
        shrink = 1.0 - 0.35 * (1.0 - ratio)
        if kind == 'flower':
            _draw_flower(p, x, y, s * shrink)
            continue
        unit = _PATHS.get(kind)
        if unit is None:
            continue
        path = unit()
        p.save()
        p.setOpacity(opacity)
        p.translate(x, y)
        p.scale(s * shrink / 16.0, s * shrink / 16.0)
        p.translate(-8, -8)
        if kind == 'heart':
            color = QColor(C.HEART if ratio > 0.45 else C.HEART_FADED)
            p.setPen(Qt.NoPen)
        else:
            stroke, fill = _FX_COLORS.get(kind, ('#888888', '#CCCCCC'))
            color = QColor(fill)
            p.setPen(QPen(QColor(stroke), 1.4))
        p.setBrush(color)
        p.drawPath(path)
        if kind == 'berry':                 # 草莓加个绿蒂
            p.setBrush(QColor(_FX_COLORS['berry'][1]))
            p.drawEllipse(QRectF(4.5, 1.5, 7, 3.5))
        p.restore()


# ---------------------------------------------------------------------------
# 气泡（真半透明圆角矩形 + 尾巴；返回轮廓 path 供蒙版使用）
# ---------------------------------------------------------------------------
def bubble_font():
    f = QFont('Microsoft YaHei UI', 10)
    return f


_bubble_fm = None


def bubble_metrics():
    """气泡字体度量（缓存），对话区高度估算用。"""
    global _bubble_fm
    if _bubble_fm is None:
        _bubble_fm = QFontMetrics(bubble_font())
    return _bubble_fm


def draw_bubble(p, text, size, area_h):
    """在窗口顶部对话区画气泡。返回气泡整体（含尾巴）的 QPainterPath。"""
    k = size / 160
    f = bubble_font()
    fm = QFontMetrics(f)
    p.setFont(f)
    tail_h = 9 * k
    max_w = 150 * k

    lines, cur = [], ''
    for ch in text:
        if fm.horizontalAdvance(cur + ch) > max_w and cur:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    max_lines = max(1, int((area_h - 8 * k - tail_h) // fm.height()))
    lines = lines[:max_lines] or [text]

    w = min(max(fm.horizontalAdvance(s) for s in lines) + 22 * k,
            max_w + 22 * k)
    h = len(lines) * fm.height() + 10 * k
    x1 = max(min(16 * k, (size - w) / 2), 2)
    y1 = 2 * k
    y2 = min(y1 + h, area_h - tail_h - 2)
    x2 = x1 + w

    r = min(7 * k, w / 4, h / 4)
    path = QPainterPath()
    path.addRoundedRect(QRectF(x1, y1, w, y2 - y1), r, r)
    cx = (x1 + x2) / 2
    tw = 7 * k
    tail = QPainterPath(QPointF(cx - tw, y2 - 1))
    tail.lineTo(QPointF(cx + tw, y2 - 1))
    tail.lineTo(QPointF(cx, y2 + tail_h))
    tail.closeSubpath()
    path = path.united(tail)

    p.setPen(QPen(QColor(C.BUBBLE_EDGE), 2))
    bubble_bg = QColor(C.BUBBLE_BG)
    bubble_bg.setAlpha(216)
    p.setBrush(bubble_bg)
    p.drawPath(path)
    p.setPen(QColor(C.BUBBLE_FG))
    p.drawText(QRectF(x1, y1, w, y2 - y1),
               Qt.AlignCenter | Qt.AlignVCenter, '\n'.join(lines))
    return path


def _flip_h(img):
    """水平镜像（Qt 6.9+ 是 flipped(Qt.Horizontal)，旧版回落 mirrored）。"""
    try:
        return img.flipped(Qt.Horizontal)
    except TypeError:
        return img.mirrored(True, False)


# ---------------------------------------------------------------------------
# 渲染器
# ---------------------------------------------------------------------------
class Renderer:
    """每应用一个实例。advance() 推进播放头，paint() 绘制当前帧，
    body_region() 返回本体命中区域（窗口内宠物区坐标）。"""

    def __init__(self):
        self.char = None
        self.kind = None
        self._pix = {}          # (pid, key, idx, flip) -> QPixmap
        self._img = {}          # (pid, key, idx, flip) -> QImage（蒙版用）
        self._reg = {}          # (pid, key, idx, flip) -> QRegion
        self._atlas_img = {}    # pid -> QImage（hatched 整张图集解码缓存）
        self._head = {}         # 播放头：key -> [idx, remaining_ms]
        self._view = None       # advance() 后的当前绘制信息
        self._pulse_t0 = None   # 落地挤压脉冲
        self._stamps = {}       # pid -> 资产包 mtime（热重载检测）
        self._reload_tick = 0   # 热重载检查降频计数

    # ---- 角色 ----
    @staticmethod
    def supported(char):
        return char.get('kind') in ('anim', 'hatch')

    def set_char(self, char):
        if self.char is not None and char.get('id') == self.char.get('id') \
                and char.get('kind') == self.kind:
            return
        self.char = char
        self.kind = char.get('kind')
        self._head = {}
        self._view = None

    def window_size(self):
        if self.kind == 'anim':
            return anims.window_size(anims.meta(self.char['photo']))
        return hatch_sprites.window_size(self.char['photo'])

    def foot_y(self):
        """脚底线在宠物画布中的 y。"""
        if self.kind == 'anim':
            return anims.foot_y(anims.meta(self.char['photo']))
        return hatch_sprites.window_size(self.char['photo']) - 6

    def pulse(self):
        """落地/着陆时调用：触发一次 squash 挤压脉冲。"""
        self._pulse_t0 = time.monotonic()

    # ---- 状态解析 ----
    def _anim_key(self, state, trick_state):
        pid = self.char['photo']
        meta = anims.meta(pid)
        if state == 'trick' and trick_state:
            return trick_state if anims.has_state(meta, trick_state) else None
        return anims.resolve_state(meta, state)

    def _hatch_row(self, state, facing, trick_row):
        """返回 (行号, 是否定格第 0 帧)——语义与 hatch_sprites.draw_frame
        一致（缺行/睡觉无行时回落 idle 第 0 帧定格）。"""
        meta = hatch_sprites._meta(self.char['photo'])
        available = meta.get('available_rows')
        if state == 'trick' and trick_row is not None:
            return trick_row, False
        row = hatch_sprites._row_for(state, facing)
        if state == 'sleep':
            sr = meta.get('sleep_row')
            if sr is not None and (available is None or sr in available):
                return sr, False
            return 0, True
        if available is not None and row not in available:
            return 0, True
        return row, False

    def _durs(self, key):
        if self.kind == 'anim':
            return anims.durations(
                anims.states_of(anims.meta(self.char['photo']))[key])
        if self.kind == 'hatch':
            row = int(key[3:])
            return hatch_sprites.ROW_SPECS[row][3]
        return None

    # ---- 每帧推进（时长累加器，帧边界与 tick 对齐）----
    def _check_reload(self):
        """资产包热重载：anim.json / 逐帧文件 / 图集 mtime 变了就清缓存，
        旧实例换资产不用重启。逐文件 stat 有开销，每 ~3s 检查一次。"""
        self._reload_tick += 1
        if self._reload_tick % 90 or self.kind not in ('anim', 'hatch'):
            return
        pid = self.char.get('photo')
        if self.kind == 'anim':
            stamp = anims.pack_stamp(pid)
        else:
            try:
                stamp = os.path.getmtime(hatch_sprites._sprite_path(pid))
            except OSError:
                stamp = None
        if stamp == self._stamps.get(pid):
            return
        self._stamps[pid] = stamp
        for cache in (self._img, self._reg):
            for k in [k for k in cache if k[0] == pid]:
                del cache[k]
        self._atlas_img.pop(pid, None)
        self._head = {}
        self._view = None

    def advance(self, state, trick_state, facing, dt_ms):
        self._check_reload()
        if self.kind == 'anim':
            key = self._anim_key(state, trick_state)
            if key is None:
                self._view = None
                return
            entry = anims.states_of(anims.meta(self.char['photo']))[key]
            flip = bool(entry.get('flip_left')) and facing < 0
            self._head.setdefault(key, [0, self._durs(key)[0]])
            head = self._head[key]
            durs = self._durs(key)
            if state == 'sleep' and key == 'idle' \
                    and not anims.has_state(anims.meta(self.char['photo']),
                                            'sleep'):
                head[0], head[1] = 0, 1 << 30      # 无睡姿行：定格 idle 第 0 帧
            else:
                head[1] -= dt_ms
                while head[1] <= 0:
                    head[0] = (head[0] + 1) % len(durs)
                    head[1] += durs[head[0]]
            self._view = {'key': key, 'idx': head[0], 'flip': flip}
        elif self.kind == 'hatch':
            row, freeze = self._hatch_row(state, facing, trick_state)
            key = f'row{row}'
            self._head.setdefault(key, [0, self._durs(key)[0]])
            head = self._head[key]
            durs = self._durs(key)
            if freeze:
                head[0], head[1] = 0, 1 << 30
            else:
                head[1] -= dt_ms
                while head[1] <= 0:
                    head[0] = (head[0] + 1) % len(durs)
                    head[1] += durs[head[0]]
            self._view = {'key': key, 'idx': head[0], 'flip': False,
                          'row': row}

    # ---- 帧图元 ----
    def _anim_image(self, key, idx, flip):
        pid = self.char['photo']
        ck = (pid, key, idx, flip)
        img = self._img.get(ck)
        if img is None:
            name = anims.states_of(anims.meta(pid))[key]['frames'][idx]
            img = QImage(anims.frame_path(pid, name))
            if flip:
                img = _flip_h(img)
            self._img[ck] = img
        return img

    def _hatch_image(self, row, idx, flip):
        pid = self.char['photo']
        ck = (pid, f'row{row}', idx, flip)
        img = self._img.get(ck)
        if img is None:
            atlas = self._atlas_img.get(pid)
            if atlas is None:
                atlas = QImage(hatch_sprites._sprite_path(pid))
                self._atlas_img[pid] = atlas
            cw, ch = hatch_sprites.CELL_W, hatch_sprites.CELL_H
            img = atlas.copy(idx * cw, row * ch, cw, ch)
            if flip:
                img = _flip_h(img)
            self._img[ck] = img
        return img

    def _frame_image(self):
        v = self._view
        if self.kind == 'anim':
            return self._anim_image(v['key'], v['idx'], v['flip'])
        if self.kind == 'hatch':
            return self._hatch_image(v['row'], v['idx'], v['flip'])
        return None

    # ---- 绘制 ----
    def paint(self, p, *, state, t, facing, particles, bubble_extra):
        """在窗口 painter 上画当前帧（宠物区 + 粒子）；气泡由 app 层画。"""
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)

        if self._view is not None:
            img = self._frame_image()
            dy = 0.0
            sx = sy = 1.0
            if state == 'happy':
                dy = -abs(math.sin(t * 7.0)) * 6
            elif state == 'walk':
                dy = -abs(math.sin(t * 9.0)) * 1.5
            elif state in ('idle', 'sleep'):
                sy = 1.0 - _BREATH_AMP * abs(math.sin(t * 2.0))
            pulse = False
            if self._pulse_t0 is not None:
                age = time.monotonic() - self._pulse_t0
                if age < _PULSE_T:
                    k = math.exp(-age * 8.0)
                    sx *= 1.0 + 0.10 * k
                    sy *= 1.0 - 0.12 * k
                    pulse = True
                else:
                    self._pulse_t0 = None

            p.save()
            p.translate(0, bubble_extra + dy)
            # 注意：镜像已烘焙进 _frame_image()（与蒙版同源），这里**不能**
            # 再叠加 QTransform 镜像——双重镜像会让显示内容与蒙版左右
            # 错位，走路时精灵超出蒙版的部分被裁掉（2026-09-25 实测）。
            if sx != 1.0 or sy != 1.0:
                p.translate(0, self.foot_y())
                p.scale(sx, sy)
                p.translate(0, -self.foot_y())
            p.drawImage(0, 0, img)
            p.restore()
            # 蒙版跟随：位移与挤压幅度记入 view（body_region 用）
            self._view['dy'] = dy
            self._view['pulse'] = pulse

        draw_particles(p, particles)

    # ---- 命中区域（宠物区坐标，y 从 0 到 window）----
    def body_region(self):
        if self._view is None:
            return None
        ck = (self.char['photo'], self._view['key'], self._view['idx'],
              self._view['flip'])
        reg = self._reg.get(ck)
        if reg is None:
            reg = region_from_image(self._frame_image())
            self._reg[ck] = reg
        dy = int(self._view.get('dy', 0))
        if dy:
            reg = reg.translated(0, dy)
        if self._view.get('pulse'):
            # squash 横向放大 ~10%：蒙版两侧扩 6px 防止挤压期间被裁边
            reg = reg.united(reg.translated(6, 0)).united(
                reg.translated(-6, 0))
        return reg
