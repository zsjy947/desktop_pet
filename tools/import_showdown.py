# -*- coding: utf-8 -*-
"""Pokémon Showdown 动画 → anims/ v2 资产批量导入（宝可梦线主力管线）。

Pokémon Showdown 的 ani 精灵（https://play.pokemonshowdown.com/sprites/
ani/<id>.gif）是官方风格的高帧率（~25fps）透明战斗动画，质量远超逐帧
i2i 生成的图集——2026-09-25 按用户决策把 5 只宝可梦全部替换为
Showdown 动画（tricks 专属动作随图集退役：GIF 无对应动画帧；tk 层的
hatched/ 包不动，仍带 tricks 兜底）。

元数据继承：displayName / description / species / phrases（叫声包）从
hatched/<id>/pet.json 带过来，用户无感知换皮。

用法：python tools/import_showdown.py [id ...]     # 缺省全部 5 只
"""
import json
import os
import shutil
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pet import anims
from tools.import_gif import import_gif

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HATCHED = os.path.join(ROOT, 'hatched')
GIF_DIR = os.path.join(ROOT, 'localgen', 'showdown')

POKEMON = ['pikachu', 'eevee', 'shaymin', 'victini', 'sprigatito']
URL = 'https://play.pokemonshowdown.com/sprites/ani/{}.gif'


def download(pid):
    """下载 GIF 到 localgen/showdown/ 缓存（已存在则跳过），返回路径。"""
    os.makedirs(GIF_DIR, exist_ok=True)
    path = os.path.join(GIF_DIR, f'{pid}.gif')
    if not os.path.isfile(path):
        req = urllib.request.Request(
            URL.format(pid), headers={'User-Agent': 'desktop-pet/1.0'})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
        with open(path, 'wb') as f:
            f.write(data)
    return path


def import_one(pid):
    """替换 anims/<pid>/ 为 Showdown 动画，元数据从 hatched 继承。"""
    pet_json = os.path.join(HATCHED, pid, 'pet.json')
    old = {}
    if os.path.isfile(pet_json):
        with open(pet_json, encoding='utf-8') as f:
            old = json.load(f)

    # 清掉旧包（转换包的 r0c0.png 等帧不能残留）
    pack_dir = os.path.join(anims.ANIMS_DIR, pid)
    if os.path.isdir(pack_dir):
        shutil.rmtree(pack_dir)

    meta = import_gif(download(pid), pid,
                      name=old.get('displayName') or pid,
                      species=old.get('species') or 'pokemon',
                      description=old.get('description') or '')
    meta['phrases'] = old.get('phrases') or {}
    with open(os.path.join(pack_dir, 'anim.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    return meta


def main(argv=None):
    ids = list(sys.argv[1:] if argv is None else argv) or POKEMON
    for pid in ids:
        meta = import_one(pid)
        n_frames = len(meta['states']['idle']['frames'])
        print(f"  {pid}: {meta['displayName']} {n_frames} 帧 / "
              f"{len(meta['states'])} 状态")


if __name__ == '__main__':
    main()
