# -*- coding: utf-8 -*-
"""精灵构建脚本（开发期工具，运行时不需要）：把 reference/pictures 的参考图
抠图、清理边缘、缩放，并生成各状态的伪姿势帧，供 pet/photo_sprites.py 使用。

用法：
    python tools/build_sprites.py            # 构建全部角色
    python tools/build_sprites.py --only nino lillie
    python tools/build_sprites.py --sheet    # 构建后输出拼图预览 tmp_sheet.png

依赖（仅构建期需要）：pip install pillow "rembg[cpu]"
产物：assets/<id>/manifest.json + 各帧 PNG（运行时零依赖加载）。

关于姿势：每张参考图只有一个姿势，帧由单张抠图做仿射变换伪造——
呼吸/走路=轻微倾斜+上下颠、睡觉=压扁成蹲姿、被拎/下落=纵向拉伸。
真正的多姿势需要生成式 AI 或 Live2D，不在本脚本范围内。
"""
import argparse
import json
import os

from PIL import Image, ImageFilter, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC_DIR = os.path.join(ROOT, 'reference', 'pictures')
OUT_DIR = os.path.join(ROOT, 'assets')

# 输出精灵规格（运行时窗口大小与脚底位置与此一致）
WINDOW = 240
FOOT_MARGIN = 8          # 精灵底边距窗口底边
TARGET_H = 208           # 精灵目标高度
MAX_W = 232              # 精灵最大宽度

# 参考图 -> (角色id, 抠图模型)；动漫插画用 isnet-anime，真人照片用 u2net
CHARACTERS = [
    ('中野二乃.jpg',   'nino',     'isnet-anime'),
    ('莉莉艾.jpg',     'lillie',   'isnet-anime'),
    ('小光.jpg',       'dawn',     'isnet-anime'),
    ('由比滨结衣.jpg', 'yui',      'isnet-anime'),
    ('竹兰.jpg',       'cynthia',  'isnet-anime'),
    ('露莎米奈.jpg',   'lusamine', 'isnet-anime'),
    ('关晓彤.jpg',     'guan',     'u2net'),
    ('戚薇.jpg',       'qiwei',    'u2net'),
    ('毛晓彤.jpg',     'mao',      'u2net'),
    ('王玉雯.jpg',     'wang',     'u2net'),
    ('赵今麦.jpg',     'zhao',     'u2net'),
    ('陈都灵.jpg',     'chen',     'u2net'),
]


def binarize_alpha(img, thresh=128):
    """alpha 二值化：键色透明方案要求像素要么不透明要么全透明，
    半透明像素会先与近黑键色混合再上屏，产生暗边。"""
    a = img.getchannel('A').point(lambda v: 255 if v >= thresh else 0)
    out = img.copy()
    out.putalpha(a)
    return out


def drop_small_islands(img, min_ratio=0.18):
    """只保留大的连通域：参考照片里的台灯、羽毛、悬空伞碎片等
    背景杂物会被 rembg 一起抠出来，按面积比例过滤掉。"""
    import numpy as np
    from collections import deque

    arr = np.array(img)
    mask = arr[..., 3] >= 32
    if not mask.any():
        return img
    h, w = mask.shape
    h4, w4 = h // 4 * 4, w // 4 * 4
    m4 = mask[:h4, :w4].reshape(h4 // 4, 4, w4 // 4, 4).any(axis=(1, 3))
    hh, ww = m4.shape
    labels = np.zeros((hh, ww), dtype=np.int32)
    sizes = {}
    cur = 0
    for sy in range(hh):
        for sx in range(ww):
            if m4[sy, sx] and labels[sy, sx] == 0:
                cur += 1
                labels[sy, sx] = cur
                q = deque([(sy, sx)])
                n = 0
                while q:
                    y, x = q.popleft()
                    n += 1
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = y + dy, x + dx
                        if (0 <= ny < hh and 0 <= nx < ww
                                and m4[ny, nx] and labels[ny, nx] == 0):
                            labels[ny, nx] = cur
                            q.append((ny, nx))
                sizes[cur] = n
    if not sizes:
        return img
    biggest = max(sizes.values())
    keep_labels = {l for l, n in sizes.items() if n >= biggest * min_ratio}
    keep4 = np.isin(labels, list(keep_labels))
    ka = np.repeat(np.repeat(keep4, 4, axis=0), 4, axis=1)
    full = np.zeros((h, w), dtype=bool)
    full[:h4, :w4] = ka
    full[h4:, :] = mask[h4:, :]     # 边缘残余行列按原样保留
    full[:, w4:] = mask[:, w4:]
    arr[~full] = 0                  # 被丢弃的岛 alpha 与 RGB 全部清零
    return Image.fromarray(arr, 'RGBA')


def clean_cutout(img):
    """抠图结果清理：收缩 1px 去掉与背景混合的过渡带，二值化，
    并把外围环带的颜色用核心区颜色外扩填充（rembg 输出的 alpha 是软 matte，
    几乎没有 255 的像素，外围 RGB 混着背景色，直接用会有黑边/背景色晕）。"""
    a = img.getchannel('A')
    keep = a.filter(ImageFilter.MinFilter(3)).point(          # 收缩 1px
        lambda v: 255 if v >= 100 else 0)
    core = a.point(lambda v: 255 if v >= 250 else 0)          # 颜色可信的核心区

    rgb = img.convert('RGB')
    bleed = Image.new('RGB', img.size, (0, 0, 0))
    bleed.paste(rgb, mask=core)                               # 只留核心颜色
    bleed = bleed.filter(ImageFilter.GaussianBlur(3))         # 向外渗色
    rgb_final = Image.composite(rgb, bleed, core)

    out = rgb_final.convert('RGBA')
    keep = keep.filter(ImageFilter.MedianFilter(3))           # 去孤立杂点
    out.putalpha(keep)
    out = binarize_alpha(out)
    bbox = out.getbbox()
    return out.crop(bbox) if bbox else out


def fit_sprite(img):
    """把抠图缩放到窗口内的目标尺寸。"""
    w, h = img.size
    scale = min(TARGET_H / h, MAX_W / w)
    size = (max(1, round(w * scale)), max(1, round(h * scale)))
    return img.resize(size, resample=_lanczos())


def _resample(name):
    return getattr(getattr(Image, 'Resampling', Image), name)


def _lanczos():
    return _resample('LANCZOS')


def transform(sprite, rot=0.0, sx=1.0, sy=1.0, dy=0):
    """以底边中心为锚做缩放/旋转，再合成到窗口画布（dy 向上为负）。"""
    if (sx, sy) != (1.0, 1.0):
        w, h = sprite.size
        sprite = sprite.resize((max(1, round(w * sx)), max(1, round(h * sy))),
                               _resample('BICUBIC'))
    if rot:
        sprite = sprite.rotate(rot, resample=_resample('BICUBIC'), expand=True)
    sprite = binarize_alpha(sprite)      # 变换插值会产生半透明像素，重新二值化
    canvas = Image.new('RGBA', (WINDOW, WINDOW), (0, 0, 0, 0))
    w, h = sprite.size
    canvas.alpha_composite(sprite, ((WINDOW - w) // 2, WINDOW - FOOT_MARGIN - h + dy))
    return canvas


def make_frames(sprite):
    """由单张抠图生成各状态伪姿势帧（朝右），返回 {状态: [帧,...]}。"""
    return {
        'idle': [transform(sprite),
                 transform(sprite, sy=0.985, sx=1.004)],
        'walk': [transform(sprite, rot=-2.6),
                 transform(sprite, dy=-2),
                 transform(sprite, rot=2.6),
                 transform(sprite, dy=-2)],
        'sleep': [transform(sprite, sx=1.14, sy=0.76)],
        'drag': [transform(sprite, sx=0.95, sy=1.07)],
        'fall': [transform(sprite, sx=0.97, sy=1.05, rot=1.5)],
        'happy': [transform(sprite, sx=1.02, sy=0.985),
                  transform(sprite, sx=0.99, sy=1.025)],
    }


def finish_character(cut, char_id, out_dir=OUT_DIR):
    """从清理好的整身抠图（RGBA）生成全部状态帧并保存 manifest。

    供 build_one 与 tools/add_character.py（角色添加接口）复用。"""
    sprite = fit_sprite(cut)

    frames = make_frames(sprite)
    out_dir = os.path.join(out_dir or OUT_DIR, char_id)
    os.makedirs(out_dir, exist_ok=True)
    manifest = {'id': char_id, 'window': WINDOW,
                'foot_margin': FOOT_MARGIN, 'frames': {}}
    for state, imgs in frames.items():
        names = []
        all_imgs = imgs + [im.transpose(Image.FLIP_LEFT_RIGHT) for im in imgs]
        for i, im in enumerate(all_imgs):
            name = f'{state}_{i}.png'
            im.save(os.path.join(out_dir, name))
            names.append(name)
        manifest['frames'][state] = names
    with open(os.path.join(out_dir, 'manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    return sprite, manifest


def build_one(src_path, char_id, model):
    from rembg import new_session, remove
    src = ImageOps.exif_transpose(Image.open(src_path)).convert('RGB')
    session = new_session(model)
    cut = remove(src, session=session)
    cut = drop_small_islands(cut)
    cut = clean_cutout(cut)
    return finish_character(cut, char_id)


def make_sheet(built, path):
    """拼预览图：每行一个角色，依次为 idle 两帧 + walk 前两帧（朝右）。"""
    cols, per = 4, 4
    cell = WINDOW + 8
    rows = (len(built) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * per * cell // 2, rows * cell), (70, 74, 82))
    half = WINDOW // 2
    for i, (char_id, frames) in enumerate(built):
        r, c = divmod(i, cols)
        for j, im in enumerate(frames['idle'] + frames['walk'][:2]):
            small = im.resize((half, half))
            sheet.paste(small, ((c * per + j) * half, r * cell + 4), small)
    sheet.save(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--only', nargs='*', default=None,
                        help='只构建指定角色 id')
    parser.add_argument('--sheet', action='store_true', help='输出拼图预览')
    args = parser.parse_args()

    built = []
    for filename, char_id, model in CHARACTERS:
        if args.only and char_id not in args.only:
            continue
        src_path = os.path.join(SRC_DIR, filename)
        if not os.path.exists(src_path):
            print(f'[skip] 缺少参考图 {filename}', flush=True)
            continue
        print(f'[build] {char_id} <- {filename} ({model})', flush=True)
        sprite, manifest = build_one(src_path, char_id, model)
        print(f'        sprite {sprite.size[0]}x{sprite.size[1]}', flush=True)
        frames = {s: [Image.open(os.path.join(OUT_DIR, char_id, n))
                      for n in names]
                  for s, names in manifest['frames'].items()}
        built.append((char_id, frames))

    if args.sheet and built:
        make_sheet(built, os.path.join(ROOT, 'tmp_sheet.png'))
        print('sheet -> tmp_sheet.png', flush=True)


if __name__ == '__main__':
    main()
