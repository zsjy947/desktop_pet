# -*- coding: utf-8 -*-
"""Win32 窗口层：DPI 感知、置顶压制、单实例互斥锁。

仅 Windows 生效；非 Windows / 调用失败时全部安全降级（返回 None/True）。
"""
import ctypes
import sys

_HWND_TOPMOST = -1
_SWP_NOSIZE = 0x0001
_SWP_NOMOVE = 0x0002
_SWP_NOACTIVATE = 0x0010
_ERROR_ALREADY_EXISTS = 183

LOCK_NAME = 'DesktopPet.SingleInstance'


def enable_dpi_awareness():
    """让进程按物理像素渲染（与截屏/坐标工具约定一致）。"""
    if sys.platform != 'win32':
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass


def get_user32():
    """返回配置好参数类型的 user32；非 Windows 或失败时返回 None。"""
    if sys.platform != 'win32':
        return None
    try:
        import ctypes.wintypes as wt
        user32 = ctypes.windll.user32
        user32.GetParent.argtypes = [wt.HWND]
        user32.GetParent.restype = wt.HWND
        user32.SetWindowPos.argtypes = [wt.HWND, wt.HWND,
                                        ctypes.c_int, ctypes.c_int,
                                        ctypes.c_int, ctypes.c_int, wt.UINT]
        user32.SetWindowPos.restype = wt.BOOL
        return user32
    except Exception:
        return None


def hwnd_of(root, user32):
    """取 tk 根窗口的原生句柄（外层 frame 才是可 SetWindowPos 的窗口）。"""
    if user32 is None:
        return None
    try:
        root.update_idletasks()
        return user32.GetParent(root.winfo_id()) or root.winfo_id()
    except Exception:
        return None


def ensure_topmost(user32, hwnd):
    """把窗口压回最顶层（任务栏也是 topmost，点过后会盖住宠物）。"""
    if user32 is None or hwnd is None:
        return
    try:
        user32.SetWindowPos(hwnd, _HWND_TOPMOST, 0, 0, 0, 0,
                            _SWP_NOSIZE | _SWP_NOMOVE | _SWP_NOACTIVATE)
    except Exception:
        pass


def _kernel32():
    if sys.platform != 'win32':
        return None
    try:
        k32 = ctypes.windll.kernel32
        k32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int,
                                     ctypes.c_wchar_p]
        k32.CreateMutexW.restype = ctypes.c_void_p
        k32.OpenMutexW.argtypes = [ctypes.c_uint, ctypes.c_int,
                                   ctypes.c_wchar_p]
        k32.OpenMutexW.restype = ctypes.c_void_p
        k32.CloseHandle.argtypes = [ctypes.c_void_p]
        return k32
    except Exception:
        return None


def acquire_lock(name=LOCK_NAME):
    """获取单实例互斥锁。返回句柄；已有实例在跑时返回 None。"""
    k32 = _kernel32()
    if k32 is None:
        return 1                        # 非 Windows：不限制
    handle = k32.CreateMutexW(None, 1, name)
    if not handle:
        return 1
    if ctypes.GetLastError() == _ERROR_ALREADY_EXISTS:
        ctypes.windll.kernel32.CloseHandle(handle)
        return None
    return handle


def lock_exists(name=LOCK_NAME):
    """是否已有实例持有锁（--quit 用来判断该不该写退出标志）。"""
    k32 = _kernel32()
    if k32 is None:
        return False
    handle = k32.OpenMutexW(0x00100000, 0, name)   # SYNCHRONIZE
    if handle:
        k32.CloseHandle(handle)
        return True
    return False


def release_lock(handle):
    if handle and handle != 1:
        k32 = _kernel32()
        if k32 is not None:
            k32.CloseHandle(handle)
