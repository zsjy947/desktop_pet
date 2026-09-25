# -*- coding: utf-8 -*-
"""右键菜单：按物种分组的交互项 + 角色子菜单 + 设置（开机自启）+ 退出。

结构与位置分离：
    spec()        菜单结构的**后端无关描述**（tk / Qt 两个渲染端共用，
                  物种自适应分组只写在这里一份）
    build()       tk Menu 渲染端（消费 spec，输出与旧版逐项一致）
    menu_origin   弹出位置（底边压住对话区、微盖宠物头顶，估高宁大勿小
                  ——估小了菜单会沉到宠物后面被键色窗口盖住）
Qt 端由 pet/qt_app.py 消费 spec() 构建 QMenu。
"""
import tkinter as tk

from . import startup

# 菜单高度估算（实测 Windows 9pt 菜单项约 22px，含 emoji 留了余量）
MENU_ITEM_H = 26
MENU_SEP_H = 8
MENU_PAD = 10

_SPECIES_EMOJI = {'pokemon': '🐾', 'cat': '🐣'}
_CHAR_KINDS = ('girl', 'hatch', 'anim')


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


def spec(app):
    """菜单结构描述（后端无关）。物种决定交互项：
        猫科    = 🍪喂食 / 🖐摸摸头
        宝可梦  = 👋打招呼 / 🍓喂个树果 / ✨表演一个动作（无聊天）
        人类    = 👋打招呼 / 🎁送个礼物 / 💬聊聊天
    """
    b = app.behavior
    items = []
    if app._is_cat():
        items.append({'type': 'command', 'label': '🍪 喂食', 'cmd': app._feed})
        items.append({'type': 'command', 'label': '🖐 摸摸头',
                      'cmd': app._pet})
    elif app._is_pokemon():
        items.append({'type': 'command', 'label': '👋 打个招呼',
                      'cmd': app._greet})
        items.append({'type': 'command', 'label': '🍓 喂个树果',
                      'cmd': app._feed_berry})
        if app.behavior.tricks:        # Showdown 动画包无 tricks：不显示死项
            items.append({'type': 'command', 'label': '✨ 表演一个动作',
                          'cmd': app._perform_trick})
    else:
        items.append({'type': 'command', 'label': '👋 打个招呼',
                      'cmd': app._greet})
        items.append({'type': 'command', 'label': '🎁 送个礼物',
                      'cmd': app._gift})
    if not app._is_pokemon():          # 宝可梦只有叫声，不聊天
        items.append({'type': 'command', 'label': '💬 聊聊天',
                      'cmd': app._chat})
    items.append({'type': 'sep'})
    items.append({'type': 'command',
                  'label': '☀ 叫醒' if b.state == 'sleep' else '😴 打个盹',
                  'cmd': app._toggle_sleep})

    # 角色子菜单：每次打开现扫注册表（新角色即时可见）
    chars = [{'type': 'radio', 'label': '🐱 橘猫', 'value': 'cat'},
             {'type': 'sep'}]
    for preset in app.registry.values():
        if preset['kind'] not in _CHAR_KINDS:
            continue
        chars.append({'type': 'radio',
                      'label': f'{_species_emoji(preset)} {preset["name"]}',
                      'value': preset['id']})
    items.append({'type': 'cascade', 'label': '🎭 切换角色', 'items': chars})

    items.append({'type': 'sep'})
    items.append({'type': 'check', 'label': '🚀 开机自启'})
    items.append({'type': 'command', 'label': '🚪 退出', 'cmd': app._quit})
    return items


def build(app):
    """tk Menu 渲染端：消费 spec()，输出与旧版 build 逐项一致。"""
    menu = tk.Menu(app.root, tearoff=0)
    for it in spec(app):
        t = it['type']
        if t == 'sep':
            menu.add_separator()
        elif t == 'command':
            menu.add_command(label=it['label'], command=it['cmd'])
        elif t == 'check':
            menu.add_checkbutton(label=it['label'],
                                 variable=app._autostart_var,
                                 command=app._toggle_autostart)
        elif t == 'radio':
            menu.add_radiobutton(label=it['label'],
                                 variable=app._char_var, value=it['value'],
                                 command=app._switch_character)
        elif t == 'cascade':
            sub = tk.Menu(menu, tearoff=0)
            for c in it['items']:
                if c['type'] == 'sep':
                    sub.add_separator()
                elif c['type'] == 'radio':
                    sub.add_radiobutton(label=c['label'],
                                        variable=app._char_var,
                                        value=c['value'],
                                        command=app._switch_character)
            menu.add_cascade(label=it['label'], menu=sub)
    return menu
