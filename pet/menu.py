# -*- coding: utf-8 -*-
"""右键菜单：按物种分组的交互项 + 角色子菜单 + 设置（开机自启）+ 退出。

结构与位置分离：build(app) 只管组装（物种自适应），menu_origin 只管
弹出位置（底边压住对话区、微盖宠物头顶，估高宁大勿小——估小了菜单
会沉到宠物后面被键色窗口盖住）。
"""
import tkinter as tk

from . import startup

# 菜单高度估算（实测 Windows 9pt 菜单项约 22px，含 emoji 留了余量）
MENU_ITEM_H = 26
MENU_SEP_H = 8
MENU_PAD = 10

_SPECIES_EMOJI = {'pokemon': '🐾', 'cat': '🐣'}


def menu_origin(pet_x, window_top_y, size, monitor, n_items, n_seps,
                bubble_h=0):
    """右键菜单弹出位置：菜单底边压住对话区、并微微盖住宠物头顶
    （overlap 取 15% 宠物边长）。monitor 用于把菜单夹回屏幕内。
    返回菜单左上角应出现的位置 (x, y)。"""
    est = n_items * MENU_ITEM_H + n_seps * MENU_SEP_H + MENU_PAD
    x = pet_x + size / 2 - 70
    x = min(max(x, monitor.x + 2), monitor.x + monitor.w - 150)
    bottom = window_top_y + bubble_h + int(size * 0.15)
    y = bottom - est
    y = max(y, monitor.y + 2)     # 屏幕上方放不下时至少贴住顶边
    return int(x), int(y)


def _species_emoji(preset):
    return _SPECIES_EMOJI.get(preset.get('species'),
                              '🧚' if preset.get('kind') == 'girl' else '🐣')


def build(app):
    """组装右键菜单。物种决定交互项：
        猫科    = 🍪喂食 / 🖐摸摸头
        宝可梦  = 👋打招呼 / 🍓喂个树果 / ✨表演一个动作（无聊天）
        人类    = 👋打招呼 / 🎁送个礼物 / 💬聊聊天
    """
    menu = tk.Menu(app.root, tearoff=0)
    b = app.behavior
    if app._is_cat():
        menu.add_command(label='🍪 喂食', command=app._feed)
        menu.add_command(label='🖐 摸摸头', command=app._pet)
    elif app._is_pokemon():
        menu.add_command(label='👋 打个招呼', command=app._greet)
        menu.add_command(label='🍓 喂个树果', command=app._feed_berry)
        menu.add_command(label='✨ 表演一个动作', command=app._perform_trick)
    else:
        menu.add_command(label='👋 打个招呼', command=app._greet)
        menu.add_command(label='🎁 送个礼物', command=app._gift)
    if not app._is_pokemon():          # 宝可梦只有叫声，不聊天
        menu.add_command(label='💬 聊聊天', command=app._chat)
    menu.add_separator()
    sleep_label = '☀ 叫醒' if b.state == 'sleep' else '😴 打个盹'
    menu.add_command(label=sleep_label, command=app._toggle_sleep)

    # 角色子菜单：每次打开现扫注册表（新角色即时可见）
    char_menu = tk.Menu(menu, tearoff=0)
    char_menu.add_radiobutton(label='🐱 橘猫', variable=app._char_var,
                              value='cat', command=app._switch_character)
    char_menu.add_separator()
    for preset in app.registry.values():
        if preset['kind'] not in ('girl', 'hatch'):
            continue
        char_menu.add_radiobutton(
            label=f'{_species_emoji(preset)} {preset["name"]}',
            variable=app._char_var, value=preset['id'],
            command=app._switch_character)
    menu.add_cascade(label='🎭 切换角色', menu=char_menu)

    menu.add_separator()
    menu.add_checkbutton(label='🚀 开机自启', variable=app._autostart_var,
                         command=app._toggle_autostart)
    menu.add_command(label='🚪 退出', command=app.root.destroy)
    return menu
