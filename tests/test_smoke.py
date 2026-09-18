# -*- coding: utf-8 -*-
"""冒烟测试：验证启动渲染、拖拽落地、摸头、菜单动作、角色切换与状态机流转。

运行：python -m unittest tests.test_smoke -v
（会短暂弹出一个测试窗口，属正常现象。）
"""
import json
import sys
import tempfile
import time
import unittest
from unittest import mock

from pet import characters
from pet import pet_window
from pet.pet_window import PetApp


class SmokeTest(unittest.TestCase):
    def setUp(self):
        # 偏好/退出标志文件指向临时目录，避免测试污染用户主目录
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        import os
        from pet import prefs
        patcher = mock.patch.object(prefs, '_PREF_FILE',
                                    os.path.join(tmp.name, 'pet_pref.json'))
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = mock.patch.object(prefs, 'QUIT_FLAG',
                                    os.path.join(tmp.name, 'pet_quit.flag'))
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

        # 地面（窗口顶边）使窗口底边=脚底正好贴住所属显示器工作区底边，
        # 且不越过显示器底边（回归：气泡对话区加高后脚底曾被顶出屏幕外）
        app = self.app
        m = screens.at(app.monitors, app.x + app.size / 2,
                       app.y + app.size / 2) or screens.primary(app.monitors)
        self.assertEqual(app.ground_y + app.size + app._bubble_extra,
                         m.wy + m.wh)
        self.assertLessEqual(m.wy + m.wh, m.y + m.h)
        self.assertLessEqual(app.y + app.size + app._bubble_extra, m.y + m.h)
        self.assertGreaterEqual(app.ground_y, v.y)
        self.assertGreaterEqual(app.min_x, v.x)
        self.assertLessEqual(app.max_x, v.x + v.w)

    def test_monitor_work_area_fallback(self):
        """工作区信息缺失时视同整屏（回落为旧的整屏落地行为）。"""
        from pet import screens
        m = screens.Monitor(10, 20, 300, 200)
        self.assertEqual((m.wx, m.wy, m.ww, m.wh), (10, 20, 300, 200))
        m2 = screens.Monitor(0, 0, 1920, 1080, 0, 0, 1920, 1030)
        self.assertEqual(m2.wy + m2.wh, 1030)

    def test_drop_below_ground_snaps_back(self):
        """拖到地面以下（如任务栏区域）松手：贴回地面站好，不留在屏幕外。"""
        app = self.app
        app.behavior.start_drag()
        app.y = app.ground_y + 30
        app._on_release(None)
        self.assertEqual(app.behavior.state, 'idle')
        self.assertEqual(app.y, app.ground_y)

    def test_characters_library(self):
        """角色库：橘猫 + 图集少女（人物线分支）；台词类别齐全。

        分支无关：宝可梦分支 characters.py 只有橘猫（GIRLS 为空），
        人物断言仅在有人物预设时要求全集。
        """
        self.assertEqual(characters.CAT['kind'], 'cat')
        girls = [p for p in characters.CHARACTERS.values() if p['kind'] == 'girl']
        expected = {'nino', 'lillie', 'dawn', 'cynthia', 'lusamine'}
        self.assertTrue({p['id'] for p in girls} <= expected)
        if girls:                        # 人物线分支：5 个少女应齐全
            self.assertEqual({p['id'] for p in girls}, expected)
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
        # 分支无关：优先 nino（人物线），否则任一非橘猫角色（宝可梦线）
        other = ('nino' if 'nino' in app.registry
                 else next(pid for pid, p in app.registry.items()
                           if pid != 'cat'))
        other_name = app.registry[other]['name']
        app._char_var.set(other)
        app._switch_character()
        self.assertEqual(app.char['id'], other)
        self.assertEqual(app.char['name'], other_name)
        self.assertIsNot(app.char['phrases']['talk'],
                         characters.CAT['phrases']['talk'])
        self.pump(2)
        self.assertTrue(app.bubble_text)
        self.assertIn(app.bubble_text, app.char['phrases']['switch'])

        # 偏好已写入临时文件，重新初始化时应恢复该角色
        self.assertEqual(pet_window.load_pref(), other)
        self.assertEqual(app.registry[pet_window.load_pref()]['name'],
                         other_name)

        # 切回橘猫
        app._char_var.set('cat')
        app._switch_character()
        self.assertEqual(app.char['id'], 'cat')
        self.assertIsNotNone(old_name)

    def test_menu_origin_above_pet(self):
        """菜单弹出位置：底边压住对话区并微盖宠物头顶（15% 边长），
        且夹回屏幕内。"""
        from pet import screens
        m = screens.Monitor(0, 0, 1920, 1080)
        pet_x, window_top, size = 500, 760, 240
        n_items, n_seps = 18, 2
        bubble_h = 74
        x, y = pet_window.menu_origin(pet_x, window_top, size, m,
                                      n_items, n_seps, bubble_h)
        est = (n_items * pet_window._MENU_ITEM_H
               + n_seps * pet_window._MENU_SEP_H + pet_window._MENU_PAD)
        self.assertEqual(y + est,
                         window_top + bubble_h + int(size * 0.15),
                         '菜单底边应压住对话区并微盖宠物头顶')
        self.assertGreaterEqual(x, m.x)
        self.assertLessEqual(x, m.x + m.w - 150)
        # 窗口已经很靠上时，菜单最多贴住屏幕顶边
        _, y2 = pet_window.menu_origin(500, 10, size, m, n_items, n_seps,
                                       bubble_h)
        self.assertGreaterEqual(y2, m.y + 2)

    def test_bubble_drawn_in_dedicated_area(self):
        """气泡画在窗口顶部的对话区画布，不进入宠物画布。"""
        app = self.app
        self.assertGreater(app._bubble_extra, 0)
        self.assertEqual(int(app.cv_bubble['height']), app._bubble_extra)
        self.assertEqual(int(app.cv['height']), app.size)
        app._chat()
        self.pump_until(lambda: app.cv_bubble.find('all'), timeout=2)
        self.assertTrue(app.bubble_text)
        self.assertTrue(app.cv_bubble.find('all'),
                        '对话区画布上应有气泡')
        app.talk_until = time.monotonic() - 0.1
        self.pump_until(lambda: not app.cv_bubble.find('all'), timeout=2)
        self.assertFalse(app.bubble_text)
        self.assertFalse(app.cv_bubble.find('all'),
                         '气泡到期后应清空对话区画布')

    def test_photo_sprite_switch_and_render(self):
        """图片精灵角色：切换后窗口变大、播帧渲染正常，切回后恢复。"""
        from pet import photo_sprites
        app = self.app
        # 挑一个未被 hatch 图集替换的照片角色（同 id 图集会覆盖照片精灵）
        pid = next((p['photo'] for p in app._registry().values()
                    if p['kind'] == 'girl' and p.get('photo')
                    and photo_sprites.has_assets(p['photo'])), None)
        if not pid:
            self.skipTest('没有未被图集替换的照片角色（全部已升级为图集）')

        self.assertEqual(photo_sprites.window_size(pid), 240)
        app._char_var.set(pid)
        app._switch_character()
        self.pump(4)
        self.assertEqual(app.size, 240)
        self.assertEqual(app.char['kind'], 'girl')   # 照片精灵角色
        self.assertTrue(app.bubble_text)
        self.assertIn(app.bubble_text, app.char['phrases']['switch'])
        app.behavior.wake()          # 深夜启动会自动打盹，先叫醒再验证
        self.pump(2)
        self.assertEqual(app.behavior.state, 'idle')

        # 图片精灵各状态都能渲染
        from pet import girl_sprites  # noqa: F401  确保回落路径可导入
        for state in ('walk', 'sleep', 'happy', 'drag', 'fall'):
            photo_sprites.draw_frame(
                app.cv, char=app.char, state=state, t=0.4, facing=-1,
                bubble_text='测试', particles=[])
        self.pump(2)

        app._char_var.set('cat')
        app._switch_character()
        self.pump(3)
        self.assertEqual(app.size, 160)

    def test_add_character_interface(self):
        """角色添加接口：合成透明底图 → 精灵帧 + 台词注册 → 进入角色表。"""
        import os
        import shutil

        from PIL import Image, ImageDraw
        from pet import custom, photo_sprites
        from tools.add_character import add_character

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        patcher = mock.patch.object(custom, 'CUSTOM_FILE',
                                    os.path.join(tmp.name, 'cc.json'))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(shutil.rmtree, os.path.join('assets', 'zztest'),
                        ignore_errors=True)

        # 合成一张透明底“小人”
        img = Image.new('RGBA', (120, 220), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.ellipse((30, 10, 90, 70), fill=(240, 200, 160, 255))
        d.polygon([(25, 80), (95, 80), (110, 200), (10, 200)],
                  fill=(120, 80, 200, 255))
        img_path = os.path.join(tmp.name, 'figure.png')
        img.save(img_path)

        preset = add_character(img_path, 'zztest', '测试角色',
                               phrases={'talk': ['你好，我是测试角色']})
        self.assertEqual(preset['id'], 'zztest')
        self.assertTrue(os.path.exists(
            os.path.join('assets', 'zztest', 'manifest.json')))

        reg = custom.registry()
        self.assertIn('zztest', reg)
        self.assertEqual(reg['zztest']['name'], '测试角色')
        self.assertEqual(reg['zztest']['phrases']['talk'],
                         ['你好，我是测试角色'])
        self.assertEqual(reg['zztest']['phrases']['feed'],
                         custom.DEFAULT_PHRASES['feed'], '未填类别用兜底台词')
        self.assertTrue(photo_sprites.has_assets('zztest'))
        self.assertEqual(self.app._size_for(reg['zztest']), 240)

    def test_character_upload_server(self):
        """上传网页：GET 表单 + POST multipart 走完整添加流程。"""
        import http.client
        import os
        import shutil
        import threading

        from PIL import Image, ImageDraw
        from pet import custom

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        patcher = mock.patch.object(custom, 'CUSTOM_FILE',
                                    os.path.join(tmp.name, 'cc.json'))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(shutil.rmtree, os.path.join('assets', 'zzsrv'),
                        ignore_errors=True)

        from tools.character_server import Handler
        from http.server import HTTPServer
        server = HTTPServer(('127.0.0.1', 0), Handler)
        th = threading.Thread(target=server.serve_forever, daemon=True)
        th.start()
        self.addCleanup(server.shutdown)

        port = server.server_address[1]
        conn = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
        conn.request('GET', '/')
        body = conn.getresponse().read().decode('utf-8')
        self.assertIn('添加桌面宠物角色', body)

        img = Image.new('RGBA', (100, 200), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.ellipse((20, 10, 80, 60), fill=(200, 180, 160, 255))
        d.rectangle((30, 70, 70, 180), fill=(60, 120, 200, 255))
        import io
        buf = io.BytesIO()
        img.save(buf, 'PNG')

        boundary = 'XBOUND123'
        parts = []
        for name, value in (('id', 'zzsrv'), ('name', '网页角色'),
                            ('model', 'u2net'), ('talk', '网页来的问候'),
                            ('talk', '第二句')):
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; '
                         f'name="{name}"\r\n\r\n{value}\r\n'.encode('utf-8'))
        png = buf.getvalue()
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="image"; '
            f'filename="f.png"\r\nContent-Type: image/png\r\n\r\n'
            .encode('utf-8') + png + b'\r\n')
        payload = b''.join(parts) + f'--{boundary}--\r\n'.encode()
        conn.request('POST', '/add', body=payload, headers={
            'Content-Type': f'multipart/form-data; boundary={boundary}'})
        resp = json.loads(conn.getresponse().read().decode('utf-8'))
        self.assertTrue(resp['ok'], resp)
        self.assertEqual(resp['id'], 'zzsrv')
        reg = custom.registry()
        self.assertEqual(reg['zzsrv']['name'], '网页角色')
        self.assertEqual(reg['zzsrv']['phrases']['talk'],
                         ['网页来的问候', '第二句'])

    def test_hatch_sprites_synthetic(self):
        """hatch-pet 图集桌宠：合成图集包 → 角色表/窗口尺寸/各状态渲染。"""
        import os
        import shutil

        from PIL import Image, ImageDraw
        from pet import hatch_sprites

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        patcher = mock.patch.object(hatch_sprites, 'HATCH_DIR', tmp.name)
        patcher.start()
        self.addCleanup(patcher.stop)
        for cache in (hatch_sprites._metad, hatch_sprites._atlas_cache,
                      hatch_sprites._cell_cache):
            cache.clear()
            self.addCleanup(cache.clear)

        # 合成图集：第 0/1/2/7 行有内容，其余行保持全透明
        atlas = Image.new('RGBA', (hatch_sprites.ATLAS_W, hatch_sprites.ATLAS_H),
                          (0, 0, 0, 0))
        d = ImageDraw.Draw(atlas)
        for row, n in ((0, 6), (1, 8), (2, 8), (7, 6)):
            for col in range(n):
                x0, y0 = col * hatch_sprites.CELL_W, row * hatch_sprites.CELL_H
                d.ellipse((x0 + 40, y0 + 40, x0 + 150, y0 + 202),
                          fill=(240, 160, 60, 255))
        os.makedirs(os.path.join(tmp.name, 'zzhatch'))
        atlas.save(os.path.join(tmp.name, 'zzhatch', 'spritesheet.png'))
        with open(os.path.join(tmp.name, 'zzhatch', 'pet.json'), 'w',
                  encoding='utf-8') as f:
            json.dump({'id': 'zzhatch', 'displayName': '图集测试',
                       'description': '测试用', 'spritesheetPath': 'spritesheet.png',
                       'available_rows': [0, 1, 2]}, f)

        pets = hatch_sprites.list_pets()
        self.assertIn('zzhatch', pets)
        self.assertTrue(hatch_sprites.has_assets('zzhatch'))
        self.assertEqual(hatch_sprites.window_size('zzhatch'), 208)
        preset = hatch_sprites.preset(pets['zzhatch'])
        self.assertEqual(preset['kind'], 'hatch')
        self.assertTrue(preset['phrases']['talk'], '缺省台词应有兜底')

        # 进入角色表并切换渲染所有状态（缺行回落 idle）
        app = self.app
        app.registry = app._registry()   # 等价于重开一次右键菜单的刷新
        self.assertIn('zzhatch', app.registry)
        app._char_var.set('zzhatch')
        app._switch_character()
        self.pump(3)
        self.assertEqual(app.size, 208)
        for state in ('idle', 'walk', 'sleep', 'happy', 'drag', 'fall'):
            hatch_sprites.draw_frame(app.cv, char=app.char, state=state,
                                     t=0.4, facing=-1, bubble_text='测试',
                                     particles=[])
            self.pump(1)
        # 宝可梦 trick：指定动作行按行播放；无 trick_row 时回落 idle
        hatch_sprites.draw_frame(app.cv, char=app.char, state='trick',
                                 t=0.2, facing=1, bubble_text='皮卡！',
                                 particles=[], trick_row=7)
        self.pump(1)
        hatch_sprites.draw_frame(app.cv, char=app.char, state='trick',
                                 t=0.2, facing=1, bubble_text='',
                                 particles=[], trick_row=None)
        self.pump(1)
        app._char_var.set('cat')
        app._switch_character()
        self.pump(2)
        self.assertEqual(app.size, 160)

    def test_hatch_pipeline_slots_and_atlas(self):
        """hatch-pet 管线：条带切槽抠底 → 行内合成 → 图集契约校验。"""
        from PIL import Image, ImageDraw
        from tools import hatch_pet as hp

        # 合成一条 4 帧白底条带（4 个红椭圆均分；模拟模型输出的任意布局）
        strip = Image.new('RGB', (800, 400), (255, 255, 255))
        d = ImageDraw.Draw(strip)
        for i in range(4):
            x0 = i * 200
            d.ellipse((x0 + 50, 100, x0 + 150, 360), fill=(200, 80, 40))
        slots = hp.extract_frames(strip, 4)
        self.assertEqual(len(slots), 4)
        for s in slots:
            self.assertIsNotNone(s)
            self.assertLessEqual(s.width, 110, '抠底后应只剩椭圆内容')

        rows = {}
        for _name, row, n, _d in hp.hs.ROW_SPECS:
            rep = [slots[i % 4] for i in range(n)]
            rows[row] = hp.place_row(rep, n)
            self.assertEqual(rows[row][0].size, (192, 208))
        rows[2] = hp.mirror_cells(rows[1])

        atlas = hp.compose_atlas(rows)
        self.assertEqual(atlas.size, (hp.hs.ATLAS_W, hp.hs.ATLAS_H))
        self.assertEqual(hp.validate_atlas(atlas, strict=True), [])

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

    def test_switch_away_from_trick_does_not_crash(self):
        """宝可梦 trick 中切到照片/Canvas 角色：主循环不得崩（trick 行
        只有图集有，_draw_state 需回落 idle，否则 photo_sprites
        KeyError）。分支无关：有人物线时用竹兰照片精灵（最能复现），
        宝可梦线回落橘猫 Canvas。"""
        from pet import photo_sprites

        app = self.app
        app.registry = app._registry()
        trick_id = next((pid for pid, p in app.registry.items()
                         if p.get('tricks')), None)
        if trick_id is None:
            self.skipTest('本分支没有带专属动作的图集角色')
        target = 'cynthia' if 'cynthia' in app.registry else 'cat'
        app._char_var.set(trick_id)
        app._switch_character()
        app.behavior._trick()
        self.assertEqual(app.behavior.state, 'trick')
        app._char_var.set(target)
        app._switch_character()
        self.pump(2)                      # 推主循环：崩溃会在此暴露
        self.assertEqual(app.behavior.state, 'idle')
        if target == 'cynthia':
            self.assertEqual(app.size,
                             photo_sprites.window_size('cynthia'))
        app._char_var.set('cat')
        app._switch_character()
        self.pump(1)

    def test_startup_autostart_cycle(self):
        """开机自启：enable/disable/is_enabled 往返 + VBS 内容标记。"""
        import os
        from pet import startup
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.assertFalse(startup.is_enabled(override_dir=tmp.name))
        path = startup.enable(tmp.name, python=sys.executable,
                              override_dir=tmp.name)
        self.assertTrue(os.path.exists(path))
        self.assertTrue(startup.is_enabled(override_dir=tmp.name))
        with open(path, encoding='utf-8') as f:
            content = f.read()
        self.assertIn(startup.MARKER, content)
        self.assertIn('main.py', content)
        startup.disable(override_dir=tmp.name)
        self.assertFalse(startup.is_enabled(override_dir=tmp.name))

    def test_single_instance_lock(self):
        """单实例互斥锁：二次获取失败，释放后可再获取。"""
        if sys.platform != 'win32':
            self.skipTest('仅 Windows 有互斥锁实现')
        from pet import windowing
        name = 'DesktopPet.TestLock.smoke'
        handle = windowing.acquire_lock(name)
        self.assertIsNotNone(handle)
        try:
            self.assertTrue(windowing.lock_exists(name))
            self.assertIsNone(windowing.acquire_lock(name))
        finally:
            windowing.release_lock(handle)
        self.assertFalse(windowing.lock_exists(name))

    def test_quit_flag_roundtrip(self):
        """退出标志：写入后可被读取一次（读即清除）。"""
        from pet import prefs
        self.assertFalse(prefs.quit_pending())
        self.assertTrue(prefs.write_quit_flag())
        self.assertTrue(prefs.quit_pending())
        self.assertFalse(prefs.quit_pending())

    def test_menu_structure_by_species(self):
        """右键菜单按物种分组：宝可梦有表演动作无聊天，猫科有喂食。"""
        from pet import menu as pet_menu

        def labels_of(m):
            return ' '.join(m.entrycget(i, 'label')
                            for i in range(m.index('end') + 1)
                            if m.type(i) != 'separator')

        app = self.app
        app.registry = app._registry()
        pk = next((p for p, preset in app.registry.items()
                   if preset.get('species') == 'pokemon'), None)
        if pk is None:
            self.skipTest('本分支没有宝可梦角色')

        app._char_var.set(pk)
        app._switch_character()
        m = pet_menu.build(app)
        labels = labels_of(m)
        self.assertIn('表演一个动作', labels)
        self.assertIn('喂个树果', labels)
        self.assertNotIn('聊聊天', labels)
        self.assertIn('切换角色', labels)
        self.assertIn('开机自启', labels)
        self.assertIn('退出', labels)
        m.destroy()

        app._char_var.set('cat')
        app._switch_character()
        m = pet_menu.build(app)
        labels = labels_of(m)
        self.assertIn('喂食', labels)
        self.assertIn('摸摸头', labels)
        self.assertIn('聊聊天', labels)
        self.assertNotIn('表演一个动作', labels)
        m.destroy()

    def test_perform_trick_menu_action(self):
        """✨ 表演一个动作：菜单动作应让宝可梦进入 trick 状态。"""
        app = self.app
        app.registry = app._registry()
        pk = next((p for p, preset in app.registry.items()
                   if preset.get('species') == 'pokemon'), None)
        if pk is None:
            self.skipTest('本分支没有宝可梦角色')
        app._char_var.set(pk)
        app._switch_character()
        self.pump(2)
        app.behavior.wake()      # 深夜自动打盹时先叫醒
        app._perform_trick()
        self.assertEqual(app.behavior.state, 'trick')
        app._char_var.set('cat')
        app._switch_character()

    def test_desired_char_boot_override(self):
        """--char 指定角色：PetApp(desired_char=) 启动即切换。"""
        app = self.app          # 借 setUp 的注册表挑一个非橘猫角色
        other = next((pid for pid in app.registry if pid != 'cat'), None)
        if other is None:
            self.skipTest('本分支只有橘猫')
        app2 = PetApp(desired_char=other)
        self.addCleanup(app2.root.destroy)
        self.assertEqual(app2.char['id'], other)

    def test_renderers_draw_all_kinds(self):
        """渲染分发：各类型角色 × excited/trick 状态都不抛异常。"""
        from pet import renderers
        app = self.app
        app.registry = app._registry()
        cv = app.cv
        cases = [(app.registry['cat'],
                  ('excited', 'trick', 'idle'))]
        for preset in app.registry.values():
            if preset.get('kind') == 'hatch':
                cases.append((preset, ('excited', 'trick')))
        for char, states in cases:
            for state in states:
                renderers.draw(cv, char=char, state=state, t=0.3, facing=1,
                               particles=[], trick_row=7)
                self.pump(1)

    def test_pokemon_trick_state_and_preset(self):
        """宝可梦：trick 随机动作状态 + pet.json tricks 过滤 + 叫声包。"""
        import time as _time
        from pet.behavior import Behavior
        from pet import hatch_sprites

        tricks = [{'name': '电气火花', 'row': 7, 'fx': 'spark',
                   'cry': '皮卡皮卡！', 'duration': 1.6}]
        b = Behavior(tricks=tricks)
        b.wake()          # 深夜时段构造会自动打盹，先唤醒再测随机分支
        b.state_until = _time.monotonic() - 1      # 到期触发随机分支
        with mock.patch('pet.behavior.random.random', return_value=0.0):
            b.update()
        self.assertEqual(b.state, 'trick')
        self.assertEqual(b.current_trick['row'], 7)
        b.state_until = _time.monotonic() - 1
        b.update()
        self.assertEqual(b.state, 'idle')
        self.assertIsNone(b.current_trick)
        self.assertEqual(b.state, 'idle')

        # tricks 过滤：不可用的行（available_rows 之外/越界/非法）被剔除
        meta = {'id': 'zzpk', 'species': 'pokemon', 'available_rows': [0, 7],
                'tricks': [{'name': 'a', 'row': 7},
                           {'name': 'b', 'row': 8},      # 不在 available_rows
                           {'name': 'c', 'row': 99},     # 越界
                           {'name': 'd', 'row': 'x'}]}   # 非法
        kept = hatch_sprites._tricks_of(meta)
        self.assertEqual([t['name'] for t in kept], ['a'])

        # preset 带出 species 与 tricks；phrases 即叫声包
        from pet import custom
        meta2 = {'id': 'zzpk', 'displayName': '皮卡丘', 'species': 'pokemon',
                 'phrases': {'talk': ['皮卡～？']}}
        preset = hatch_sprites.preset(meta2)
        self.assertEqual(preset['species'], 'pokemon')
        self.assertEqual(preset['phrases']['talk'], ['皮卡～？'])
        self.assertEqual(preset['phrases']['feed'],
                         custom.DEFAULT_PHRASES['feed'])


if __name__ == '__main__':
    unittest.main()
