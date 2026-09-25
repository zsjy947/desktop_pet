# -*- coding: utf-8 -*-
"""v2 动画资产包（anims/<id>/）加载器：anim.json + frames/*.png。

与 hatched/ 图集（打包成 1536x1872 大图、左右朝向烘焙成两行）不同，
v2 资产是**逐帧 PNG 序列**（软 alpha 保留，供逐像素透明窗口直接绘制），
朝向翻转交给运行时镜像，不再烘焙左右两行。这是为云端生视频抽帧管线
（tools/cloud_hatch.py，下一轮）准备的资产格式；hatched/ 图集可用
tools/convert_atlas.py 一键转成本格式。

anim.json schema：
    {
      "id", "displayName", "description",
      "species",              # pokemon/cat/...（影响菜单分组与交互）
      "window",               # 窗口边长（帧画布为 window x window）
      "foot",                 # 脚底线在画布中的 y（落地/变换锚点）
      "phrases": {...},       # 台词包（键同 custom.PHRASE_KEYS）
      "tricks": [             # 专属随机动作（宝可梦）
        {"name", "state", "fx", "cry"}],   # state 指向 states 的键
      "states": {
        "idle":  {"frames": ["idle_0.png", ...],
                  "durations": [280, ...]},   # ms；缺省用 "fps"（缺省 10fps）
        "walk":  {..., "flip_left": true},    # 朝左时运行时水平镜像
        "sleep": {...}, "happy": {...}, "jump": {...},
        "trick0": {...}, "trick1": {...}
      }
    }

状态解析（resolve_state）：行为层状态 → 资产状态键，缺行回落：
    excited → happy（无则 idle）；fall/drag → jump（无则 idle）；
    sleep 无专门行时由渲染层定格 idle 第 0 帧（沿用图集语义）。
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANIMS_DIR = os.path.join(ROOT, 'anims')

DEFAULT_FPS = 10.0


def list_packs():
    """扫描 anims/ 下所有资产包，返回 {id: anim.json 内容}。"""
    out = {}
    try:
        names = sorted(os.listdir(ANIMS_DIR))
    except OSError:
        return out
    for pid in names:
        meta = _load_pack_meta(pid)
        if meta:
            out[meta.get('id') or pid] = meta
    return out


def _load_pack_meta(pid):
    path = os.path.join(ANIMS_DIR, pid, 'anim.json')
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


_metad = {}      # pid -> anim.json 内容


def meta(pid):
    if pid not in _metad:
        _metad[pid] = _load_pack_meta(pid) or {}
    return _metad[pid]


def has_assets(pid):
    """该 id 是否有可播的 v2 资产包（至少 idle 有帧）。"""
    states = states_of(meta(pid))
    return bool(states.get('idle', {}).get('frames'))


def frames_dir(pid):
    return os.path.join(ANIMS_DIR, pid, 'frames')


def frame_path(pid, name):
    return os.path.join(frames_dir(pid), name)


def states_of(m):
    return m.get('states') or {}


def window_size(m):
    """窗口边长（帧画布边长，正方形）。"""
    return int(m.get('window') or 208)


def foot_y(m):
    """脚底线在画布中的 y：落地、呼吸/挤压变换的锚点。"""
    return int(m.get('foot') or (window_size(m) - 6))


def durations(entry):
    """逐帧时长 ms 列表：durations 字段优先，否则按 fps 均匀。"""
    durs = entry.get('durations')
    if isinstance(durs, list) and len(durs) == len(entry.get('frames') or []):
        return [max(16, int(d)) for d in durs]
    fps = float(entry.get('fps') or DEFAULT_FPS) or DEFAULT_FPS
    n = len(entry.get('frames') or [])
    return [int(round(1000.0 / fps))] * max(n, 1)


def loop_seconds(m, key):
    """一个状态循环播完的秒数（trick 时长基准）。"""
    entry = states_of(m).get(key)
    if not entry:
        return 0.0
    return sum(durations(entry)) / 1000.0


def resolve_state(m, state):
    """行为状态 → 资产状态键（缺行回落规则与图集播放器一致）。"""
    states = states_of(m)
    if state in states:
        return state
    if state == 'excited':
        return 'happy' if 'happy' in states else 'idle'
    if state in ('fall', 'drag'):
        return 'jump' if 'jump' in states else 'idle'
    return 'idle'


def has_state(m, key):
    return key in states_of(m)


def sleep_entry(m):
    """睡觉状态：有 sleep 行则播该行，否则 None（渲染层定格 idle）。"""
    states = states_of(m)
    return states.get('sleep')


def _tricks_of(m):
    """专属随机动作：只保留 states 里真实可播的 state。"""
    out = []
    for t in m.get('tricks') or []:
        if not isinstance(t, dict):
            continue
        state = str(t.get('state') or '')
        if not state or state not in states_of(m):
            continue
        out.append({'name': str(t.get('name') or '动作'),
                    'state': state,
                    'fx': str(t.get('fx') or ''),
                    'cry': str(t.get('cry') or '')})
    return out


def preset(m):
    """把 anim.json 包装成角色表条目（台词缺省用通用兜底）。"""
    from .custom import DEFAULT_PHRASES, PHRASE_KEYS
    phrases = dict(DEFAULT_PHRASES)
    for k in PHRASE_KEYS:
        v = (m.get('phrases') or {}).get(k)
        if isinstance(v, list) and v:
            phrases[k] = [str(s) for s in v if str(s).strip()]
    return {'id': m['id'],
            'name': str(m.get('displayName') or m['id']),
            'kind': 'anim', 'photo': m['id'],
            'species': str(m.get('species') or 'human'),
            'phrases': phrases,
            'tricks': _tricks_of(m)}


def registry():
    """anims/ 下全部可用角色 {id: 角色条目}。"""
    out = {}
    for pid, m in list_packs().items():
        if has_assets(pid):
            out[pid] = preset(m)
    return out
