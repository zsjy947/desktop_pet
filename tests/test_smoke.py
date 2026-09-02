# -*- coding: utf-8 -*-
"""冒烟测试：验证启动渲染、拖拽落地、摸头、菜单动作、角色切换与状态机流转。

运行：python -m unittest tests.test_smoke -v
（会短暂弹出一个测试窗口，属正常现象。）
"""
import tempfile
import time
import unittest
from unittest import mock

from pet import characters
from pet import pet_window
from pet.pet_window import PetApp


class SmokeTest(unittest.TestCase):
    def setUp(self):
        # 偏好文件指向临时目录，避免测试污染用户主目录
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        import os
        pref = os.path.join(tmp.name, 'pet_pref.json')
        patcher = mock.patch.object(pet_window, '_PREF_FILE', pref)
        patcher.start()
        self.addCleanup(patcher.stop)

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

    def test_screens_and_ground(self):
        from pet import screens
        mons = screens.get_monitors((1920, 1080))
        self.assertTrue(mons)
        v = screens.union(mons)
        self.assertGreater(v.w, 0)
        self.assertGreater(v.h, 0)
        # 主屏、点定位、按 x 定位都应返回合法显示器
        self.assertIn(screens.primary(mons), mons)
        self.assertIsNotNone(screens.at(mons, v.x + v.w // 2, v.y + v.h // 2))
        self.assertIn(screens.at_x(mons, v.x), mons)

        # 地面应落在虚拟桌面底边之上，窗口初始位置应在虚拟桌面内
        app = self.app
        self.assertLessEqual(app.ground_y, v.y + v.h)
        self.assertGreaterEqual(app.ground_y, v.y)
        self.assertGreaterEqual(app.min_x, v.x)
        self.assertLessEqual(app.max_x, v.x + v.w)

    def test_characters_library(self):
        """角色库：橘猫 + 12 个参考图少女，台词类别齐全。"""
        self.assertEqual(characters.CAT['kind'], 'cat')
        girls = [p for p in characters.CHARACTERS.values() if p['kind'] == 'girl']
        self.assertEqual(len(girls), 12)
        for preset in characters.CHARACTERS.values():
            for key in ('talk', 'feed', 'pet', 'sleep', 'wake', 'drop',
                        'switch'):
                self.assertTrue(preset['phrases'][key],
                                f'{preset["name"]} 缺少台词类别 {key}')
        # 未知 id 回落到橘猫
        self.assertIs(characters.get('nope'), characters.CAT)

    def test_all_characters_render_all_states(self):
        """所有角色 × 所有状态都能画出来，不抛异常。"""
        states = ('idle', 'walk', 'sleep', 'drag', 'fall', 'happy')
        cv = self.app.cv
        for preset in characters.CHARACTERS.values():
            for state in states:
                if preset['kind'] == 'cat':
                    from pet import sprites
                    sprites.draw_frame(cv, state=state, t=0.4, facing=1,
                                       bubble_text='测试气泡',
                                       particles=[])
                else:
                    from pet import girl_sprites
                    girl_sprites.draw_frame(cv, char=preset, state=state,
                                            t=0.4, facing=-1,
                                            bubble_text='测试气泡',
                                            particles=[])
            self.pump(1)

    def test_switch_character_changes_phrases_and_persists(self):
        app = self.app
        old_name = app.char['name']
        app._char_var.set('nino')
        app._switch_character()
        self.assertEqual(app.char['id'], 'nino')
        self.assertEqual(app.char['name'], '中野二乃')
        self.assertIsNot(app.char['phrases']['talk'],
                         characters.CAT['phrases']['talk'])
        self.pump(2)
        self.assertTrue(app.bubble_text)
        self.assertIn(app.bubble_text, app.char['phrases']['switch'])

        # 偏好已写入临时文件，重新初始化时应恢复该角色
        self.assertEqual(pet_window.load_pref(), 'nino')
        self.assertEqual(pet_window.get_character(pet_window.load_pref())['name'],
                         '中野二乃')

        # 切回橘猫
        app._char_var.set('cat')
        app._switch_character()
        self.assertEqual(app.char['id'], 'cat')
        self.assertIsNotNone(old_name)

    def test_menu_origin_above_pet(self):
        """菜单弹出位置：底边贴住宠物头顶上方，且夹回屏幕内。"""
        from pet import screens
        m = screens.Monitor(0, 0, 1920, 1080)
        pet_x, pet_y, size = 500, 920, 160
        n_items, n_seps = 18, 2
        x, y = pet_window.menu_origin(pet_x, pet_y, size, m, n_items, n_seps)
        # 菜单估算高度
        est = n_items * pet_window._MENU_ITEM_H + n_seps * pet_window._MENU_SEP_H
        self.assertLessEqual(y + est, pet_y + 14, '菜单不应压住宠物')
        self.assertGreaterEqual(x, m.x)
        self.assertLessEqual(x, m.x + m.w - 150)
        # 宠物已经很靠上时，菜单最多贴住屏幕顶边
        _, y2 = pet_window.menu_origin(500, 10, size, m, n_items, n_seps)
        self.assertGreaterEqual(y2, m.y + 2)

    def test_behavior_pause_stops_walk(self):
        """右键菜单打开时走路应先站定（真实弹窗交互由人工验证）。"""
        app = self.app
        app.behavior._walk()
        x0 = app.x
        app.behavior.pause()
        self.assertEqual(app.behavior.state, 'idle')
        self.pump(2)
        self.assertEqual(app.x, x0, '暂停后不应再移动')

        # 非 walk 状态时 pause 应无副作用
        app.behavior.happy()
        app.behavior.pause()
        self.assertEqual(app.behavior.state, 'happy')


if __name__ == '__main__':
    unittest.main()
