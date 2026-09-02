# -*- coding: utf-8 -*-
"""冒烟测试：验证启动渲染、拖拽落地、摸头、菜单动作与状态机流转。

运行：python -m unittest tests.test_smoke -v
（会短暂弹出一个测试窗口，属正常现象。）
"""
import time
import unittest

from pet.pet_window import PetApp


class SmokeTest(unittest.TestCase):
    def setUp(self):
        self.app = PetApp()
        self.pump(1)  # 先让窗口完成映射，否则合成的鼠标事件会被丢弃

    def tearDown(self):
        if self.app._after_id is not None:
            self.app.root.after_cancel(self.app._after_id)
        self.app.root.destroy()

    def pump(self, frames=3):
        """处理若干轮事件，让绑定回调与动画 tick 跑起来。"""
        for _ in range(frames):
            self.app.root.update()

    def pump_until(self, cond, timeout=5.0):
        """循环处理事件直到条件满足（让真实时钟推进、after 回调得以触发）。"""
        deadline = time.monotonic() + timeout
        while not cond() and time.monotonic() < deadline:
            self.app.root.update()

    def test_boot_and_first_frames(self):
        self.pump(5)
        self.assertIn(self.app.behavior.state, ('idle', 'walk', 'sleep'))

    def test_drag_and_fall_landing(self):
        cv, app = self.app.cv, self.app
        press_x, press_y = app.x + 80, app.y + 70
        cv.event_generate('<ButtonPress-1>', x=80, y=70,
                          rootx=press_x, rooty=press_y)
        self.pump(2)
        self.assertEqual(app.behavior.state, 'drag')

        # 向上拖 100px
        cv.event_generate('<B1-Motion>', x=80, y=70,
                          rootx=press_x, rooty=press_y - 100)
        self.pump(2)
        self.assertEqual(app.y, app.ground_y - 100)

        # 松手 → 下落 → 落地回 idle
        cv.event_generate('<ButtonRelease-1>', x=80, y=70,
                          rootx=press_x, rooty=app.y + 70)
        self.pump(1)
        self.assertEqual(app.behavior.state, 'fall')

        self.pump_until(lambda: app.behavior.state != 'fall', timeout=10)
        self.assertEqual(app.behavior.state, 'idle')
        self.assertAlmostEqual(app.y, app.ground_y, delta=1)

    def test_double_click_pets_and_spawns_hearts(self):
        cv, app = self.app.cv, self.app
        # 两次快速按下触发 <Double-Button-1> 绑定
        for _ in range(2):
            cv.event_generate('<ButtonPress-1>', x=80, y=70,
                              rootx=app.x + 80, rooty=app.y + 70)
        self.pump(2)
        self.assertEqual(app.behavior.state, 'happy')
        self.assertTrue(app.particles, '摸头后应产生爱心粒子')
        self.assertTrue(app.bubble_text)

        # happy 状态到期后应自动回落 idle，而不是永久卡住
        app.behavior.state_until = time.monotonic() - 0.1
        self.pump_until(lambda: app.behavior.state == 'idle', timeout=3)
        self.assertEqual(app.behavior.state, 'idle')

    def test_menu_actions(self):
        app = self.app
        app._feed()
        self.pump(2)
        self.assertEqual(app.behavior.state, 'happy')

        app._toggle_sleep()
        self.pump(2)
        self.assertEqual(app.behavior.state, 'sleep')
        app._toggle_sleep()
        self.pump(2)
        self.assertNotEqual(app.behavior.state, 'sleep')

        app._chat()
        self.assertTrue(app.bubble_text)

    def test_walk_turns_at_edges(self):
        app = self.app
        app.behavior._walk()
        app.x = app.min_x          # 顶到左边缘
        app.behavior.facing = -1   # 继续往左走
        self.pump_until(lambda: app.behavior.facing == 1, timeout=5)
        self.assertEqual(app.behavior.facing, 1, '撞墙后应掉头')
        self.assertGreaterEqual(app.x, app.min_x)


if __name__ == '__main__':
    unittest.main()
