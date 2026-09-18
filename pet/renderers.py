# -*- coding: utf-8 -*-
"""渲染器分发：按角色类型选择绘制后端，统一状态归一化。

四套绘制后端的差异在这里抹平（app 只管传当前状态）：
    sprites        Canvas 程序化橘猫（无 char，自身签名不带 char）
    girl_sprites   Canvas 参数化少女
    photo_sprites  照片帧精灵（assets/）
    hatch_sprites  图集桌宠（hatched/，唯一支持 excited 跳跃行与
                   trick 专属动作行）

状态归一化（_normalize）：
    excited（开心跳）→ 非图集回落 happy（图集原生播跳跃行）；
    trick（宝可梦专属动作）→ 非图集回落 idle——透传会让照片精灵在
    manifest 里查不到 'trick' 行直接 KeyError，主循环崩掉（角色消失、
    气泡永不消失，2026-09-13 实测）。
"""
from . import girl_sprites
from . import hatch_sprites
from . import photo_sprites
from . import sprites


def _normalize(state, char):
    kind = char.get('kind')
    if kind == 'hatch':
        return state              # 图集原生支持全部状态
    if state == 'excited':
        return 'happy'
    if state == 'trick':
        return 'idle'
    return state


def draws_bubble(char):
    """该角色的后端是否负责画气泡（图集类由对话区画布统一画，不画）。"""
    return char.get('kind') not in ('hatch',)


def draw(cv, *, char, state, t, facing, particles, trick_row=None):
    """画一帧。trick_row 仅在 state='trick' 且角色为图集时生效。"""
    kind = char.get('kind')
    use_photo = (kind == 'girl' and bool(char.get('photo'))
                 and photo_sprites.has_assets(char['photo']))
    if kind == 'cat':
        sprites.draw_frame(cv, state=_normalize(state, char), t=t,
                           facing=facing, bubble_text='',
                           particles=particles)
    elif use_photo:
        photo_sprites.draw_frame(cv, char=char,
                                 state=_normalize(state, char),
                                 t=t, facing=facing, bubble_text='',
                                 particles=particles)
    elif kind == 'hatch' and char.get('photo'):
        hatch_sprites.draw_frame(cv, char=char, state=state, t=t,
                                 facing=facing, bubble_text='',
                                 particles=particles,
                                 trick_row=trick_row)
    else:
        girl_sprites.draw_frame(cv, char=char,
                                state=_normalize(state, char),
                                t=t, facing=facing, bubble_text='',
                                particles=particles)
