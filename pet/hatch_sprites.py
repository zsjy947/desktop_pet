# -*- coding: utf-8 -*-
"""hatch-pet 图集播放器：播放 Codex hatch-pet 规格的桌宠图集。

图集由 tools/hatch_pet.py 生成（z-image-turbo 逐行生姿势 + 确定性合成），
或从 Codex 导入（hatched/<id>/pet.json + spritesheet.png）。契约与 OpenAI
Codex hatch-pet skill 一致：

    图集 1536x1872 = 8 列 x 9 行，格 192x208，行序固定：
    0 idle / 1 running-right / 2 running-left / 3 waving / 4 jumping /
    5 failed / 6 waiting / 7 running / 8 review
    每行用不完的格子必须全透明；合成时脚底统一贴到格底（地面着陆点）。

运行时把宠物状态映射到图集行：
    idle→idle  walk→running-right/left（按朝向）  happy→waving
    fall/drag→jumping  sleep→idle 第 0 帧定格（配 Zzz 粒子）
    waiting/running/review 是 Codex 应用专属行，桌宠暂不使用。

pet.json 除 Codex 规定的 id/displayName/description/spritesheetPath 外，
允许附带 window（窗口边长）与 available_rows（可用行号，缺省全可用）。
"""
import json
import math
import os

import tkinter as tk

from .drawutil import draw_bubble, draw_particles

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HATCH_DIR = os.path.join(ROOT, 'hatched')

CELL_W, CELL_H = 192, 208
COLS, N_ROWS = 8, 9
ATLAS_W, ATLAS_H = COLS * CELL_W, N_ROWS * CELL_H


def _durs(n, step, final):
    return [step] * (n - 1) + [final]


# (行名, 行号, 帧数, 每帧时长 ms)——时长取自 hatch-pet 的 animation-rows 规范
ROW_SPECS = [
    ('idle', 0, 6, [280, 110, 110, 140, 140, 320]),
    ('running-right', 1, 8, _durs(8, 120, 220)),
    ('running-left', 2, 8, _durs(8, 120, 220)),
    ('waving', 3, 4, _durs(4, 140, 280)),
    ('jumping', 4, 5, _durs(5, 140, 280)),
    ('failed', 5, 8, _durs(8, 140, 240)),
    ('waiting', 6, 6, _durs(6, 150, 260)),
    ('running', 7, 6, _durs(6, 120, 220)),
    ('review', 8, 6, _durs(6, 150, 280)),
]
FRAME_COUNT = {row: n for _name, row, n, _d in ROW_SPECS}

_metad = {}          # pid -> pet.json 内容
_atlas_cache = {}    # pid -> (mtime, PhotoImage)
_cell_cache = {}     # (pid, row, col) -> PhotoImage


def _meta(pid):
    if pid not in _metad:
        with open(os.path.join(HATCH_DIR, pid, 'pet.json'),
                  encoding='utf-8') as f:
            _metad[pid] = json.load(f)
    return _metad[pid]


def list_pets():
    """扫描 hatched/ 下所有桌宠包，返回 {id: pet.json 内容}。"""
    out = {}
    try:
        names = sorted(os.listdir(HATCH_DIR))
    except OSError:
        return out
    for pid in names:
        path = os.path.join(HATCH_DIR, pid, 'pet.json')
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding='utf-8') as f:
                meta = json.load(f)
            out[meta.get('id') or pid] = meta
        except Exception:
            pass
    return out


def _sprite_path(pid):
    name = _meta(pid).get('spritesheetPath') or 'spritesheet.png'
    if name.lower().endswith('.webp'):
        # tkinter 不支持 webp：构建管线总是另存一份同名 png
        png = name[:-5] + '.png'
        if os.path.exists(os.path.join(HATCH_DIR, pid, png)):
            name = png
    return os.path.join(HATCH_DIR, pid, name)


def has_assets(pid):
    try:
        return os.path.exists(_sprite_path(pid))
    except Exception:
        return False


def window_size(pid):
    """桌宠窗口边长：格子高 208，窗口取正方形把格子横向居中。"""
    return int(_meta(pid).get('window', CELL_H))


def preset(meta):
    """把 pet.json 包装成角色表条目（缺省台词用通用兜底）。"""
    from .custom import DEFAULT_PHRASES, PHRASE_KEYS
    phrases = dict(DEFAULT_PHRASES)
    for k in PHRASE_KEYS:
        v = (meta.get('phrases') or {}).get(k)
        if isinstance(v, list) and v:
            phrases[k] = [str(s) for s in v if str(s).strip()]
    return {'id': meta['id'],
            'name': str(meta.get('displayName') or meta['id']),
            'kind': 'hatch', 'photo': meta['id'], 'phrases': phrases}


def registry():
    """hatched/ 下的全部可用桌宠角色 {id: 角色条目}。"""
    out = {}
    for pid, meta in list_pets().items():
        if has_assets(pid):
            out[pid] = preset(meta)
    return out


def _row_for(state, facing):
    if state == 'walk':
        return 1 if facing >= 0 else 2
    if state == 'happy':
        return 3
    if state in ('fall', 'drag'):
        return 4
    return 0


def _phase(row, t):
    """按该行每帧时长算出 t 时刻应显示的帧号。"""
    durs = ROW_SPECS[row][3]
    phase = int(t * 1000) % sum(durs)
    acc = 0
    for i, d in enumerate(durs):
        acc += d
        if phase < acc:
            return i
    return 0


def _atlas(cv, pid):
    path = _sprite_path(pid)
    mtime = os.path.getmtime(path)
    hit = _atlas_cache.get(pid)
    if hit and hit[0] == mtime:
        return hit[1]
    ph = tk.PhotoImage(file=path, master=cv)
    _atlas_cache[pid] = (mtime, ph)
    for key in [k for k in _cell_cache if k[0] == pid]:
        del _cell_cache[key]
    return ph


def _cell(cv, pid, row, col):
    key = (pid, row, col)
    ph = _cell_cache.get(key)
    if ph is not None:
        return ph
    atlas = _atlas(cv, pid)
    ph = tk.PhotoImage(master=cv, width=CELL_W, height=CELL_H)
    x1, y1 = col * CELL_W, row * CELL_H
    # Python 3.12 的 PhotoImage.copy() 不带参数，直接走 tk 命令拷区域
    ph.tk.call(ph.name, 'copy', atlas.name, '-from',
               x1, y1, x1 + CELL_W, y1 + CELL_H)
    _cell_cache[key] = ph
    return ph


def draw_frame(cv, *, char, state, t, facing, bubble_text, particles):
    """绘制一帧图集桌宠。参数含义同 photo_sprites.draw_frame。"""
    cv.delete('all')
    pid = char['photo']
    size = window_size(pid)

    available = _meta(pid).get('available_rows')
    row = _row_for(state, facing)
    if state == 'sleep':
        row, idx = 0, 0
    elif available is not None and row not in available:
        row, idx = 0, 0          # 缺行回落 idle
    else:
        idx = _phase(row, t)
    idx %= FRAME_COUNT[row]

    ph = _cell(cv, pid, row, idx)
    dy = 0
    if state == 'happy':                          # 开心跳动
        dy = -abs(math.sin(t * 7.0)) * 6
    elif state == 'walk':                         # 走路上下颠
        dy = -abs(math.sin(t * 9.0)) * 1.5

    cv.create_image(size / 2, size / 2 + dy, image=ph)
    draw_particles(cv, particles)
    if bubble_text:
        draw_bubble(cv, bubble_text, size)
