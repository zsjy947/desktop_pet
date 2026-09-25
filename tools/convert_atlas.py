# -*- coding: utf-8 -*-
"""hatched/ 图集包 → anims/ v2 资产包一键转换。

图集契约（hatch_sprites.py）：1536x1872 = 8 列 x 9 行，格 192x208，
行序固定（0 idle / 1 running-right / 2 running-left / 3 waving /
4 jumping / 5 failed / 6 waiting / 7 running / 8 review）。转换规则：

    行 0 → idle        行 1 → walk（flip_left=true，行 2 丢弃改运行时镜像）
    行 3 → happy       行 4 → jump
    pet.json sleep_row → sleep
    pet.json tricks[i].row → trick{i}（按声明顺序）

每格贴进 window x window 画布（水平居中），脚底线 = 窗口底 - FOOT_PAD，
逐帧时长沿用 ROW_SPECS。像素原样搬运（alpha 不动）——v2 资产保留软
alpha 的能力，供逐像素透明窗口与云端管线使用。

用法：python tools/convert_atlas.py [id ...]     # 无参数 = 全部转换
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image

from pet import anims, hatch_sprites

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HATCHED = os.path.join(ROOT, 'hatched')

FOOT_PAD = 6      # hatch_pet.compose_atlas 合成时脚底离格底的间隙
FIXED_ROWS = ((0, 'idle'), (1, 'walk'), (3, 'happy'), (4, 'jump'))


def convert(pid, dest=None):
    """转换一个 hatched/<id>/ → anims/<id>/，返回 anim.json 内容。"""
    src = os.path.join(HATCHED, pid)
    with open(os.path.join(src, 'pet.json'), encoding='utf-8') as f:
        pet = json.load(f)
    atlas = Image.open(os.path.join(src, pet.get('spritesheetPath')
                                    or 'spritesheet.png')).convert('RGBA')
    window = int(pet.get('window') or hatch_sprites.CELL_H)
    available = pet.get('available_rows')
    pack_dir = os.path.join(dest or anims.ANIMS_DIR, pid)
    os.makedirs(os.path.join(pack_dir, 'frames'), exist_ok=True)

    row_durs = {row: durs for _n, row, _c, durs in hatch_sprites.ROW_SPECS}

    states, trick_states = {}, []
    fdir = os.path.join(pack_dir, 'frames')

    def _add(row, state, durs=None):
        """一行 → 一个状态；全透明行（available 声明了但没画）跳过。"""
        entry = _row_state(fdir, atlas, row, window, durs or row_durs.get(row))
        if entry['frames']:
            states[state] = entry
        return entry

    for row, state in FIXED_ROWS:
        if available is not None and row not in available:
            continue
        _add(row, state)
        if state == 'walk' and 'walk' in states:
            states['walk']['flip_left'] = True
    sleep_row = pet.get('sleep_row')
    if (sleep_row is not None
            and (available is None or sleep_row in available)
            and sleep_row in row_durs):
        _add(sleep_row, 'sleep')
    for i, t in enumerate(pet.get('tricks') or []):
        try:
            row = int(t.get('row'))
        except (TypeError, ValueError):
            continue
        if not 0 <= row < hatch_sprites.N_ROWS:
            continue
        if available is not None and row not in available:
            continue
        if _add(row, f'trick{i}'):
            trick_states.append({'name': str(t.get('name') or '动作'),
                                 'state': f'trick{i}',
                                 'fx': str(t.get('fx') or ''),
                                 'cry': str(t.get('cry') or '')})

    meta = {'id': pid,
            'displayName': pet.get('displayName') or pid,
            'description': pet.get('description') or '',
            'species': pet.get('species') or 'human',
            'window': window,
            'foot': window - FOOT_PAD,
            'phrases': pet.get('phrases') or {},
            'tricks': trick_states,
            'states': states}
    with open(os.path.join(pack_dir, 'anim.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    print(f'{pid}: {len(states)} 状态 / '
          f'{sum(len(s["frames"]) for s in states.values())} 帧 → {pack_dir}')
    return meta


def _row_state(fdir, atlas, row, window, durs):
    """图集一行 → 一个状态条目（帧 PNG 写盘 + durations）。"""
    cw, ch = hatch_sprites.CELL_W, hatch_sprites.CELL_H
    names = []
    for col in range(hatch_sprites.COLS):
        cell = atlas.crop((col * cw, row * ch,
                           (col + 1) * cw, (row + 1) * ch))
        if cell.getextrema()[3][1] > 0:      # 全透明格（未用槽位）跳过
            canvas = Image.new('RGBA', (window, window), (0, 0, 0, 0))
            canvas.paste(cell, ((window - cw) // 2, 0), cell)
            name = f'r{row}c{col}.png'
            canvas.save(os.path.join(fdir, name))
            names.append(name)
    return {'frames': names, 'durations': list(durs or [])}


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    pids = args or sorted(
        d for d in os.listdir(HATCHED)
        if os.path.isfile(os.path.join(HATCHED, d, 'pet.json')))
    for pid in pids:
        if not os.path.isfile(os.path.join(HATCHED, pid, 'pet.json')):
            print(f'跳过 {pid}：hatched/{pid}/pet.json 不存在')
            continue
        convert(pid)


if __name__ == '__main__':
    main()
