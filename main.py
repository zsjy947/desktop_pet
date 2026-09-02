# -*- coding: utf-8 -*-
"""桌面宠物 · 橘猫 —— 程序入口。

运行：python main.py
仅依赖 Python 标准库（tkinter），无需安装第三方包。
"""
import sys

from pet.pet_window import PetApp


def _enable_windows_dpi_awareness():
    """让窗口按物理像素渲染，避免高分屏下被系统拉伸而模糊。"""
    if sys.platform == 'win32':
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass


def main():
    _enable_windows_dpi_awareness()
    PetApp().run()


if __name__ == '__main__':
    main()
