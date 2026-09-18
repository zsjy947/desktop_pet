# -*- coding: utf-8 -*-
"""角色注册表：内置预设 + 自定义图片角色 + hatch-pet 图集包的唯一合并点。

合并规则（原 PetApp._registry）：图集与已有角色同 id 时视为**图片替换**
——渲染走图集（kind=hatch），名字与台词沿用旧 preset（人设不丢）。
"""
from . import characters
from . import custom
from . import hatch_sprites


def full_registry():
    """完整角色表 {id: preset}，每次调用现扫（新角色即时可见）。"""
    reg = custom.registry()
    for pid, preset in hatch_sprites.registry().items():
        old = reg.get(pid)
        if old:
            merged = dict(preset)
            merged['name'] = old.get('name') or preset['name']
            if old.get('phrases'):
                merged['phrases'] = old['phrases']
            reg[pid] = merged
        else:
            reg[pid] = preset
    return reg
