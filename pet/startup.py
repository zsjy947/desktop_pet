# -*- coding: utf-8 -*-
"""开机自启：往用户"启动"文件夹写一个隐藏启动的 VBS（零依赖实现）。

enable/disable/is_enabled 的目录都可参数化，便于测试。
"""
import os
import sys

VBS_NAME = 'desktop_pet_autostart.vbs'
MARKER = "' desktop-pet autostart"


def startup_dir(override=None):
    """用户启动文件夹（shell:startup）。测试可注入临时目录。"""
    if override is not None:
        return override
    appdata = os.environ.get('APPDATA')
    if not appdata:
        return None
    return os.path.join(appdata, 'Microsoft', 'Windows',
                        'Start Menu', 'Programs', 'Startup')


def vbs_path(override_dir=None):
    d = startup_dir(override_dir)
    return os.path.join(d, VBS_NAME) if d else None


def pythonw_path(python=None):
    """python.exe 同目录的 pythonw.exe（无控制台）；找不到回落自身。"""
    python = python or sys.executable
    sibling = os.path.join(os.path.dirname(python), 'pythonw.exe')
    return sibling if os.path.exists(sibling) else python


def is_enabled(override_dir=None):
    path = vbs_path(override_dir)
    if not path or not os.path.exists(path):
        return False
    try:
        with open(path, encoding='utf-8') as f:
            return MARKER in f.read()
    except OSError:
        return False


def enable(project_dir, python=None, override_dir=None):
    """写入自启 VBS。返回 VBS 路径；启动文件夹不可用时抛 RuntimeError。"""
    path = vbs_path(override_dir)
    if not path:
        raise RuntimeError('找不到用户启动文件夹（缺 APPDATA）')
    pythonw = pythonw_path(python)
    content = (f'{MARKER}\n'
               f'Set sh = CreateObject("WScript.Shell")\n'
               f'sh.CurrentDirectory = "{project_dir}"\n'
               f'sh.Run """{pythonw}"" main.py", 0, False\n')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    return path


def disable(override_dir=None):
    path = vbs_path(override_dir)
    if path and os.path.exists(path):
        os.remove(path)
    return path
