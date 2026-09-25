# -*- coding: utf-8 -*-
"""GIF → anims/ v2 资产包导入。

用途：把现成的高帧率透明动画（如 Pokémon Showdown 的 ani 精灵
https://play.pokemonshowdown.com/sprites/ani/<name>.gif）转成 v2 资产，
用于验证 Qt 播放器在高帧率（16~25fps）素材下的流畅度上限——这是
免费就能拿到的"动态效果天花板"参照物。

转换规则：
    * 逐帧合成（GIF 帧是增量帧，按 disposal 规则叠到整幅）；
    * 逐帧时长取自 GIF（缺省 80ms），运行时按同节奏播放；
    * NEAREST 整数倍放大（像素风保持锐利，默认放大到高约 160px）；
    * 生成 idle / walk（flip_left=true，运行时镜像）/ happy 三个状态
      共用同一动画；sleep 用首帧定格（单帧）。

用法：
    python tools/import_gif.py --gif pikachu.gif --id pikachu-anime \
        --name 皮卡丘动画版 [--species pokemon] [--scale auto|N]
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image, ImageSequence

from pet import anims

FOOT_PAD = 4      # 脚底离窗口底边的间隙
TARGET_H = 160    # --scale auto 时的目标帧高


def read_frames(gif_path):
    frames, durs = [], []
    with Image.open(gif_path) as im:
        for f in ImageSequence.Iterator(im):
            frames.append(f.convert('RGBA').copy())
            durs.append(max(30, int(im.info.get('duration', 80))))
    return frames, durs


def import_gif(gif_path, pid, name=None, species='pokemon', scale='auto',
               dest=None, description=''):
    frames, durs = read_frames(gif_path)
    if not frames:
        raise SystemExit('GIF 里没有帧')
    fw, fh = frames[0].size

    # 缩放：整数倍 NEAREST（像素风锐利）；auto = 放大到目标高
    if scale == 'auto':
        factor = max(1, min(8, round(TARGET_H / max(fh, 1))))
    else:
        factor = max(1, int(scale))
    fw, fh = fw * factor, fh * factor
    if factor > 1:
        frames = [f.resize((fw, fh), Image.NEAREST) for f in frames]

    # 画布：帧居中、**脚底贴合**（按所有帧的最低不透明行对齐到 foot 上方，
    # 否则源 GIF 底部留白的精灵会悬空）、留出呼吸/弹跳余量
    window = int(max(fw, fh) + 12) // 2 * 2
    foot = window - FOOT_PAD
    x0 = (window - fw) // 2
    import numpy as np
    bottom = -1
    for f in frames:
        rows = np.nonzero((np.array(f)[:, :, 3] > 8).any(axis=1))[0]
        if len(rows):
            bottom = max(bottom, int(rows[-1]))
    y0 = foot - 1 - bottom if bottom >= 0 else foot - fh

    pack_dir = os.path.join(dest or anims.ANIMS_DIR, pid)
    os.makedirs(os.path.join(pack_dir, 'frames'), exist_ok=True)
    names = []
    for i, f in enumerate(frames):
        canvas = Image.new('RGBA', (window, window), (0, 0, 0, 0))
        canvas.paste(f, (x0, y0), f)
        name_i = f'idle_{i}.png'
        canvas.save(os.path.join(pack_dir, 'frames', name_i))
        names.append(name_i)

    states = {
        'idle': {'frames': names, 'durations': durs},
        'walk': {'frames': names, 'durations': durs, 'flip_left': True},
        'happy': {'frames': names, 'durations': durs},
        'sleep': {'frames': names[:1], 'durations': [1000]},
    }
    meta = {'id': pid,
            'displayName': name or pid,
            'description': description
            or f'{pid}（GIF 导入 · 帧率 {1000.0 / (sum(durs) / len(durs)):.0f}fps）',
            'species': species,
            'window': window,
            'foot': foot,
            'phrases': {},
            'tricks': [],
            'states': states}
    with open(os.path.join(pack_dir, 'anim.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    print(f'{pid}: {len(frames)} 帧 @{1000.0 / (sum(durs) / len(durs)):.0f}fps '
          f'窗口 {window} → {pack_dir}')
    return meta


def main(argv=None):
    ap = argparse.ArgumentParser(description='GIF → v2 动画资产包')
    ap.add_argument('--gif', required=True, help='输入 GIF 路径')
    ap.add_argument('--id', required=True, help='角色 id（anims/<id>/）')
    ap.add_argument('--name', default=None, help='显示名（缺省用 id）')
    ap.add_argument('--species', default='pokemon')
    ap.add_argument('--scale', default='auto',
                    help='缩放：auto=按目标高整数倍放大，或直接给倍数')
    ap.add_argument('--dest', default=None, help='输出根目录（缺省 anims/）')
    args = ap.parse_args(argv)
    import_gif(args.gif, args.id, name=args.name, species=args.species,
               scale=args.scale, dest=args.dest)


if __name__ == '__main__':
    main()
