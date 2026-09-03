# -*- coding: utf-8 -*-
"""hatch-pet 生成管线（开发期工具，借鉴 OpenAI Codex 的 hatch-pet skill）。

流程（对应 hatch-pet 的 base -> row strips -> 确定性组装 -> QA）：
  1. base：z-image-turbo 生成角色定形象（identity 在所有提示词中原样复述，
     作为无参考图能力下的"身份锁"）
  2. 逐行生成姿势条带（8 条；running-left 由 running-right 逐帧镜像派生，
     保持时序——与 hatch-pet 的派生策略一致）
  3. 确定性处理：四角取背景色阈值分割 -> 4x 块级洪泛（与边界不相连的
     即前景，自动填洞）-> 连通域去杂物 -> 行内统一缩放、脚底对齐格底 ->
     alpha 二值化 + 透明像素 RGB 清零（键色窗口的硬性要求）
  4. 合成 1536x1872 图集（8 列 x 9 行，格 192x208，行序固定）并校验
  5. QA：联络表 + 每行 GIF 预览
  6. 打包 hatched/<id>/{pet.json, spritesheet.png}，运行时由
     pet/hatch_sprites.py 播放

用法：
    python tools/hatch_pet.py --id mango --name 芒果 \
        --prompt 'a chubby orange tabby kitten with big round eyes' \
        [--style sticker] [--desc '一句话介绍']
    python tools/hatch_pet.py --import-atlas sheet.webp --id codey --name Codey
依赖（仅构建期）：pip install pillow numpy requests
"""
import argparse
import json
import os
import sys
import time

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

from pet import hatch_sprites as hs  # noqa: E402  行序/帧数/格子的唯一事实源

OUT_DIR = os.path.join(ROOT, 'hatched')

CELL_W, CELL_H = hs.CELL_W, hs.CELL_H
COLS = hs.COLS
FOOT_PAD = 6          # 合成时脚底距格底的距离（窗口落地后即离地间隙）
MAX_SIDE = 10         # 格内内容四边留白

# z-image-turbo（reference/image.py 同款 ModelScope 异步接口）。
# key 不入库：优先读环境变量 MODELSCOPE_API_KEY，否则从本地未入库的
# reference/image.py 里解析，都没有再报错。
_API = 'https://api-inference.modelscope.cn/'
_MODEL = 'Tongyi-MAI/Z-Image-Turbo'


def _api_key():
    key = os.environ.get('MODELSCOPE_API_KEY')
    if key:
        return key
    ref = os.path.join(ROOT, 'reference', 'image.py')
    try:
        with open(ref, encoding='utf-8') as f:
            for line in f:
                if 'api_key' in line and '"' in line:
                    return line.split('"')[1]
    except OSError:
        pass
    raise SystemExit('找不到 ModelScope API key：请设置环境变量 '
                     'MODELSCOPE_API_KEY，或保留 reference/image.py')

# 风格预设：轮廓干净、颜色平坦的最利于抠图与键色透明
STYLES = {
    'sticker': 'cute flat sticker style with a bold dark outline and vivid flat colors',
    'pixel': 'cute pixel art with a limited palette and crisp square pixels',
    'chibi': 'cute chibi cartoon with clean flat colors and minimal soft shading',
    'auto': 'cute mascot character design',
}

# 每行动作描述（浓缩自 hatch-pet 的 state-specific guidance）
ROW_ACTIONS = {
    'idle': ('standing calmly, subtle looping micro-motion only '
             '(blinking, tiny breathing bob), nearly identical frames'),
    'running-right': ('a clear walking cycle moving to the right, directional '
                      'gait, legs alternating between frames'),
    'waving': ('greeting wave with one arm: arm down, arm raised waving, arm '
               'returning down'),
    'jumping': ('a jump: anticipation crouch, lift-off, airborne peak, '
                'descent, landing settle'),
    'failed': ('sad deflated reaction: shoulders droop, body slumps down, '
               'then slowly recovers'),
    'waiting': ('expectant asking pose looking at the viewer, pleading gently '
                'for attention'),
    'running': ('concentrating on a task in place, typing or scanning '
                'intently, NOT traveling, legs still'),
    'review': ('inspecting or thinking, examining something closely with a '
               'focused look'),
}


def gen_image(prompt, out_path):
    """z-image-turbo 异步生成一张图并下载到 out_path。"""
    import requests
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    key = _api_key()
    headers = {'Authorization': f'Bearer {key}',
               'Content-Type': 'application/json'}
    r = requests.post(
        _API + 'v1/images/generations',
        headers={**headers, 'X-ModelScope-Async-Mode': 'true'},
        data=json.dumps({'model': _MODEL, 'prompt': prompt}).encode('utf-8'),
        verify=False, timeout=60)
    r.raise_for_status()
    task_id = r.json()['task_id']

    while True:
        d = requests.get(
            _API + f'v1/tasks/{task_id}',
            headers={**headers, 'X-ModelScope-Task-Type': 'image_generation'},
            verify=False, timeout=60).json()
        if d['task_status'] == 'SUCCEED':
            raw = requests.get(d['output_images'][0], verify=False,
                               timeout=180).content
            with open(out_path, 'wb') as f:
                f.write(raw)
            return out_path
        if d['task_status'] == 'FAILED':
            raise RuntimeError(f'生图失败：{prompt[:60]}...')
        time.sleep(4)


# ---------------- 确定性图像处理 ----------------

def _resample(name):
    return getattr(getattr(Image, 'Resampling', Image), name)


def binarize_alpha(img, thresh=128):
    a = img.getchannel('A').point(lambda v: 255 if v >= thresh else 0)
    out = img.copy()
    out.putalpha(a)
    return out


def zero_transparent_rgb(img):
    """全透明像素的 RGB 清零：键色窗口会拿透明像素的 RGB 与键色混合，
    残留颜色会形成暗边/色晕（hatch-pet 的 transparency invariant 同款）。"""
    import numpy as np
    arr = np.array(img)
    arr[arr[..., 3] == 0] = 0
    return Image.fromarray(arr, 'RGBA')


def remove_bg(img, tol=42):
    """纯色底抠图：四角均色为背景色 -> 阈值分割 -> 4x 块级洪泛。

    与边界连通的近似背景色区域判为背景；其余（含封闭孔洞）判为前景，
    天然完成填洞。前景中按连通域面积再去一遍杂物。
    """
    import numpy as np
    from collections import deque

    arr = np.array(img.convert('RGB')).astype(np.int32)
    h, w = arr.shape[:2]
    corners = np.concatenate([arr[:8, :8].reshape(-1, 3), arr[:8, -8:].reshape(-1, 3),
                              arr[-8:, :8].reshape(-1, 3), arr[-8:, -8:].reshape(-1, 3)])
    bg = corners.mean(axis=0)
    near_bg = (np.sqrt(((arr - bg) ** 2).sum(axis=2)) < tol)

    # 4x 块洪泛：从边界出发的近背景块 = 背景，其余全为前景（自动填洞）
    h4, w4 = h // 4, w // 4
    nb4 = near_bg[:h4 * 4, :w4 * 4].reshape(h4, 4, w4, 4).all(axis=(1, 3))
    bg4 = np.zeros((h4, w4), dtype=bool)
    dq = deque()
    for x in range(w4):
        for y in (0, h4 - 1):
            if nb4[y, x] and not bg4[y, x]:
                bg4[y, x] = True
                dq.append((y, x))
    for y in range(h4):
        for x in (0, w4 - 1):
            if nb4[y, x] and not bg4[y, x]:
                bg4[y, x] = True
                dq.append((y, x))
    while dq:
        y, x = dq.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h4 and 0 <= nx < w4 and nb4[ny, nx] and not bg4[ny, nx]:
                bg4[ny, nx] = True
                dq.append((ny, nx))
    fg4 = ~bg4

    # 连通域去杂物：保留面积 >= 最大块 8% 的前景块
    labels = np.zeros((h4, w4), dtype=np.int32)
    sizes = {}
    cur = 0
    for sy in range(h4):
        for sx in range(w4):
            if fg4[sy, sx] and labels[sy, sx] == 0:
                cur += 1
                labels[sy, sx] = cur
                q = deque([(sy, sx)])
                n = 0
                while q:
                    y, x = q.popleft()
                    n += 1
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = y + dy, x + dx
                        if (0 <= ny < h4 and 0 <= nx < w4
                                and fg4[ny, nx] and labels[ny, nx] == 0):
                            labels[ny, nx] = cur
                            q.append((ny, nx))
                sizes[cur] = n
    if sizes:
        biggest = max(sizes.values())
        keep = {l for l, n in sizes.items() if n >= max(biggest * 0.08, 3)}
        fg4 = np.isin(labels, list(keep))

    alpha4 = np.repeat(np.repeat(fg4, 4, axis=0), 4, axis=1)
    full = np.zeros((h, w), dtype=bool)
    full[:h4 * 4, :w4 * 4] = alpha4
    full[h4 * 4:, :] = ~near_bg[h4 * 4:, :]
    full[:, w4 * 4:] = ~near_bg[:, w4 * 4:]

    out = np.array(img.convert('RGBA'))
    out[..., 3] = np.where(full, 255, 0)
    return zero_transparent_rgb(Image.fromarray(out, 'RGBA'))


def extract_frames(strip, n):
    """从姿势条带里检测角色连通域，按阅读顺序取 n 帧。

    生成模型并不保证把 n 个姿势画成等距横排（实测常画成网格），所以
    不做固定等分切槽：抠底后按 4x 块级 8-连通域找出每个角色（互相分离
    的猫/人不会粘连，部件断开的耳朵尾巴靠 8-连通收回来），行优先排序
    （先上后下、行内从左到右），再取 n 帧。
    """
    import numpy as np
    from collections import deque

    cut = remove_bg(strip)
    a = np.array(cut)
    mask = a[..., 3] > 0
    h, w = mask.shape
    h4, w4 = h // 4, w // 4
    m4 = mask[:h4 * 4, :w4 * 4].reshape(h4, 4, w4, 4).any(axis=(1, 3))

    labels = np.zeros((h4, w4), dtype=np.int32)
    groups = []                       # (label, 块列表)
    cur = 0
    for sy in range(h4):
        for sx in range(w4):
            if m4[sy, sx] and labels[sy, sx] == 0:
                cur += 1
                labels[sy, sx] = cur
                blocks = []
                q = deque([(sy, sx)])
                while q:
                    y, x = q.popleft()
                    blocks.append((y, x))
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            if dy == 0 and dx == 0:
                                continue
                            ny, nx = y + dy, x + dx
                            if (0 <= ny < h4 and 0 <= nx < w4
                                    and m4[ny, nx] and labels[ny, nx] == 0):
                                labels[ny, nx] = cur
                                q.append((ny, nx))
                groups.append((cur, blocks))
    if not groups:
        return [None] * n
    biggest = max(len(b) for _l, b in groups)
    keep = [(l, b) for l, b in groups if len(b) >= max(biggest * 0.06, 8)]

    frames = []
    for lab, blocks in keep:
        ys = [p[0] for p in blocks]
        xs = [p[1] for p in blocks]
        y0, y1 = max(0, min(ys) * 4), min(h, (max(ys) + 1) * 4)
        x0, x1 = max(0, min(xs) * 4), min(w, (max(xs) + 1) * 4)
        sub = (labels[y0 // 4:y1 // 4, x0 // 4:x1 // 4] == lab)
        sub_full = np.repeat(np.repeat(sub, 4, axis=0), 4, axis=1)
        crop = a[y0:y1, x0:x1].copy()
        crop[~sub_full] = 0           # 只留本连通域，排除相邻角色的越界像素
        img = Image.fromarray(crop, 'RGBA')
        bbox = img.getbbox()
        frames.append(img.crop(bbox) if bbox else None)

    frames = _reading_order([f for f in frames if f is not None])
    return _pick_n(frames, n)


def _reading_order(frames):
    """行优先排序：按 y 中心聚行（行高自适应），行内按 x。"""
    if not frames:
        return frames
    infos = [(f, (f.getbbox()[1] + f.getbbox()[3]) / 2, f.getbbox()[0])
             for f in frames]
    infos.sort(key=lambda it: it[1])
    rows, cur_cy = [], None
    for it in infos:
        f, cy, _x = it
        hh = f.getbbox()[3] - f.getbbox()[1]
        if cur_cy is None or abs(cy - cur_cy) > hh * 0.6:
            rows.append([cy, [it]])
            cur_cy = cy
        else:
            rows[-1][1].append(it)
            cur_cy = sum(i[1] for i in rows[-1][1]) / len(rows[-1][1])
    out = []
    for _cy, group in rows:
        group.sort(key=lambda it: it[2])
        out.extend(it[0] for it in group)
    return out


def _pick_n(frames, n):
    """取出 n 帧：多于 n 时均匀抽样，不足 n 时循环复用。"""
    if not frames:
        return [None] * n
    if len(frames) >= n:
        idx = sorted({i * (len(frames) - 1) // max(1, n - 1)
                      for i in range(n)}) if n > 1 else [0]
        picked = [frames[i] for i in idx]
        while len(picked) < n:
            picked.append(picked[-1])
        return picked
    return [frames[i % len(frames)] for i in range(n)]


def place_row(slots, n):
    """槽内容放进 n 个 192x208 格：行内统一缩放（防帧间大小跳变）、
    脚底对齐格底、水平居中。空槽克隆最近邻帧。"""
    good = [s for s in slots if s is not None]
    if not good:
        raise RuntimeError('整行条带都没抠出内容')
    max_w = max(s.width for s in good)
    max_h = max(s.height for s in good)
    scale = min((CELL_W - MAX_SIDE) / max_w, (CELL_H - MAX_SIDE) / max_h)
    cells = []
    last = good[0]
    for s in slots:
        if s is None:
            s = last                     # 空槽：克隆上一帧保时序
        last = s
        im = s.resize((max(1, round(s.width * scale)),
                       max(1, round(s.height * scale))), _resample('LANCZOS'))
        im = binarize_alpha(im)          # 缩放插值产生半透明，重新二值化
        canvas = Image.new('RGBA', (CELL_W, CELL_H), (0, 0, 0, 0))
        canvas.alpha_composite(
            im, ((CELL_W - im.width) // 2, CELL_H - FOOT_PAD - im.height))
        cells.append(zero_transparent_rgb(canvas))
    return cells


def mirror_cells(cells):
    """逐帧镜像（不整条翻转）：保持帧时序语义（hatch-pet 派生策略）。"""
    return [c.transpose(Image.FLIP_LEFT_RIGHT) for c in cells]


def compose_atlas(rows_cells):
    """rows_cells: {行号: [格,...]} -> 1536x1872 图集，未用格全透明。"""
    atlas = Image.new('RGBA', (hs.ATLAS_W, hs.ATLAS_H), (0, 0, 0, 0))
    for _name, row, n, _d in hs.ROW_SPECS:
        cells = rows_cells.get(row)
        if not cells:
            continue
        for col, cell in enumerate(cells[:n]):
            atlas.alpha_composite(cell, (col * CELL_W, row * CELL_H))
    return zero_transparent_rgb(atlas)


def validate_atlas(atlas, strict=True):
    """校验契约：尺寸、每行已用格非空、未用格全透明、透明像素无 RGB 残留。
    返回问题列表；strict=True 时行内容缺失也算问题。"""
    import numpy as np
    problems = []
    if atlas.size != (hs.ATLAS_W, hs.ATLAS_H):
        problems.append(f'尺寸 {atlas.size} != {(hs.ATLAS_W, hs.ATLAS_H)}')
    a = np.array(atlas)
    rows_ok = []
    for _name, row, n, _d in hs.ROW_SPECS:
        band = a[row * CELL_H:(row + 1) * CELL_H]
        cells = [band[:, c * CELL_W:(c + 1) * CELL_W] for c in range(n)]
        has = [(u[..., 3] > 0).any() for u in cells]
        if not any(has):
            problems.append(f'行 {row}（{_name}）整行空白')
        elif not all(has):
            problems.append(f'行 {row}（{_name}）有空帧槽')
        if band[:, n * CELL_W:, 3].any():
            problems.append(f'行 {row}（{_name}）未用格不透明')
        rows_ok.append(any(has))
    mask = a[..., 3] == 0
    if mask.any() and a[..., :3][mask].any():
        problems.append('透明像素残留 RGB（会形成暗边）')
    if strict and not all(rows_ok):
        problems.append('存在整行缺失（strict 模式不允许）')
    return problems


def qa_outputs(atlas, run_dir, pet_id):
    """QA 媒体：联络表（深灰底画格线）+ 每行 GIF（灰底，看帧间大小跳动）。"""
    import numpy as np
    qa = os.path.join(run_dir, 'qa')
    os.makedirs(qa, exist_ok=True)

    cell_bg = 52
    pad = 6
    sheet = Image.new('RGB', (COLS * (CELL_W // 2 + pad) + pad,
                              hs.N_ROWS * (CELL_H // 2 + pad) + pad),
                      (cell_bg, cell_bg, cell_bg))
    a = np.array(atlas)
    for _name, row, n, _d in hs.ROW_SPECS:
        for col in range(n):
            cell = atlas.crop((col * CELL_W, row * CELL_H,
                               (col + 1) * CELL_W, (row + 1) * CELL_H))
            half = cell.resize((CELL_W // 2, CELL_H // 2), _resample('NEAREST'))
            x = pad + col * (CELL_W // 2 + pad)
            y = pad + row * (CELL_H // 2 + pad)
            sheet.paste(half, (x, y), half)
    sheet.save(os.path.join(qa, f'{pet_id}_contact_sheet.png'))

    for name, row, n, durs in hs.ROW_SPECS:
        frames = []
        for col in range(n):
            cell = atlas.crop((col * CELL_W, row * CELL_H,
                               (col + 1) * CELL_W, (row + 1) * CELL_H))
            frame = Image.new('RGB', (CELL_W, CELL_H), (cell_bg,) * 3)
            frame.paste(cell, (0, 0), cell)
            frames.append(frame)
        frames[0].save(os.path.join(qa, f'row{row}_{name}.gif'),
                       save_all=True, append_images=frames[1:],
                       duration=durs, loop=0)


def write_package(atlas, pet_id, name, desc, run_dir):
    os.makedirs(run_dir, exist_ok=True)
    atlas.save(os.path.join(run_dir, 'spritesheet.png'))
    rows_used = [n if cells else 0 for (_n, row, n, _d), cells in
                 zip(hs.ROW_SPECS, _rows_in(atlas))]
    meta = {'id': pet_id, 'displayName': name, 'description': desc,
            'spritesheetPath': 'spritesheet.png',
            'window': CELL_H,
            'available_rows': [row for row, used in enumerate(rows_used)
                               if used]}
    with open(os.path.join(run_dir, 'pet.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)


def _rows_in(atlas):
    import numpy as np
    a = np.array(atlas)
    out = []
    for _name, row, n, _d in hs.ROW_SPECS:
        band = a[row * CELL_H:(row + 1) * CELL_H]
        cells = [band[:, c * CELL_W:(c + 1) * CELL_W] for c in range(n)]
        out.append([c for c in cells if (c[..., 3] > 0).any()] or None)
    return out


# ---------------- 主流程 ----------------

def identity_block(prompt, style):
    style_txt = STYLES.get(style, style)
    return (f'{prompt}. {style_txt}. The character must look exactly the same '
            'in every frame: same face, same colors, same proportions.')


def strip_prompt(identity, action, n):
    return (f'{identity} Sprite sheet for animation: exactly {n} copies of the '
            f'same character in one single horizontal row, evenly spaced, all '
            f'the same size, all standing on the same ground line with feet '
            f'visible, pure white background, no text, no grid, no borders, '
            f'no shadows, no overlapping frames. Action across the {n} frames: {action}.')


def hatch(args):
    run_dir = os.path.join(OUT_DIR, args.id)
    build_dir = os.path.join(run_dir, 'build')
    os.makedirs(build_dir, exist_ok=True)
    identity = identity_block(args.prompt, args.style)

    print(f'[base] 生成角色定形象 -> build/base.png', flush=True)
    base_prompt = (f'{identity} Full body, single character, standing, '
                   'centered, on a flat pure white background. No text, '
                   'no watermark, no border.')
    if os.path.exists(os.path.join(build_dir, 'base.png')) and not args.force:
        print('       已存在，跳过（--force 重新生成）')
    else:
        gen_image(base_prompt, os.path.join(build_dir, 'base.png'))

    rows_cells = {}
    for name, row, n, _d in hs.ROW_SPECS:
        if name == 'running-left':
            continue                    # 由 running-right 镜像派生
        out = os.path.join(build_dir, f'strip_{name}.png')
        if os.path.exists(out) and not args.force:
            print(f'[row]   {name}: 已存在，跳过')
        else:
            print(f'[row]   {name}: 生成 {n} 帧条带...', flush=True)
            gen_image(strip_prompt(identity, ROW_ACTIONS[name], n), out)
        slots = extract_frames(Image.open(out), n)
        rows_cells[row] = place_row(slots, n)
        got = sum(1 for s in slots if s is not None)
        print(f'       检出并取用 {got}/{n} 帧', flush=True)

    rows_cells[2] = mirror_cells(rows_cells[1])
    print('[row]   running-left: 由 running-right 逐帧镜像派生')

    atlas = compose_atlas(rows_cells)
    problems = validate_atlas(atlas, strict=True)
    if problems:
        for p in problems:
            print(f'[warn]  {p}')
        if any('整行空白' in p for p in problems):
            print('[fail]  有整行缺失，先看 build/strip_*.png 与 qa/ 再调提示词')
    else:
        print('[ok]    图集校验通过')

    qa_outputs(atlas, run_dir, args.id)
    write_package(atlas, args.id, args.name, args.desc or '', run_dir)
    print(f'[done]  {run_dir}{os.sep}pet.json + spritesheet.png（QA 见 qa/），'
          f'重启宠物或重开菜单即可看到「{args.name}」')


def import_atlas(args):
    """把现成的 Codex 图集（png/webp）包装成本项目的桌宠包。"""
    run_dir = os.path.join(OUT_DIR, args.id)
    os.makedirs(run_dir, exist_ok=True)
    src = Image.open(args.import_atlas).convert('RGBA')
    if src.size != (hs.ATLAS_W, hs.ATLAS_H):
        ratio = src.width / src.height
        want = hs.ATLAS_W / hs.ATLAS_H
        if abs(ratio - want) > 0.02:
            raise SystemExit(f'图集长宽比 {ratio:.3f} 与 Codex 图集 {want:.3f} 不符，'
                             '拒绝缩放（请给 1536x1872 或等比图）')
        src = src.resize((hs.ATLAS_W, hs.ATLAS_H), _resample('LANCZOS'))
    atlas = zero_transparent_rgb(binarize_alpha(src))
    problems = validate_atlas(atlas, strict=False)
    for p in problems:
        print(f'[warn]  {p}')
    qa_outputs(atlas, run_dir, args.id)
    write_package(atlas, args.id, args.name, args.desc or '', run_dir)
    print(f'[done]  导入完成：{run_dir}{os.sep}（缺失的行运行时会回落 idle）')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--id', required=True, help='角色 id（小写字母开头）')
    parser.add_argument('--name', required=True, help='显示名字')
    parser.add_argument('--desc', default='', help='一句话介绍（写进 pet.json）')
    parser.add_argument('--prompt', help='角色形象描述（英文更稳）')
    parser.add_argument('--style', default='sticker',
                        choices=sorted(STYLES) + ['none'],
                        help='画风预设（默认 sticker，轮廓干净好抠图）')
    parser.add_argument('--force', action='store_true',
                        help='忽略已生成的 base/条带，全部重生成')
    parser.add_argument('--import-atlas',
                        help='导入现成 Codex 图集（png/webp）而不是生图')
    args = parser.parse_args()

    if args.import_atlas:
        import_atlas(args)
        return
    if not args.prompt:
        parser.error('生图模式需要 --prompt（或用 --import-atlas 导入现成图集）')
    hatch(args)


if __name__ == '__main__':
    main()
