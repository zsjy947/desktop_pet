# -*- coding: utf-8 -*-
"""桌面宠物 · 兼容启动入口（run.bat 双击用）。

新入口：python -m pet（支持 --char/--list/--quit，见 pet/__main__.py）。
"""
import sys

from pet.__main__ import main


if __name__ == '__main__':
    sys.exit(main())
