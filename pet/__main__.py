# -*- coding: utf-8 -*-
"""桌宠命令行入口：python -m pet。

    python -m pet                 启动（单实例；重复启动直接退出）
    python -m pet --char pikachu  以指定角色启动
    python -m pet --list          列出可用角色
    python -m pet --quit          请求正在运行的实例退出

main.py 是兼容入口（run.bat 双击用），内部也走这里。
"""
import argparse
import sys


def build_parser():
    p = argparse.ArgumentParser(prog='python -m pet', description='桌面宠物')
    p.add_argument('--char', metavar='ID', help='以指定角色启动（忽略偏好）')
    p.add_argument('--list', action='store_true', help='列出可用角色后退出')
    p.add_argument('--quit', action='store_true',
                   help='请求正在运行的实例退出')
    return p


def main(argv=None):
    from . import prefs
    from . import windowing

    args = build_parser().parse_args(argv)

    if args.list:
        from . import registry
        for pid, preset in registry.full_registry().items():
            print(f'{pid}\t{preset["name"]}')
        return 0

    if args.quit:
        if windowing.lock_exists():
            ok = prefs.write_quit_flag()
            print('已请求运行中的桌宠退出' if ok else '写退出标志失败')
        else:
            print('桌宠未在运行')
        return 0

    windowing.enable_dpi_awareness()
    lock = windowing.acquire_lock()
    if lock is None:
        print('桌宠已在运行（可用 python -m pet --quit 退出）')
        return 0

    from .app import PetApp
    app = PetApp(desired_char=args.char)
    try:
        app.run()
    finally:
        windowing.release_lock(lock)
    return 0


if __name__ == '__main__':
    sys.exit(main())
