# -*- coding: utf-8 -*-
"""角色添加接口：传入一张图片，生成桌面宠物精灵帧并注册角色与台词。

既是命令行工具，也可被 tools/character_server.py（本地上传网页）调用：

    # 命令行（需要抠图时须先 pip install "rembg[cpu]"）
    python tools/add_character.py --image 我的人物.png --id mychar --name 小 char
    python tools/add_character.py --image 照片.jpg --id mychar --model isnet-anime \
        --talk '你好呀' --talk '今天也加油鸭' --feed '谢谢投喂！'

    # 透明底 PNG 可跳过抠图（无需 rembg）
    python tools/add_character.py --image cutout.png --id mychar

台词条目可选；未提供的类别使用通用兜底台词，之后可直接改
custom_characters.json。
"""
import argparse
import json
import os
import sys

from PIL import Image, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import build_sprites as bs  # noqa: E402
from pet import custom  # noqa: E402


def cutout_image(src_path, model='u2net'):
    """带背景的图片 → 整身抠图 RGBA。透明底 PNG 直接返回（跳过 rembg）。"""
    img = ImageOps.exif_transpose(Image.open(src_path))
    if img.mode == 'RGBA':
        alpha = img.getchannel('A')
        lo, hi = alpha.getextrema()
        if lo < 250:          # 已是抠好的透明底图
            return img
    from rembg import new_session, remove
    cut = remove(img.convert('RGB'), session=new_session(model))
    return bs.drop_small_islands(cut)


def add_character(image_path, char_id, name=None, model='u2net',
                  phrases=None):
    """生成精灵帧并注册角色，返回角色预设 dict。

    phrases: {类别: [台词, ...]}，可只给部分类别，其余用通用兜底。
    """
    char_id = (char_id or '').strip().lower()
    if not custom.valid_id(char_id):
        raise ValueError(f'非法角色 id：{char_id!r}（小写字母开头，仅含'
                         f'小写字母/数字/下划线，且不与内置角色冲突）')
    if not os.path.exists(image_path):
        raise FileNotFoundError(image_path)

    cut = cutout_image(image_path, model=model)
    cut = bs.drop_small_islands(cut)
    cut = bs.clean_cutout(cut)
    _, manifest = bs.finish_character(cut, char_id)

    entry = {'id': char_id, 'name': name or char_id, 'photo': char_id,
             'phrases': {k: list(v) for k, v in (phrases or {}).items()}}
    custom.upsert(entry)
    print(f'[ok] 角色 {char_id}（{entry["name"]}）已添加：'
          f'{len(manifest["frames"])} 个状态，重启宠物或重新打开菜单即可看到')
    return custom.normalize(entry)


def _phrase_args(parser):
    for key in custom.PHRASE_KEYS:
        parser.add_argument(f'--{key}', action='append', default=None,
                            metavar='台词', help=f'{key} 类台词，可重复')


def _collect_phrases(args):
    phrases = {}
    for key in custom.PHRASE_KEYS:
        lines = getattr(args, key, None)
        if lines:
            phrases[key] = lines
    return phrases


def main():
    parser = argparse.ArgumentParser(
        description='传入图片生成桌面宠物角色（抠图 → 精灵帧 → 台词注册）')
    parser.add_argument('--image', required=True, help='图片路径'
                        '（带背景自动抠图；透明底 PNG 跳过抠图）')
    parser.add_argument('--id', required=True, dest='char_id',
                        help='角色 id：小写字母开头，仅含小写字母/数字/下划线')
    parser.add_argument('--name', default=None, help='菜单显示名（默认用 id）')
    parser.add_argument('--model', default='u2net',
                        choices=('u2net', 'isnet-anime', 'isnet-general-use'),
                        help='抠图模型：真人照片 u2net，动漫插画 isnet-anime')
    _phrase_args(parser)
    args = parser.parse_args()
    add_character(args.image, args.char_id, args.name, args.model,
                  _collect_phrases(args))


if __name__ == '__main__':
    main()
