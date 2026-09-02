# -*- coding: utf-8 -*-
"""行为状态机：管理宠物的状态切换与朝向。

状态流转：
    idle --(随机)--> walk --> idle
    idle/walk --(菜单/深夜)--> sleep --(点击/菜单)--> idle
    任意 --(按下拖拽)--> drag --(松手且悬空)--> fall --(落地)--> idle
    idle/walk --(喂食/摸头)--> happy --> idle
"""
import random
import time

from . import config as C


class Behavior:
    def __init__(self):
        self.state = 'idle'
        self.facing = -1
        now = time.monotonic()
        self.state_until = now + random.uniform(3.0, 8.0)
        # 深夜启动时先打个盹
        hour = time.localtime().tm_hour
        if C.NAP_HOUR_START <= hour or hour < C.NAP_HOUR_END:
            self.sleep()

    # ---------- 查询 ----------
    @property
    def moving(self):
        return self.state == 'walk'

    # ---------- 每帧推进 ----------
    def update(self):
        """推进状态机：happy 到期回落 idle；空闲/走路按计时器随机切换。"""
        if self.state == 'happy' and time.monotonic() >= self.state_until:
            self._idle()
        if self.state in ('idle', 'walk') and time.monotonic() >= self.state_until:
            if self.state == 'idle' and random.random() < 0.65:
                self._walk()
            else:
                self._idle()
            return True
        return False

    # ---------- 状态切换 ----------
    def _idle(self):
        self.state = 'idle'
        self.state_until = time.monotonic() + random.uniform(3.0, 9.0)

    def _walk(self):
        self.state = 'walk'
        self.facing = random.choice((-1, 1))
        self.state_until = time.monotonic() + random.uniform(3.0, 7.0)

    def sleep(self):
        self.state = 'sleep'

    def wake(self):
        if self.state == 'sleep':
            self._idle()

    def happy(self):
        self.state = 'happy'
        self.state_until = time.monotonic() + 2.2

    def start_drag(self):
        self.state = 'drag'

    def fall(self):
        self.state = 'fall'

    def release_drag(self, on_ground):
        if on_ground:
            self._idle()
        else:
            self.fall()

    def land(self):
        """落地（含反弹），返回是否还需要继续反弹。"""
        # 由窗口层根据反弹速度决定继续 fall 还是结束
        self._idle()

    def turn_around(self):
        self.facing *= -1
