# -*- coding: utf-8 -*-
"""ComfyUI 本地生图后端（开发期工具）：hatch 管线的本地版生图源。

把 tools/hatch_pet.py 的远程 z-image-turbo API 换成本地 ComfyUI
（默认 http://127.0.0.1:8188），确定性后处理（抠底/切帧/行内缩放/
合成/校验/QA）全部复用 hatch_pet，图集契约不变。

本地后端的两条帧生成路线（按生图工具的能力选）：
  strip  —— 一次生成整行条带（n 连贯姿势），模型不听版式时靠
            extract_frames 的连通域切帧兜底；
  frame  —— 逐帧 img2img：以定形象 base 为 init、低重绘幅度 +
            帧级姿势词，身份一致性最好，姿势变化幅度有限。

用法：
    # 单张测试（评估矩阵 / 挑 base 用）
    python tools/comfy_hatch.py gen --ckpt NoobAI-XL-v1.1.safetensors \
        --pos '...' --neg '...' --w 832 --h 1216 --out localgen/x.png
    python tools/comfy_hatch.py gen --zimage --pos '中文提示词' --out localgen/y.png
    python tools/comfy_hatch.py gen --ckpt DreamShaper_8_pruned.safetensors \
        --init ref.png --denoise 0.55 --pos '...' --out localgen/z.png

    # 组装图集桌宠包
    python tools/comfy_hatch.py atlas --id nino --name 二乃 \
        --base localgen/nino_base.png --ckpt NoobAI-XL-v1.1.safetensors \
        --rows idle,running-right,waving,jumping --mode frame
依赖（仅构建期）：pillow numpy requests
"""
import argparse
import hashlib
import json
import os
import sys
import time
import urllib.parse
import urllib.request

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import hatch_pet as hp  # noqa: E402  确定性后处理与行规格的唯一事实源
from pet import hatch_sprites as hs  # noqa: E402

SERVER = os.environ.get('COMFYUI_SERVER', 'http://127.0.0.1:8188')
COMFY_DIR = os.environ.get('COMFYUI_DIR', 'D:/AAA_code/python/ComfyUI')
INPUT_DIR = os.path.join(COMFY_DIR, 'input')

CKPT_DEFAULTS = {
    # 各底模的稳妥参数（来源：部署与使用说明.md / SDXL立绘调试模板.md）
    'DreamShaper_8_pruned.safetensors': dict(
        w=512, h=768, steps=20, cfg=7.0,
        sampler='dpmpp_2m', scheduler='karras'),
    'animagine-xl-4.0-opt.safetensors': dict(
        w=832, h=1216, steps=28, cfg=6.0,
        sampler='euler_ancestral', scheduler='normal'),
    'NoobAI-XL-v1.1.safetensors': dict(
        w=832, h=1216, steps=28, cfg=5.5,
        sampler='euler_ancestral', scheduler='normal'),
}


# ---------------- ComfyUI API 客户端 ----------------

def _http_json(path, payload=None, timeout=60):
    req = urllib.request.Request(
        SERVER + path,
        data=None if payload is None else json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST' if payload is not None else 'GET')
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))


def free_models():
    """卸载已加载模型释放内存/显存（换底模前调用；16GB 内存贴线）。
    /free 成功时返回空 body，不解析响应。"""
    try:
        _http_json('/free', {'unload_models': True, 'free_memory': True})
    except (OSError, ValueError):
        pass


def submit(graph, client_id='comfy-hatch'):
    return _http_json('/prompt', {'prompt': graph,
                                  'client_id': client_id})['prompt_id']


def wait_output(prompt_id, poll=2.0):
    """阻塞直到该 prompt 完成，返回 outputs 里全部图片信息。"""
    while True:
        hist = _http_json(f'/history/{prompt_id}')
        if prompt_id in hist:
            entry = hist[prompt_id]
            status = entry.get('status', {})
            if status.get('status_str') == 'error':
                raise RuntimeError(f'ComfyUI 执行出错：'
                                   f'{status.get("messages", "")}')
            imgs = []
            for node in entry.get('outputs', {}).values():
                imgs.extend(node.get('images', []))
            if imgs:
                return imgs
        time.sleep(poll)


def fetch(img_info, out_path):
    q = urllib.parse.urlencode(img_info)
    with urllib.request.urlopen(f'{SERVER}/view?{q}', timeout=300) as r:
        data = r.read()
    with open(out_path, 'wb') as f:
        f.write(data)
    return out_path


def _put_init(path):
    """把 init 图复制进 ComfyUI/input（LoadImage 只认输入目录）。"""
    os.makedirs(INPUT_DIR, exist_ok=True)
    name = 'ch_' + hashlib.md5(os.path.abspath(path).encode('utf-8')
                               ).hexdigest()[:10] + '.png'
    Image.open(path).convert('RGB').save(os.path.join(INPUT_DIR, name))
    return name


# ---------------- 工作流构建 ----------------

def wf_ckpt(ckpt, pos, neg, w, h, seed, steps, cfg, sampler, scheduler,
            denoise=1.0, init=None, prefix='comfy'):
    """SD1.5/SDXL checkpoint 的文生图 / 图生图（init 给定时）最小图。"""
    g = {'1': {'class_type': 'CheckpointLoaderSimple',
               'inputs': {'ckpt_name': ckpt}}}
    if init:
        g['2'] = {'class_type': 'LoadImage', 'inputs': {'image': init}}
        g['3'] = {'class_type': 'VAEEncode',
                  'inputs': {'pixels': ['2', 0], 'vae': ['1', 2]}}
        latent = ['3', 0]
    else:
        g['6'] = {'class_type': 'EmptyLatentImage',
                  'inputs': {'width': w, 'height': h, 'batch_size': 1}}
        latent = ['6', 0]
    g['4'] = {'class_type': 'CLIPTextEncode',
              'inputs': {'clip': ['1', 1], 'text': pos}}
    g['5'] = {'class_type': 'CLIPTextEncode',
              'inputs': {'clip': ['1', 1], 'text': neg}}
    g['7'] = {'class_type': 'KSampler',
              'inputs': {'model': ['1', 0], 'positive': ['4', 0],
                         'negative': ['5', 0], 'latent_image': latent,
                         'seed': seed, 'steps': steps, 'cfg': cfg,
                         'sampler_name': sampler, 'scheduler': scheduler,
                         'denoise': denoise}}
    g['8'] = {'class_type': 'VAEDecode',
              'inputs': {'samples': ['7', 0], 'vae': ['1', 2]}}
    g['9'] = {'class_type': 'SaveImage',
              'inputs': {'images': ['8', 0], 'filename_prefix': prefix}}
    return g


def wf_zimage(pos, w, h, seed, denoise=1.0, init=None,
              prefix='comfy-zimage'):
    """Z-Image-Turbo GGUF（官方模板参数：8 步 cfg1 AuraFlow shift3）。
    cfg=1 负向无效；img2img 时 denoise<1。"""
    g = {'1': {'class_type': 'UnetLoaderGGUF',
               'inputs': {'unet_name': 'z-image-turbo-Q4_K_M.gguf'}},
         '2': {'class_type': 'ModelSamplingAuraFlow',
               'inputs': {'model': ['1', 0], 'shift': 3.0}},
         '3': {'class_type': 'CLIPLoader',
               'inputs': {'clip_name': 'qwen_3_4b_fp8_mixed.safetensors',
                          'type': 'lumina2', 'device': 'default'}},
         '4': {'class_type': 'CLIPTextEncode',
               'inputs': {'clip': ['3', 0], 'text': pos}},
         '5': {'class_type': 'ConditioningZeroOut',
               'inputs': {'conditioning': ['4', 0]}}}
    if init:
        g['10'] = {'class_type': 'LoadImage', 'inputs': {'image': init}}
        g['11'] = {'class_type': 'VAEEncode',
                   'inputs': {'pixels': ['10', 0], 'vae': ['8', 0]}}
        latent = ['11', 0]
    else:
        g['6'] = {'class_type': 'EmptySD3LatentImage',
                  'inputs': {'width': w, 'height': h, 'batch_size': 1}}
        latent = ['6', 0]
    g['7'] = {'class_type': 'KSampler',
              'inputs': {'model': ['2', 0], 'positive': ['4', 0],
                         'negative': ['5', 0], 'latent_image': latent,
                         'seed': seed, 'steps': 8, 'cfg': 1.0,
                         'sampler_name': 'res_multistep',
                         'scheduler': 'simple', 'denoise': denoise}}
    g['8'] = {'class_type': 'VAELoader',
              'inputs': {'vae_name': 'z_image_ae.safetensors'}}
    g['9'] = {'class_type': 'VAEDecode',
              'inputs': {'samples': ['7', 0], 'vae': ['8', 0]}}
    g['12'] = {'class_type': 'SaveImage',
               'inputs': {'images': ['9', 0], 'filename_prefix': prefix}}
    return g


# ---------------- 生成入口 ----------------

_last_model = None


def gen(out, pos, neg='', ckpt=None, zimage=False, w=None, h=None,
        seed=20260905, steps=None, cfg=None, sampler=None, scheduler=None,
        denoise=1.0, init=None, prefix='comfy', free_first=False):
    """生成一张图。参数缺省时取该底模的稳妥参数；换模型自动卸载。"""
    global _last_model
    if zimage:
        w, h = w or 768, h or 768
    else:
        d = CKPT_DEFAULTS.get(ckpt, {})
        w, h = w or d.get('w', 512), h or d.get('h', 512)
        steps = steps or d.get('steps', 20)
        cfg = cfg if cfg is not None else d.get('cfg', 7.0)
        sampler = sampler or d.get('sampler', 'euler_ancestral')
        scheduler = scheduler or d.get('scheduler', 'normal')

    model = 'zimage' if zimage else ckpt
    if free_first or (_last_model is not None and model != _last_model):
        print(f'       [comfy] 切换模型 {_last_model} -> {model}，先卸载',
              flush=True)
        free_models()
        time.sleep(2)
    _last_model = model

    init_name = _put_init(init) if init else None
    if init_name and (w, h):
        # 图生图的 latent 尺寸跟 init 走：先适配到目标生成尺寸
        im = Image.open(init)
        if im.size != (w, h):
            fit_canvas(im, w, h).save(os.path.join(INPUT_DIR, init_name))
    if zimage:
        graph = wf_zimage(pos, w, h, seed, denoise=denoise, init=init_name,
                          prefix=prefix)
    else:
        graph = wf_ckpt(ckpt, pos, neg, w, h, seed, steps, cfg, sampler,
                        scheduler, denoise=denoise, init=init_name,
                        prefix=prefix)
    t0 = time.time()
    imgs = wait_output(submit(graph))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    fetch(imgs[0], out)
    print(f'       [comfy] {os.path.basename(out)}  '
          f'{time.time() - t0:.0f}s  ({w}x{h} denoise={denoise})', flush=True)
    return out


# ---------------- init 图画布适配 ----------------

def fit_canvas(img, w, h):
    """保持长宽比缩进目标画布，四周用原图边缘 1px 拉伸补边
    （图生图 init 需固定尺寸；棚拍背景上下不同色时不会出硬边）。"""
    scale = min(w / img.width, h / img.height)
    im = img.resize((max(1, round(img.width * scale)),
                     max(1, round(img.height * scale))), hp._resample('LANCZOS'))
    rgb = img.convert('RGB')
    canvas = rgb.crop((0, 0, w, h))  # 占位
    canvas = Image.new('RGB', (w, h))
    x0, y0 = (w - im.width) // 2, (h - im.height) // 2
    canvas.paste(im, (x0, y0))
    if im.width < w:
        left = im.crop((0, 0, 1, im.height)).resize((x0, im.height))
        right = im.crop((im.width - 1, 0, im.width, im.height)
                        ).resize((w - x0 - im.width, im.height))
        canvas.paste(left, (0, y0))
        canvas.paste(right, (x0 + im.width, y0))
    if im.height < h:
        top = im.crop((0, 0, im.width, 1)).resize((im.width, y0))
        bot = im.crop((0, im.height - 1, im.width, im.height)
                      ).resize((im.width, h - y0 - im.height))
        canvas.paste(top, (x0, 0))
        canvas.paste(bot, (x0, y0 + im.height))
    return canvas


# ---------------- 帧级姿势词（frame 模式） ----------------

def _cycle(words, n):
    return [words[i % len(words)] for i in range(n)]


ROW_FRAMES = {
    'idle': lambda n: ['standing calmly, arms relaxed, facing viewer'] * n,
    'running-right': lambda n: _cycle([
        'walking to the right, right leg forward',
        'walking to the right, legs passing each other',
        'walking to the right, left leg forward',
        'walking to the right, legs passing each other',
    ], n),
    'waving': lambda n: _cycle([
        'standing, right arm raised high waving at the viewer',
        'standing, right arm raised waving, hand tilted',
        'standing, right arm lowered halfway',
        'standing, both arms relaxed down',
    ], n),
    'jumping': lambda n: [
        'slightly crouching, knees bent, ready to jump',
        'leaping into the air, both feet off the ground',
        'jumping high, knees tucked up',
        'falling, legs extended down',
        'landing softly, knees bent',
    ][:n] + ['landing softly, knees bent'] * max(0, n - 5),
    'failed': lambda n: _cycle([
        'standing, shoulders drooping, sad face',
        'slumping down, head lowered',
        'slumped, looking down',
        'slowly straightening up, still sad',
    ], n),
    'waiting': lambda n: ['leaning forward slightly, looking at the viewer '
                          'expectantly, hands clasped'] * n,
    'running': lambda n: ['standing in place, typing on an invisible '
                          'keyboard, focused'] * n,
    'review': lambda n: ['standing, holding a magnifying glass, inspecting '
                         'closely'] * n,
    # 睡觉姿势行（本项目扩展，占用图集第 6 行槽位）：单条姿势词 -> 全帧
    # 一致（同种子下直接命中图缓存），呼吸感由运行时微动补，防闪烁
    'sleep': lambda n: ['sleeping, lying curled up on the floor, eyes '
                        'closed, peaceful'] * n,
}

ROW_DENOISE = {'idle': 0.3, 'running-right': 0.45, 'waving': 0.45,
               'jumping': 0.5, 'failed': 0.45, 'waiting': 0.4,
               'running': 0.35, 'review': 0.35, 'sleep': 0.35}


def _single_frame(frame_png, w, h):
    """从一张生成图里取最大的角色连通域（RGBA，紧致裁剪）。"""
    frames = hp.extract_frames(Image.open(frame_png), 1)
    return frames[0]


# ---------------- 子命令 ----------------

def cmd_gen(args):
    gen(args.out, args.pos, args.neg, ckpt=args.ckpt, zimage=args.zimage,
        w=args.w, h=args.h, seed=args.seed, denoise=args.denoise,
        init=args.init, prefix='comfy-eval')
    if args.base_out:
        frame = _single_frame(args.out, args.w or 512, args.h or 512)
        if frame is None:
            raise SystemExit('生成图里没抠出角色，看原图再调提示词')
        frame.save(args.base_out)
        print(f'[ok]    抠好的角色帧 -> {args.base_out}')


def cmd_atlas(args):
    run_dir = os.path.join(hp.OUT_DIR, args.id)
    build_dir = os.path.join(run_dir, 'build')
    os.makedirs(build_dir, exist_ok=True)

    base = Image.open(args.base).convert('RGB')
    w = args.w or CKPT_DEFAULTS.get(args.ckpt, {}).get('w', 512)
    h = args.h or CKPT_DEFAULTS.get(args.ckpt, {}).get('h', 512)
    identity = args.identity or ''
    rows = [r.strip() for r in args.rows.split(',') if r.strip()]
    strip_rows = {r.strip() for r in args.strip_rows.split(',') if r.strip()}
    if args.snap:
        hp.REMOVE_KW = {'snap': args.snap}
    wanted = {name: (row, n, _d) for name, row, n, _d in hs.ROW_SPECS}
    # 'sleep' 是本项目扩展：借用图集第 6 行槽位放睡觉姿势行（运行时
    # pet.json 的 sleep_row 指过去）；init 用 --sleep-base（睡姿定形象）
    wanted['sleep'] = (6, hs.FRAME_COUNT[6], None)

    rows_cells = {}
    for name in rows:
        if name == 'running-left' or name not in wanted:
            continue
        row, n, _d = wanted[name]
        slots = []
        if args.mode == 'strip' or name in strip_rows:
            out = os.path.join(build_dir, f'strip_{name}.png')
            if not os.path.exists(out) or args.force:
                action = hp.ROW_ACTIONS[name]
                pos = (f'{identity} sprite sheet, animation sheet with exactly '
                       f'{n} frames of the same full character in one horizontal '
                       f'row, evenly spaced, same size, same ground line, '
                       f'white background, no text, no grid. '
                       f'Action: {action}.')
                gen(out, pos, args.neg, ckpt=args.ckpt, zimage=args.zimage,
                    w=w, h=h, seed=args.seed, prefix=f'comfy-strip')
            slots = hp.extract_frames(Image.open(out), n)
        else:
            if name == 'sleep':
                if not args.sleep_base:
                    raise SystemExit("rows 含 sleep 时需要 --sleep-base"
                                     "（睡姿定形象图）")
                base_img = Image.open(args.sleep_base).convert('RGB')
            else:
                base_img = base
            init_src = os.path.join(build_dir, f'init_{name}.png')
            if not os.path.exists(init_src) or args.force:
                fit_canvas(base_img, w, h).save(init_src)
            # 同一行共用一个种子：同 init + 同种子 + 低重绘 => 衣服细节
            # 逐帧锁定，只有姿势词带来的微差（防"一闪一闪"）
            row_seed = args.seed + row * 997
            for i, frag in enumerate(ROW_FRAMES[name](n)):
                out = os.path.join(build_dir, f'frame_{name}_{i}.png')
                if not os.path.exists(out) or args.force:
                    pos = f'{identity}, full body, {frag}' if identity else \
                          f'full body, {frag}'
                    gen(out, pos, args.neg, ckpt=args.ckpt,
                        zimage=args.zimage, w=w, h=h,
                        seed=row_seed,
                        denoise=args.denoise or ROW_DENOISE[name],
                        init=init_src, prefix='comfy-frame')
                slots.append(_single_frame(out, w, h))
                print(f'       帧 {i + 1}/{n} 抠出'
                      f'{"成功" if slots[-1] else "失败(用上一帧补)"}', flush=True)
        rows_cells[row] = hp.place_row(slots, n, erode=args.erode)

    if wanted.get('running-right', (None,))[0] == 1 and 1 in rows_cells:
        rows_cells[2] = hp.mirror_cells(rows_cells[1])
        print('[row]   running-left: 由 running-right 逐帧镜像派生')

    atlas = hp.compose_atlas(rows_cells)
    for p in hp.validate_atlas(atlas, strict=False):
        print(f'[warn]  {p}')
    hp.qa_outputs(atlas, run_dir, args.id)
    hp.write_package(atlas, args.id, args.name, args.desc or '', run_dir)
    if 6 in rows_cells:
        meta_path = os.path.join(run_dir, 'pet.json')
        meta = json.load(open(meta_path, encoding='utf-8'))
        meta['sleep_row'] = 6
        json.dump(meta, open(meta_path, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
    print(f'[done]  {run_dir}{os.sep}pet.json + spritesheet.png（QA 见 qa/）')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='cmd', required=True)

    g = sub.add_parser('gen', help='生成单张图（评估/挑 base）')
    g.add_argument('--out', required=True)
    g.add_argument('--pos', required=True)
    g.add_argument('--neg', default='')
    g.add_argument('--ckpt', help='checkpoint 文件名')
    g.add_argument('--zimage', action='store_true', help='用 Z-Image GGUF')
    g.add_argument('--w', type=int)
    g.add_argument('--h', type=int)
    g.add_argument('--seed', type=int, default=20260905)
    g.add_argument('--denoise', type=float, default=1.0)
    g.add_argument('--init', help='图生图的 init 图（复制进 ComfyUI/input）')
    g.add_argument('--base-out', help='同时抠出角色帧存到该路径（当 base 用）')
    g.set_defaults(fn=cmd_gen)

    a = sub.add_parser('atlas', help='生成图集桌宠包 hatched/<id>/')
    a.add_argument('--id', required=True)
    a.add_argument('--name', required=True)
    a.add_argument('--desc', default='')
    a.add_argument('--base', required=True, help='定形象图（RGB 生成图即可）')
    a.add_argument('--identity', default='',
                   help='身份描述（拼进每帧提示词；danbooru tag 串）')
    a.add_argument('--neg', default='')
    a.add_argument('--ckpt', help='checkpoint 文件名')
    a.add_argument('--zimage', action='store_true')
    a.add_argument('--rows', default='idle,running-right,waving,jumping',
                   help='逗号分隔的行名（默认桌宠用到的 4 行）')
    a.add_argument('--mode', choices=['frame', 'strip'], default='frame')
    a.add_argument('--strip-rows', default='',
                   help='在 --mode frame 基础上，这些行改用条带模式'
                        '（逗号分隔，如 running-right,jumping）')
    a.add_argument('--denoise', type=float,
                   help='frame 模式统一重绘幅度（缺省按行默认）')
    a.add_argument('--erode', type=int, default=2,
                   help='去白边：缩放前蒙版向内腐蚀的源图像素数（0 关闭）')
    a.add_argument('--sleep-base',
                   help="睡姿定形象图（rows 含 sleep 时必须；睡姿无法从"
                        "站姿 i2i 变出来，先单独 txt2img 一张）")
    a.add_argument('--snap', type=int,
                   help="绿幕流程：背景吸附半径（推荐 80；白底流程不要开，"
                        "会把浅色服装一起吸掉）")
    a.add_argument('--w', type=int)
    a.add_argument('--h', type=int)
    a.add_argument('--seed', type=int, default=20260905)
    a.add_argument('--force', action='store_true')
    a.set_defaults(fn=cmd_atlas)

    args = parser.parse_args()
    args.fn(args)


if __name__ == '__main__':
    main()
