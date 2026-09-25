# -*- coding: utf-8 -*-
"""Qt 运行时截图冒烟：后台起宠物 → 按窗口标题找 HWND → 截窗口区域。

用法：python tmp_qt_smoke.py <char_id> <输出png> [等待秒]
驱动进程自己 SetProcessDpiAwareness(2)（物理像素），与 Qt PMv2 窗口
的 GetWindowRect 物理坐标对齐。
"""
import ctypes
import ctypes.wintypes as wt
import subprocess
import sys
import time

def main():
    char, out = sys.argv[1], sys.argv[2]
    wait = float(sys.argv[3]) if len(sys.argv) > 3 else 5.0

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass

    proc = subprocess.Popen([sys.executable, '-m', 'pet', '--char', char],
                            cwd='.')
    time.sleep(wait)

    # 按标题前缀枚举窗口（不硬编码角色名）
    hwnd = None
    found = []
    user32 = ctypes.windll.user32
    buf = ctypes.create_unicode_buffer(128)

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def _cb(h, _l):
        nonlocal hwnd
        user32.GetWindowTextW(h, buf, 128)
        if buf.value.startswith('桌面宠物 · '):
            found.append(buf.value)
            if hwnd is None:
                hwnd = h
        return True
    user32.EnumWindows(_cb, 0)
    if not hwnd:
        print('找不到宠物窗口（ EnumWindows 结果：', found or '无', '）')
        proc.terminate()
        return 1
    title = found[0]

    rect = wt.RECT()
    ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
    print(f'窗口「{title}」 rect=({rect.left},{rect.top})-'
          f'({rect.right},{rect.bottom})')

    from PIL import ImageGrab
    img = ImageGrab.grab(bbox=(rect.left, rect.top, rect.right, rect.bottom))
    img.save(out)
    print('已保存', out, img.size)

    subprocess.run([sys.executable, '-m', 'pet', '--quit'])
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.terminate()
    return 0

if __name__ == '__main__':
    sys.exit(main())
