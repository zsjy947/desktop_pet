# -*- coding: utf-8 -*-
"""用户偏好与跨实例信号：上次选择的角色、退出标志文件。

均为用户目录下的小 JSON/标志文件，不属于项目仓库。
"""
import json
import os
import time

_PREF_FILE = os.path.join(os.path.expanduser('~'), '.desktop_pet.json')
# 第二实例用 --quit 请求正在运行的实例退出（单实例锁见 windowing）
QUIT_FLAG = os.path.join(os.path.expanduser('~'), '.desktop_pet.quit')
QUIT_TTL = 120   # 秒：退出标志的有效期，超时视为陈旧（写端崩溃残留）


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
    """写退出标志（内容为 epoch 秒，读端据此判新鲜）。返回是否写入成功。"""
    try:
        with open(QUIT_FLAG, 'w', encoding='utf-8') as f:
            f.write(str(int(time.time())))
        return True
    except OSError:
        return False


def quit_pending():
    """检查并清除退出标志（运行中实例每两秒轮询一次）。

    内容是写端的 epoch 秒：超过 QUIT_TTL 秒视为陈旧（写端崩溃残留或
    内容损坏）——同样删除，但不触发退出。"""
    try:
        with open(QUIT_FLAG, encoding='utf-8') as f:
            raw = f.read().strip()
        os.remove(QUIT_FLAG)
    except OSError:
        return False
    try:
        return time.time() - float(raw) <= QUIT_TTL
    except ValueError:
        return False               # 内容非数字：按陈旧处理
