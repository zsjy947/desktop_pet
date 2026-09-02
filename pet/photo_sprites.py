# -*- coding: utf-8 -*-
"""图片精灵渲染器：加载 tools/build_sprites.py 预生成的 PNG 帧播放。

运行时不依赖 Pillow/rembg——帧是构建期处理好的：
  - alpha 已二值化（配合键色透明窗口不会出现暗边）
  - 每个状态存 [朝右 x N, 朝左 x N] 两段帧（tkinter 无法运行时翻转）
  - 帧内已含伪姿势变换（倾斜/压扁/拉伸），运行时只做播帧与位移

若 assets 目录缺失（如 fresh clone 未构建），has_assets 返回 False，
主窗口会自动回落到 Canvas 程序化绘制的少女。
"""
import json
import math
import os

import tkinter as tk

from . import config as C
from .drawutil import draw_bubble, draw_particles

ASSET_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         'assets')

# 各状态的播帧速率（帧/秒）
STATE_FPS = {'idle': 1.6, 'walk': 8.0, 'sleep': 0.0, 'drag': 0.0,
             'fall': 0.0, 'happy': 6.0}

_manifests = {}     # id -> manifest dict
_frames = {}        # (id, filename) -> tk.PhotoImage


def _manifest(char_id):
    if char_id not in _manifests:
        path = os.path.join(ASSET_DIR, char_id, 'manifest.json')
        with open(path, encoding='utf-8') as f:
            _manifests[char_id] = json.load(f)
    return _manifests[char_id]


def has_assets(char_id):
    """该角色是否已有预生成的图片精灵。"""
    return os.path.exists(os.path.join(ASSET_DIR, char_id, 'manifest.json'))


def window_size(char_id):
    """精灵的窗口边长（构建时决定，运行时据此调整窗口）。"""
    return int(_manifest(char_id).get('window', C.WINDOW_SIZE))


def _frame(cv, char_id, state, index):
    m = _manifest(char_id)
    names = m['frames'][state]
    name = names[index % len(names)]
    key = (char_id, name)
    ph = _frames.get(key)
    if ph is None:
        path = os.path.join(ASSET_DIR, char_id, name)
        ph = tk.PhotoImage(file=path, master=cv)
        _frames[key] = ph
    return ph


def draw_frame(cv, *, char, state, t, facing, bubble_text, particles):
    """绘制一帧图片精灵。参数含义同 sprites.draw_frame。"""
    cv.delete('all')
    char_id = char['photo']

    m = _manifest(char_id)
    n_half = len(m['frames'][state]) // 2
    base = 0 if facing == 1 else n_half          # 后半段是镜像帧
    fps = STATE_FPS.get(state, 0.0)
    idx = base + (int(t * fps) % n_half if fps else 0)
    ph = _frame(cv, char_id, state, idx)

    dy = 0
    if state == 'happy':                          # 开心跳动
        dy = -abs(math.sin(t * 7.0)) * 6
    elif state == 'walk':                         # 走路上下颠（帧内已有倾斜）
        dy = -abs(math.sin(t * 9.0)) * 1.5

    size = int(m.get('window', C.WINDOW_SIZE))
    cv.create_image(size / 2, size / 2 + dy, image=ph)

    draw_particles(cv, particles)
    if bubble_text:
        draw_bubble(cv, bubble_text, size)
