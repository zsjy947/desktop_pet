# -*- coding: utf-8 -*-
"""自定义角色注册表：管理用户通过接口添加的角色。

registry 数据写在项目根目录 custom_characters.json（不入库），条目格式：
    {"id": "mychar", "name": "我的角色", "photo": "mychar",
     "phrases": {"talk": ["..."], ...}}

外观帧由 tools/add_character.py 生成到 assets/<id>/；运行时按
photo_sprites.has_assets 校验，帧缺失的角色不会进入菜单。
"""
import json
import os
import re

from . import characters as core
from . import photo_sprites

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CUSTOM_FILE = os.path.join(ROOT, 'custom_characters.json')

ID_PATTERN = re.compile(r'^[a-z][a-z0-9_]{0,23}$')
PHRASE_KEYS = ('talk', 'feed', 'pet', 'sleep', 'wake', 'drop', 'switch')

# 新角色未填写的台词类别使用这里的通用兜底
DEFAULT_PHRASES = {
    'talk': ['你好呀，很高兴见到你', '今天有什么新鲜事吗？', '陪你散散步吧'],
    'feed': ['谢谢你喂我，很好吃！', '唔，满足～'],
    'pet': ['好舒服呀，再摸摸', '嘿嘿，最喜欢你了'],
    'sleep': ['晚安，我先睡啦', 'Zzz……'],
    'wake': ['嗯？发生什么了？', '睡得真好呀'],
    'drop': ['呀！安全着陆', '吓我一跳……没事没事'],
    'switch': ['你好呀，我是新来的！'],
}


def load_custom():
    """读取自定义角色列表；文件缺失或损坏时返回空列表。"""
    try:
        with open(CUSTOM_FILE, encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, list):
            return [p for p in data if isinstance(p, dict) and p.get('id')]
    except Exception:
        pass
    return []


def save_custom(presets):
    with open(CUSTOM_FILE, 'w', encoding='utf-8') as f:
        json.dump(presets, f, ensure_ascii=False, indent=1)


def valid_id(char_id):
    return bool(ID_PATTERN.match(char_id or '')) and char_id not in core.CHARACTERS


def normalize(entry):
    """把自定义条目补全为可渲染的预设：缺省台词用通用兜底。"""
    phrases = dict(DEFAULT_PHRASES)
    for k in PHRASE_KEYS:
        v = (entry.get('phrases') or {}).get(k)
        if isinstance(v, list) and v:
            phrases[k] = [str(s) for s in v if str(s).strip()]
    return {
        'id': entry['id'],
        'name': str(entry.get('name') or entry['id']),
        'kind': 'girl',
        'photo': entry.get('photo') or entry['id'],
        'phrases': phrases,
    }


def upsert(entry):
    """新增或覆盖一个自定义角色（按 id），并做基础校验。"""
    char_id = entry.get('id')
    if not valid_id(char_id):
        raise ValueError(f'非法角色 id：{char_id!r}（需小写字母开头，'
                         f'仅含小写字母/数字/下划线，且不与内置角色冲突）')
    presets = [p for p in load_custom() if p.get('id') != char_id]
    presets.append({
        'id': char_id,
        'name': str(entry.get('name') or char_id),
        'photo': entry.get('photo') or char_id,
        'phrases': entry.get('phrases') or {},
    })
    save_custom(presets)


def registry():
    """完整角色表：内置角色 + 帧文件齐全的自定义角色。"""
    merged = dict(core.CHARACTERS)
    for entry in load_custom():
        preset = normalize(entry)
        if photo_sprites.has_assets(preset['photo']):
            merged[preset['id']] = preset
    return merged
