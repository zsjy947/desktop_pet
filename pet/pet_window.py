# -*- coding: utf-8 -*-
"""兼容 shim：PetApp 的实现已拆到 pet.app 及其子模块。

保留本模块是因为外部驱动脚本（localgen/ui_*.py 等）和旧代码习惯
`from pet.pet_window import PetApp`。新代码请直接 import pet.app。
"""
from .app import PetApp, ROOT                    # noqa: F401
from .menu import (menu_origin,                  # noqa: F401
                   MENU_ITEM_H as _MENU_ITEM_H,
                   MENU_SEP_H as _MENU_SEP_H,
                   MENU_PAD as _MENU_PAD)
from .prefs import _PREF_FILE, load_pref, save_pref            # noqa: F401
from .renderers import _normalize as _draw_state               # noqa: F401

__all__ = ['PetApp', 'ROOT', 'menu_origin', 'load_pref', 'save_pref',
           '_draw_state']
