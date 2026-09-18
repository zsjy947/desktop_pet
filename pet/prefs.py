# -*- coding: utf-8 -*-
"""用户偏好与跨实例信号：上次选择的角色、退出标志文件。

均为用户目录下的小 JSON/标志文件，不属于项目仓库。
"""
import json
import os

_PREF_FILE = os.path.join(os.path.expanduser('~'), '.desktop_pet.json')
# 第二实例用 --quit 请求正在运行的实例退出（单实例锁见 windowing）
QUIT_FLAG = os.path.join(os.path.expanduser('~'), '.desktop_pet.quit')


def load_pref():
    """读取上次选择的角色 id；没有或损坏时返回 None。"""
    try:
        with open(_PREF_FILE, encoding='utf-8') as f:
            return json.load(f).get('char')
    except Exception:
        return None


def save_pref(char_id):
    try:
        with open(_PREF_FILE, 'w', encoding='utf-8') as f:
            json.dump({'char': char_id}, f)
    except Exception:
        pass


def write_quit_flag():
    """写退出标志。返回是否写入成功。"""
    try:
        with open(QUIT_FLAG, 'w', encoding='utf-8') as f:
            f.write('quit')
        return True
    except OSError:
        return False


def quit_pending():
    """检查并清除退出标志（运行中实例每两秒轮询一次）。"""
    try:
        with open(QUIT_FLAG, encoding='utf-8') as f:
            f.read()
        os.remove(QUIT_FLAG)
        return True
    except OSError:
        return False
