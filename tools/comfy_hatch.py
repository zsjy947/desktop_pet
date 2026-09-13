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
            denoise=1.0, init=None, prefix='comfy',
            lora=None, lora_strength=1.0):
    """SD1.5/SDXL checkpoint 的文生图 / 图生图（init 给定时）最小图。
    lora 给定时叠加 LoraLoader（如 Hyper-SD 蒸馏 LoRA 提速）。"""
    g = {'1': {'class_type': 'CheckpointLoaderSimple',
               'inputs': {'ckpt_name': ckpt}}}
    model, clip = ['1', 0], ['1', 1]
    if lora:
        g['11'] = {'class_type': 'LoraLoader',
                   'inputs': {'lora_name': lora,
                              'strength_model': lora_strength,
                              'strength_clip': lora_strength,
                              'model': model, 'clip': clip}}
        model, clip = ['11', 0], ['11', 1]
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
              'inputs': {'clip': clip, 'text': pos}}
    g['5'] = {'class_type': 'CLIPTextEncode',
              'inputs': {'clip': clip, 'text': neg}}
    g['7'] = {'class_type': 'KSampler',
              'inputs': {'model': model, 'positive': ['4', 0],
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
        denoise=1.0, init=None, prefix='comfy', free_first=False,
        lora=None, lora_strength=1.0):
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

    model = ('zimage' if zimage else ckpt) + (f'+{lora}' if lora else '')
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
                        prefix=prefix, lora=lora,
                        lora_strength=lora_strength)
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

# trick 行走 txt2img（--trick-txt2img）：i2i 被站姿 init 锁死，画不出
# 放电/冲刺这类带特效的大动作；正统宝可梦身份靠 danbooru 本体 tag
# 天然稳定，trick 帧直接文生图（绿幕底同款背景词）。
# 本体含绿色/含白的新叶喵类角色用 --trick-bg 换键控色（如蓝幕）。
TRICK_BG = ('centered, large in frame, uniform flat solid bright green '
            'background, flat chroma key green screen background, no '
            'gradient, no vignette, no shadow, no text')


def _strip_ground_line(img, bottom=0.45, ratio=1.5):
    """裁掉连接在脚下的地线（txt2img trick 帧常画一条贯穿地线，与脚
    连通被一起抠出）。底部带区里"行宽 ≫ 中位行宽"的行是地线行：
    地线行超出角色列域的像素裁掉，角色本体（含尾巴等横向部件）保留；
    脚底正下方贴着脚的短线留在线内，缩进格子里读作地面阴影。"""
    import numpy as np
    a = np.array(img)
    m = a[..., 3] > 0
    ys = np.where(m.any(axis=1))[0]
    if not len(ys):
        return img
    y0, y1 = ys[0], ys[-1]
    band = y0 + int((y1 - y0) * (1 - bottom))
    widths = m[band:, :].sum(axis=1)
    pos = widths[widths > 0]
    if not len(pos):
        return img
    med = np.median(pos)
    sel = np.zeros_like(m)
    sel[:band, :] = m[:band, :]
    sel[band:, :] = m[band:, :] & (widths <= med * ratio)[:, None]
    cols = np.where(sel.any(axis=0))[0]
    if not len(cols):
        return img
    keep = np.zeros(m.shape[1], dtype=bool)
    keep[cols[0]:cols[-1] + 1] = True
    m[band:, :] &= keep[None, :]
    a[..., 3] = np.where(m, 255, 0)
    out = hp.zero_transparent_rgb(Image.fromarray(a, 'RGBA'))
    bbox = out.getbbox()
    return out.crop(bbox) if bbox else out


def _single_frame(frame_png, w, h, trim_ground=False):
    """从一张生成图里取最大的角色连通域（RGBA，紧致裁剪）。"""
    frames = hp.extract_frames(Image.open(frame_png), 1)
    f = frames[0]
    if f is not None and trim_ground:
        f = _strip_ground_line(f)
    return f


# ---------------- 子命令 ----------------

def cmd_gen(args):
    gen(args.out, args.pos, args.neg, ckpt=args.ckpt, zimage=args.zimage,
        w=args.w, h=args.h, seed=args.seed, steps=args.steps,
        denoise=args.denoise, init=args.init, prefix='comfy-eval',
        lora=args.lora, lora_strength=args.lora_strength)
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
    # 动作行换键控色：本体含绿色（新叶喵）绿幕会吃掉本体，换蓝幕；
    # TRICK_BG 在 gen 调用点实时读取，模块级覆盖即可
    global TRICK_BG
    if args.trick_bg:
        TRICK_BG = args.trick_bg
    wanted = {name: (row, n, _d) for name, row, n, _d in hs.ROW_SPECS}
    # 'sleep' 是本项目扩展：借用图集第 6 行槽位放睡觉姿势行（运行时
    # pet.json 的 sleep_row 指过去）；init 用 --sleep-base（睡姿定形象）
    wanted['sleep'] = (6, hs.FRAME_COUNT[6], None)
    # 'trick7'/'trick8' 是宝可梦专属动作行（借用第 7/8 行槽位；桌宠本来
    # 不用 Codex 的 running/review 行）。帧姿势词用 | 分隔，不足循环复用
    for key, spec in (('trick7', args.trick7), ('trick8', args.trick8)):
        if not spec:
            continue
        words = [w.strip() for w in spec.split('|') if w.strip()]
        if not words:
            raise SystemExit(f'--{key} 姿势词为空')
        ROW_FRAMES[key] = (lambda ws: lambda n: _cycle(ws, n))(words)
        ROW_DENOISE[key] = args.trick_denoise or 0.5
        wanted[key] = (7 if key == 'trick7' else 8,
                       hs.FRAME_COUNT[7 if key == 'trick7' else 8], None)

    rows_cells = {}
    for name in rows:
        if name == 'running-left' or name not in wanted:
            continue
        row, n, _d = wanted[name]
        txt2img = False
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
                    w=w, h=h, seed=args.seed, steps=args.steps,
                    prefix=f'comfy-strip',
                    lora=args.lora, lora_strength=args.lora_strength)
            slots = hp.extract_frames(Image.open(out), n)
        else:
            if name == 'sleep':
                if not args.sleep_base:
                    raise SystemExit("rows 含 sleep 时需要 --sleep-base"
                                     "（睡姿定形象图）")
                base_path = args.sleep_base
            else:
                base_path = args.base
            base_img = Image.open(base_path).convert('RGB')
            # init 文件名带 base mtime：换了 base 定形象图自动失效重建，
            # 否则会一直用旧 init 图生图（换 base 不生效的坑）
            init_src = os.path.join(
                build_dir, f'init_{name}_{int(os.path.getmtime(base_path))}.png')
            if not os.path.exists(init_src) or args.force:
                fit_canvas(base_img, w, h).save(init_src)
            # 同一行共用一个种子：同 init + 同种子 + 低重绘 => 衣服细节
            # 逐帧锁定，只有姿势词带来的微差（防"一闪一闪"）。
            # 只生成去重后的姿势词：重复词的帧与前面完全同参数，必然是
            # 同一张图——但 ComfyUI 的节点缓存是单槽的（中间插了别的词
            # 就被顶掉），重跑注定全价；直接克隆补位，结果等价还省钱。
            row_seed = args.seed + row * 997
            frags = ROW_FRAMES[name](n)
            uniq = len(dict.fromkeys(frags))
            slots = []
            # trick 行的 txt2img 变体：帧文件名带 t 后缀（与 i2i 版互不
            # 覆盖，两种模式可共存/回退）
            txt2img = args.trick_txt2img and name in ('trick7', 'trick8')
            for i, frag in enumerate(frags[:uniq]):
                out = os.path.join(
                    build_dir,
                    f'frame_{name}_{"t" if txt2img else ""}{i}.png')
                if not os.path.exists(out) or args.force:
                    if txt2img:
                        pos = f'{identity}, solo, {frag}, {TRICK_BG}'
                        gen(out, pos, args.neg, ckpt=args.ckpt,
                            zimage=args.zimage, w=w, h=h, seed=row_seed,
                            steps=args.steps, denoise=1.0, prefix='comfy-frame',
                            lora=args.lora, lora_strength=args.lora_strength)
                    else:
                        pos = (f'{identity}, full body, {frag}'
                               if identity else f'full body, {frag}')
                        gen(out, pos, args.neg, ckpt=args.ckpt,
                            zimage=args.zimage, w=w, h=h,
                            seed=row_seed, steps=args.steps,
                            denoise=args.denoise or ROW_DENOISE[name],
                            init=init_src, prefix='comfy-frame',
                            lora=args.lora, lora_strength=args.lora_strength)
                slots.append(_single_frame(out, w, h, trim_ground=txt2img))
                print(f'       帧 {i + 1}/{uniq} 抠出'
                      f'{"成功" if slots[-1] else "失败(用上一帧补)"}', flush=True)
            # 重复姿势词的槽位克隆补位（同图克隆，等价于缓存命中）
            slots = [slots[i % len(slots)] for i in range(n)]
        rows_cells[row] = hp.place_row(slots, n, erode=args.erode,
                                       normalize=txt2img if name in (
                                           'trick7', 'trick8') else False)

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
    if args.extra_json:
        meta_path = os.path.join(run_dir, 'pet.json')
        meta = json.load(open(meta_path, encoding='utf-8'))
        meta.update(json.loads(args.extra_json))
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
    g.add_argument('--lora', help='叠加的 LoRA（如 Hyper-SD 蒸馏提速）')
    g.add_argument('--lora-strength', type=float, default=1.0)
    g.add_argument('--steps', type=int, help='采样步数（覆盖底模默认）')
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
    a.add_argument('--trick7', help='宝可梦动作行7：帧姿势词，用 | 分隔')
    a.add_argument('--trick8', help='宝可梦动作行8：帧姿势词，用 | 分隔')
    a.add_argument('--trick-denoise', type=float,
                   help='动作行重绘幅度（缺省 0.5）')
    a.add_argument('--trick-txt2img', action='store_true',
                   help='动作行改 txt2img（i2i 画不出放电/冲刺等大动作时'
                        '用；帧文件与 i2i 版互不覆盖）')
    a.add_argument('--trick-bg',
                   help='动作行 txt2img 的背景词（本体含绿色/白色时换'
                        '"uniform flat solid bright blue background, flat '
                        'chroma key blue screen background"）')
    a.add_argument('--lora', help='叠加的 LoRA（如 Hyper-SD 蒸馏提速）')
    a.add_argument('--lora-strength', type=float, default=1.0)
    a.add_argument('--extra-json',
                   help='附加 pet.json 字段（JSON，如 species/tricks）')
    a.add_argument('--w', type=int)
    a.add_argument('--h', type=int)
    a.add_argument('--steps', type=int, help='采样步数（覆盖底模默认）')
    a.add_argument('--seed', type=int, default=20260905)
    a.add_argument('--force', action='store_true')
    a.set_defaults(fn=cmd_atlas)

    args = parser.parse_args()
    args.fn(args)


if __name__ == '__main__':
    main()
