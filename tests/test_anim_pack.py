# -*- coding: utf-8 -*-
"""v2 动画资产包（anims/）+ Qt 渲染层单元测试。

覆盖：anims 加载器与状态解析、convert_atlas 图集往返、import_gif 合成
GIF 导入、Qt 渲染器（离屏）：播放头时序 / 镜像 / 蒙版区域 / 橘猫 /
气泡 / 粒子。Qt 部分用 QT_QPA_PLATFORM=offscreen，不弹真窗口。
"""
import os
import sys
import tempfile
import time
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image

from pet import anims, registry as registry_mod


def _make_pack(dest, pid='zzanim', durs=(100, 200)):
    """合成一个最小 v2 资产包：4 帧不对称图案（镜像验证用）。"""
    fdir = os.path.join(dest, pid, 'frames')
    os.makedirs(fdir, exist_ok=True)
    names = []
    for i in range(4):
        im = Image.new('RGBA', (16, 16), (0, 0, 0, 0))
        # 左上角标记块（i 递增右移）+ 中心不透明块
        im.putpixel((2 + i, 2), (255, 0, 0, 255))
        for y in range(6, 10):
            for x in range(6, 10):
                im.putpixel((x, y), (0, 128, 255, 255))
        name = f'idle_{i}.png'
        im.save(os.path.join(fdir, name))
        names.append(name)
    meta = {'id': pid, 'displayName': '合成测试', 'species': 'pokemon',
            'window': 16, 'foot': 12,
            'phrases': {'talk': ['测试叫声']},
            'tricks': [{'name': '动作', 'state': 'trick0', 'fx': 'spark',
                        'cry': '测试！'}],
            'states': {'idle': {'frames': names[:2], 'durations': list(durs)},
                       'walk': {'frames': names[2:], 'durations': [80, 80],
                                'flip_left': True},
                       'happy': {'frames': names[:1], 'durations': [120]},
                       'trick0': {'frames': names[3:], 'durations': [500]}}}
    with open(os.path.join(dest, pid, 'anim.json'), 'w',
              encoding='utf-8') as f:
        json_dump = __import__('json').dump(meta, f, ensure_ascii=False)
    return meta


class AnimLoaderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.meta = _make_pack(self.tmp.name)
        self.patcher = mock.patch.object(anims, 'ANIMS_DIR', self.tmp.name)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        anims._metad.clear()

    def test_list_and_preset(self):
        packs = anims.list_packs()
        self.assertIn('zzanim', packs)
        self.assertTrue(anims.has_assets('zzanim'))
        preset = anims.preset(self.meta)
        self.assertEqual(preset['kind'], 'anim')
        self.assertEqual(preset['species'], 'pokemon')
        self.assertEqual(preset['phrases']['talk'], ['测试叫声'])
        self.assertEqual([t['state'] for t in preset['tricks']], ['trick0'])

    def test_resolve_state_fallbacks(self):
        m = self.meta
        self.assertEqual(anims.resolve_state(m, 'idle'), 'idle')
        self.assertEqual(anims.resolve_state(m, 'excited'), 'happy')
        self.assertEqual(anims.resolve_state(m, 'fall'), 'idle')  # 无 jump
        self.assertEqual(anims.resolve_state(m, 'sleep'), 'idle')
        self.assertEqual(anims.resolve_state(m, 'trick'), 'idle')

    def test_durations_and_loop(self):
        m = self.meta
        self.assertEqual(anims.durations(m['states']['idle']), [100, 200])
        # 缺 durations 时按 fps 均匀
        entry = {'frames': ['a.png', 'b.png'], 'fps': 8}
        self.assertEqual(anims.durations(entry), [125, 125])
        self.assertAlmostEqual(anims.loop_seconds(m, 'trick0'), 0.5)

    def test_registry_overlay(self):
        # tk 路径（include_anims=False）不含 anim 包
        self.assertNotIn('zzanim', registry_mod.full_registry())
        # Qt 路径包含，且 kind=anim
        reg = registry_mod.full_registry(include_anims=True)
        self.assertIn('zzanim', reg)
        self.assertEqual(reg['zzanim']['kind'], 'anim')


class ConvertAtlasTest(unittest.TestCase):
    def test_atlas_roundtrip(self):
        from tools import convert_atlas
        from pet import hatch_sprites

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        # 合成图集：行 0/1/6 各画一格不透明标记（行 2 故意留空）
        atlas = Image.new('RGBA', (hatch_sprites.ATLAS_W, hatch_sprites.ATLAS_H),
                          (0, 0, 0, 0))
        cw, ch = hatch_sprites.CELL_W, hatch_sprites.CELL_H
        for row, col in ((0, 0), (1, 3), (6, 2), (7, 0), (8, 1)):
            im = Image.new('RGBA', (cw, ch), (0, 0, 0, 0))
            for y in range(10, 20):
                for x in range(10, 30):
                    im.putpixel((x, y), (40 + row * 10, col, 99, 255))
            atlas.paste(im, (col * cw, row * ch))
        pid = 'zzconv'
        src = os.path.join(convert_atlas.HATCHED, pid)
        os.makedirs(src, exist_ok=True)
        self.addCleanup(lambda: __import__('shutil').rmtree(src,
                                                            ignore_errors=True))
        atlas.save(os.path.join(src, 'spritesheet.png'))
        with open(os.path.join(src, 'pet.json'), 'w', encoding='utf-8') as f:
            import json
            json.dump({'id': pid, 'displayName': '转换测试',
                       'species': 'pokemon', 'window': 208,
                       'available_rows': [0, 1, 3, 4, 6, 7, 8],
                       'sleep_row': 6,
                       'phrases': {'talk': ['转']},
                       'tricks': [{'name': '动作一', 'row': 7, 'fx': 'spark',
                                   'cry': '一'},
                                  {'name': '动作二', 'row': 8, 'fx': 'leaf',
                                   'cry': '二'}]}, f)

        dest = os.path.join(tmp.name, 'anims')
        meta = convert_atlas.convert(pid, dest=dest)

        # 状态映射：行 0→idle / 1→walk(flip) / 6→sleep / 7,8→trick0,1；
        # 行 2（running-left）丢弃、行 5 failed 不转换
        self.assertEqual(list(meta['states']),
                         ['idle', 'walk', 'sleep', 'trick0', 'trick1'])
        self.assertTrue(meta['states']['walk']['flip_left'])
        self.assertEqual(meta['foot'], 208 - convert_atlas.FOOT_PAD)
        self.assertEqual(meta['tricks'][1]['state'], 'trick1')
        # 时长沿用 ROW_SPECS（idle 行逐帧非均匀）
        self.assertEqual(meta['states']['idle']['durations'],
                         hatch_sprites.ROW_SPECS[0][3])
        # 帧文件：格 192x208 贴进 208x208 画布，像素原样搬运
        frame = Image.open(os.path.join(dest, pid, 'frames',
                                        meta['states']['idle']['frames'][0]))
        self.assertEqual(frame.size, (208, 208))
        # cell(0,0) 的标记块 (10,10) → 画布 (10+8, 10)
        self.assertEqual(frame.getpixel((18, 10)), (40, 0, 99, 255))
        # trick0 来自行 7
        t0 = Image.open(os.path.join(dest, pid, 'frames',
                                     meta['states']['trick0']['frames'][0]))
        self.assertEqual(t0.getpixel((18, 10)), (110, 0, 99, 255))

        # 转换产物能被 anims 加载器读回
        with mock.patch.object(anims, 'ANIMS_DIR', dest):
            anims._metad.clear()
            packs = anims.list_packs()
            self.assertIn(pid, packs)
            preset = anims.preset(packs[pid])
            self.assertEqual(preset['kind'], 'anim')
            self.assertEqual([t['state'] for t in preset['tricks']],
                             ['trick0', 'trick1'])
        anims._metad.clear()


class ImportGifTest(unittest.TestCase):
    def test_gif_roundtrip(self):
        from tools import import_gif as ig

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        gif = os.path.join(tmp.name, 'in.gif')
        frames = [Image.new('RGBA', (40, 40), (0, 0, 0, 0)) for _ in range(5)]
        for i, f in enumerate(frames):
            f.putpixel((i, 5), (255, 255, 0, 255))
            for y in range(20, 36):
                for x in range(12, 28):
                    f.putpixel((x, y), (200, 30, 30, 255))
        frames[0].save(gif, save_all=True, append_images=frames[1:],
                       duration=[50, 50, 60, 70, 80], loop=0, disposal=2)

        dest = os.path.join(tmp.name, 'anims')
        meta = ig.import_gif(gif, 'zzgif', name='GIF 测试', species='pokemon',
                             scale='2', dest=dest)
        self.assertEqual(meta['window'], (80 + 12) // 2 * 2)
        states = meta['states']
        self.assertEqual(len(states['idle']['frames']), 5)
        self.assertEqual(states['idle']['durations'], [50, 50, 60, 70, 80])
        self.assertTrue(states['walk']['flip_left'])
        self.assertEqual(len(states['sleep']['frames']), 1)   # 首帧定格
        # NEAREST 放大 2 倍：帧 80x80 贴进画布，脚底对齐 foot
        frame = Image.open(os.path.join(dest, 'zzgif', 'frames',
                                        states['idle']['frames'][0]))
        self.assertEqual(frame.size, (meta['window'], meta['window']))
        # 脚底线上方（画布下沿附近）应有身体像素，脚底线以下全透明
        foot = meta['foot']
        lower = [1 for y in range(foot - 12, foot)
                 for x in range(meta['window'])
                 if frame.getpixel((x, y))[3] > 0]
        self.assertGreater(sum(lower), 0)
        self.assertTrue(all(frame.getpixel((x, y))[3] == 0
                            for y in range(foot, meta['window'])
                            for x in range(meta['window'])))


class QtRendererTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from PySide6 import QtWidgets  # noqa: F401
        except ImportError:
            raise unittest.SkipTest('未安装 PySide6')
        from PySide6 import QtWidgets
        cls.app = QtWidgets.QApplication.instance() \
            or QtWidgets.QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.meta = _make_pack(self.tmp.name)
        self.patcher = mock.patch.object(anims, 'ANIMS_DIR', self.tmp.name)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        anims._metad.clear()

    def _renderer(self, state='idle'):
        from pet import qt_render
        r = qt_render.Renderer()
        r.set_char({'id': 'zzanim', 'kind': 'anim', 'photo': 'zzanim'})
        r.advance(state, 'trick0' if state == 'trick' else None, 1, 0)
        return r

    def test_region_from_image_orientation(self):
        from PySide6.QtCore import QPoint
        from PySide6.QtGui import QImage
        from pet.qt_render import region_from_image
        img = QImage(16, 16, QImage.Format_ARGB32)
        img.fill(0)
        img.setPixel(8, 8, 0xFF3366AA)      # 仅中心不透明
        reg = region_from_image(img)
        self.assertTrue(reg.contains(QPoint(8, 8)))
        self.assertFalse(reg.contains(QPoint(1, 1)))
        self.assertFalse(reg.contains(QPoint(15, 15)))

    def test_advance_playhead_aligns_with_durations(self):
        r = self._renderer()
        # idle durations [100, 200]：帧边界与累计 dt 严格对齐
        r.advance('idle', None, 1, 99)
        self.assertEqual(r._view['idx'], 0)
        r.advance('idle', None, 1, 1)
        self.assertEqual(r._view['idx'], 1)
        r.advance('idle', None, 1, 200)
        self.assertEqual(r._view['idx'], 0)
        r.advance('idle', None, 1, 210)      # 一次性跨两帧也不丢拍
        self.assertEqual(r._view['idx'], 1)

    def test_trick_and_flip(self):
        r = self._renderer('trick')
        self.assertEqual(r._view['key'], 'trick0')
        r.advance('walk', None, -1, 0)       # 朝左 → flip_left 镜像
        self.assertTrue(r._view['flip'])
        r.advance('walk', None, 1, 0)
        self.assertFalse(r._view['flip'])

    def test_flip_mirrors_pixels(self):
        from PySide6.QtGui import QImage
        r = self._renderer()
        r.advance('walk', None, 1, 0)
        r._frame_image()
        r.advance('walk', None, -1, 0)
        r._frame_image()
        # 合成帧 walk 行（idle_2）标记块在 (4,2)：镜像后应移到 (11,2)
        left = r._img[('zzanim', 'walk', 0, True)]
        right = r._img[('zzanim', 'walk', 0, False)]
        self.assertEqual(right.pixel(4, 2) >> 24 & 0xFF, 255)
        self.assertEqual(left.pixel(11, 2) >> 24 & 0xFF, 255)
        self.assertEqual(right.pixel(11, 2) >> 24 & 0xFF, 0)

    def test_body_region_tracks_offset(self):
        from PySide6.QtCore import QPoint
        from PySide6.QtGui import QPainter, QImage
        import numpy as np
        r = self._renderer('walk')
        img = QImage(64, 64, QImage.Format_ARGB32)
        p = QPainter(img)
        r.paint(p, state='walk', t=0.0, facing=-1, particles=[],
                bubble_extra=8)
        p.end()
        self.assertEqual(r._view['dy'], 0)   # t=0 时 sin=0
        reg = r.body_region()
        self.assertFalse(reg.isEmpty())
        reg_t = reg.translated(0, 8)         # app 层平移到对话区下方
        self.assertFalse(reg_t.isEmpty())

    def test_mask_covers_painted_walk_both_facings(self):
        """回归：走路镜像曾双重翻转（帧图已镜像 + paint 再套 QTransform），
        蒙版与显示错位 → 朝左走时精灵被裁得只剩碎片（38% 像素在蒙版外）。
        断言两个朝向下蒙版都必须覆盖全部绘制像素。"""
        from PySide6.QtCore import QPoint
        from PySide6.QtGui import QPainter, QImage
        import numpy as np
        for facing in (-1, 1):
            r = self._renderer('walk')
            r.advance('walk', None, facing, 0)
            img = QImage(64, 64, QImage.Format_ARGB32_Premultiplied)
            img.fill(0)
            p = QPainter(img)
            r.paint(p, state='walk', t=0.0, facing=facing, particles=[],
                    bubble_extra=0)
            p.end()
            reg = r.body_region()
            a = img.convertToFormat(QImage.Format_ARGB32)
            arr = np.frombuffer(a.constBits(), dtype=np.uint8).reshape(
                a.height(), a.bytesPerLine())
            painted = arr[:, 3::4][:, :a.width()] > 16
            ys, xs = np.nonzero(painted)
            inside = sum(reg.contains(QPoint(x, y))
                         for y, x in zip(ys.tolist(), xs.tolist()))
            self.assertEqual(inside, int(painted.sum()),
                             f'facing={facing} 时蒙版未覆盖全部绘制像素'
                             f'（{inside}/{int(painted.sum())}）')

    def test_cat_paint_and_region(self):
        from PySide6.QtCore import QPoint
        from PySide6.QtGui import QPainter, QImage
        from pet import qt_render
        r = qt_render.Renderer()
        r.set_char({'id': 'cat', 'kind': 'cat'})
        for state in ('idle', 'walk', 'sleep', 'happy', 'fall', 'drag'):
            r.advance(state, None, -1, 0)
            img = QImage(160, 160, QImage.Format_ARGB32_Premultiplied)
            img.fill(0)
            p = QPainter(img)
            r.paint(p, state=state, t=0.3, facing=-1, particles=[],
                    bubble_extra=0)
            p.end()
            reg = r.body_region()
            self.assertFalse(reg.isEmpty(), f'{state} 蒙版不应为空')
            # 中心区（身体）应命中；左上角（猫不画那里）应未命中
            self.assertTrue(reg.contains(QPoint(80, 120)), state)
            self.assertFalse(reg.contains(QPoint(5, 5)), state)

    def test_hatch_kind_paint(self):
        from PySide6.QtCore import QPoint
        from PySide6.QtGui import QPainter, QImage
        from pet import hatch_sprites, qt_render

        # 合成 hatched 包（复用图集契约）
        tmp2 = tempfile.TemporaryDirectory()
        self.addCleanup(tmp2.cleanup)
        atlas = Image.new('RGBA', (hatch_sprites.ATLAS_W,
                                   hatch_sprites.ATLAS_H), (0, 0, 0, 0))
        cw, ch = hatch_sprites.CELL_W, hatch_sprites.CELL_H
        im = Image.new('RGBA', (cw, ch), (0, 0, 0, 0))
        for y in range(20, 180):
            for x in range(40, 150):
                im.putpixel((x, y), (255, 200, 40, 255))
        atlas.paste(im, (0, ch))            # 贴进行 1（walk 行）col 0
        pid = 'zzhatchr'
        os.makedirs(os.path.join(tmp2.name, pid), exist_ok=True)
        atlas.save(os.path.join(tmp2.name, pid, 'spritesheet.png'))
        import json
        with open(os.path.join(tmp2.name, pid, 'pet.json'), 'w',
                  encoding='utf-8') as f:
            json.dump({'id': pid, 'displayName': '图集Qt', 'window': 208,
                       'phrases': {}}, f)
        with mock.patch.object(hatch_sprites, 'HATCH_DIR', tmp2.name):
            hatch_sprites._metad.clear()
            r = qt_render.Renderer()
            r.set_char({'id': pid, 'kind': 'hatch', 'photo': pid})
            r.advance('walk', None, 1, 0)
            self.assertEqual(r._view['row'], 1)
            img = QImage(208, 208, QImage.Format_ARGB32_Premultiplied)
            img.fill(0)
            p = QPainter(img)
            r.paint(p, state='walk', t=0.0, facing=1, particles=[],
                    bubble_extra=10)
            p.end()
            reg = r.body_region()
            self.assertFalse(reg.isEmpty())
            self.assertTrue(reg.contains(QPoint(100, 100)))

    def test_particles_and_bubble_draw(self):
        from PySide6.QtGui import QPainter, QImage
        from pet import qt_render
        for kind in ('heart', 'zzz', 'spark', 'leaf', 'flower', 'fire',
                     'star', 'berry'):
            pr = {'kind': kind, 'x': 20.0, 'y': 20.0, 'age': 0.2,
                  'life': 1.5, 'size': 14}
            img = QImage(64, 64, QImage.Format_ARGB32_Premultiplied)
            img.fill(0)
            p = QPainter(img)
            qt_render.draw_particles(p, [pr])
            p.end()
            self.assertTrue(
                any(img.pixel(x, 20) for x in range(8, 32)),
                f'{kind} 应有像素')
        img = QImage(208, 300, QImage.Format_ARGB32_Premultiplied)
        img.fill(0)
        p = QPainter(img)
        path = qt_render.draw_bubble(p, '你好呀，这是一条测试台词', 208, 92)
        p.end()
        self.assertFalse(path.isEmpty())


if __name__ == '__main__':
    unittest.main()
