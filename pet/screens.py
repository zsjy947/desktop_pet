# -*- coding: utf-8 -*-
"""多显示器支持：枚举显示器与虚拟桌面边界。

Windows 下通过 EnumDisplayMonitors 获取所有显示器的真实坐标
（坐标系受进程 DPI 感知影响，与 tkinter 的窗口坐标一致）；
其他平台或枚举失败时退化为单主屏。
"""
import sys
from collections import namedtuple

# x/y 为左上角坐标，w/h 为宽高
Monitor = namedtuple('Monitor', ['x', 'y', 'w', 'h'])


def get_monitors(fallback_size):
    """返回所有显示器列表；fallback_size=(宽, 高) 用于非 Windows/失败时兜底。"""
    if sys.platform == 'win32':
        try:
            mons = _windows_monitors()
            if mons:
                return mons
        except Exception:
            pass
    return [Monitor(0, 0, fallback_size[0], fallback_size[1])]


def _windows_monitors():
    import ctypes
    import ctypes.wintypes as wt

    user32 = ctypes.windll.user32
    mons = []
    proto = ctypes.WINFUNCTYPE(wt.BOOL, wt.HMONITOR, wt.HDC,
                               ctypes.POINTER(wt.RECT), wt.LPARAM)

    def on_monitor(_hmon, _hdc, rect, _param):
        r = rect.contents
        mons.append(Monitor(r.left, r.top, r.right - r.left, r.bottom - r.top))
        return True

    user32.EnumDisplayMonitors(None, None, proto(on_monitor), 0)
    return mons


def union(monitors):
    """所有显示器的包围盒（虚拟桌面）。"""
    x1 = min(m.x for m in monitors)
    y1 = min(m.y for m in monitors)
    x2 = max(m.x + m.w for m in monitors)
    y2 = max(m.y + m.h for m in monitors)
    return Monitor(x1, y1, x2 - x1, y2 - y1)


def primary(monitors):
    """包含原点 (0, 0) 的显示器视为主屏。"""
    for m in monitors:
        if m.x <= 0 < m.x + m.w and m.y <= 0 < m.y + m.h:
            return m
    return monitors[0]


def at(monitors, px, py):
    """返回包含点 (px, py) 的显示器，没有则 None。"""
    for m in monitors:
        if m.x <= px < m.x + m.w and m.y <= py < m.y + m.h:
            return m
    return None


def at_x(monitors, px):
    """按 x 坐标找显示器；找不到（点在缝隙里）取 x 距离最近的。"""
    for m in monitors:
        if m.x <= px < m.x + m.w:
            return m
    return min(monitors, key=lambda m: min(abs(px - m.x), abs(px - m.x - m.w)))
