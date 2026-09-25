# -*- coding: utf-8 -*-
"""角色注册表：内置预设 + 自定义图片角色 + hatch-pet 图集包的唯一合并点。

合并规则（原 PetApp._registry）：图集与已有角色同 id 时视为**图片替换**
——渲染走图集（kind=hatch），名字与台词沿用旧 preset（人设不丢）。

v2 动画资产（anims/，kind=anim）走同样的"图片替换"合并，且优先级高于
hatched/ 图集（新格式优先，旧图集兜底）。include_anims 默认关闭：tk
渲染层不认识 anim 包，只有 Qt 运行时（qt_app）才开启。
"""
from . import characters
from . import custom
from . import hatch_sprites


def _merge_image_replacement(reg, presets):
    """图片替换合并：同 id 保留旧 name/phrases（人设不丢）。"""
    for pid, preset in presets.items():
        old = reg.get(pid)
        if old:
            merged = dict(preset)
            merged['name'] = old.get('name') or preset['name']
            if old.get('phrases'):
                merged['phrases'] = old['phrases']
            reg[pid] = merged
        else:
            reg[pid] = preset


def full_registry(include_anims=False):
    """完整角色表 {id: preset}，每次调用现扫（新角色即时可见）。"""
    reg = custom.registry()
    _merge_image_replacement(reg, hatch_sprites.registry())
    if include_anims:
        from . import anims
        _merge_image_replacement(reg, anims.registry())
    return reg
