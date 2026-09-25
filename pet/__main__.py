# -*- coding: utf-8 -*-
"""桌宠命令行入口：python -m pet。

    python -m pet                 启动（单实例；重复启动直接退出）
    python -m pet --char pikachu  以指定角色启动
    python -m pet --list          列出可用角色
    python -m pet --quit          请求正在运行的实例退出
    python -m pet --renderer qt|tk  指定渲染层（缺省 qt，PySide6 缺失回落 tk）

渲染层说明：qt = PySide6 逐像素透明窗口（anims/hatch/cat 全支持）；
tk = 旧键色窗口零依赖兜底（anims 不支持，宝可梦回落 hatched 图集）。

main.py 是兼容入口（run.bat 双击用），内部也走这里。
"""
import argparse
import sys


def qt_available():
    try:
        import PySide6  # noqa: F401
        return True
    except ImportError:
        return False


def build_parser():
    p = argparse.ArgumentParser(prog='python -m pet', description='桌面宠物')
    p.add_argument('--char', metavar='ID', help='以指定角色启动（忽略偏好）')
    p.add_argument('--list', action='store_true', help='列出可用角色后退出')
    p.add_argument('--quit', action='store_true',
                   help='请求正在运行的实例退出')
    p.add_argument('--renderer', choices=('qt', 'tk'), default=None,
                   help='渲染层（缺省 qt，未装 PySide6 时自动回落 tk）')
    return p


def _resolve_renderer(name):
    """缺省 qt（装了 PySide6 就用）；qt 不可用回落 tk。"""
    if name == 'tk':
        return 'tk'
    if qt_available():
        return 'qt'
    print('提示：未安装 PySide6（pip install PySide6），回落 tkinter 渲染层')
    return 'tk'


def _qt_can_run(char_id):
    """目标角色是否支持 Qt 渲染层（anim/hatch/cat）。"""
    from . import qt_render
    from . import registry as registry_mod
    reg = registry_mod.full_registry(include_anims=True)
    char = reg.get(char_id) if char_id else None
    return char is not None and qt_render.Renderer.supported(char)


def main(argv=None):
    from . import prefs
    from . import windowing

    args = build_parser().parse_args(argv)
    renderer = _resolve_renderer(args.renderer)

    if args.list:
        from . import registry
        for pid, preset in registry.full_registry(
                include_anims=(renderer == 'qt')).items():
            print(f'{pid}\t{preset["name"]}')
        return 0

    if args.quit:
        if windowing.lock_exists():
            ok = prefs.write_quit_flag()
            print('已请求运行中的桌宠退出' if ok else '写退出标志失败')
        else:
            print('桌宠未在运行')
        return 0

    char_id = args.char or prefs.load_pref() or 'pikachu'

    if renderer == 'qt':
        if _qt_can_run(char_id):
            # Qt6 自带 per-monitor DPI 感知，不再手动 SetProcessDpiAwareness
            from . import qt_app
            lock = windowing.acquire_lock()
            if lock is None:
                print('桌宠已在运行（可用 python -m pet --quit 退出）')
                return 0
            try:
                return qt_app.main(args.char)
            finally:
                windowing.release_lock(lock)
        print(f'角色 {char_id} 暂不支持 Qt 渲染层，回落 tkinter')

    # tk 渲染层（零依赖兜底）
    windowing.enable_dpi_awareness()
    lock = windowing.acquire_lock()
    if lock is None:
        print('桌宠已在运行（可用 python -m pet --quit 退出）')
        return 0
    from .app import PetApp
    app_tk = PetApp(desired_char=args.char)
    try:
        app_tk.run()
    finally:
        windowing.release_lock(lock)
    return 0


if __name__ == '__main__':
    sys.exit(main())
