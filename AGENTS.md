# AGENTS.md — 桌面宠物项目交接文档

给在新电脑/新会话上接手本项目的 agent（或未来的自己）：本文档浓缩了
整个开发与调优过程中的架构、构建流程、踩坑与验证方法。改代码前先读完。

## 1. 项目概览

Python 标准库（tkinter）桌面宠物，运行时**零第三方依赖**；图片精灵的
生成在开发期完成（pillow + rembg）。多显示器漫游、置顶（不被任务栏
遮挡）、右键菜单弹出在宠物头顶（可微盖）。角色为二次元向，当前
7 个：橘猫 + 图集少女×4（二乃/莉莉艾/小光/露莎米奈，NoobAI 本地
生成）+ 芒果图集猫 + 竹兰照片精灵。三次元明星 6 位已按需求移除
（2026-09-05）；由比滨结衣也整个移除（和服版 3 次生成都没命中粉色
和服锚点，按规则跳过，后续可加 (pink kimono:1.3) 类强色锚重试）；
竹兰的图集版未命中锚点（大衣穿身 vs 披肩）已删、回退照片精灵。
图集与旧角色同 id 时图集**替换**旧角色（渲染走图集、名字台词沿用旧
preset，见 pet_window._registry）。
**绿幕流程（浅色服装角色必用）**：白底+空腔色距判罚会把白裙/白帽
当成"封闭浅色空腔"大面积抠掉（莉莉艾首版白裙全没），色距法对白色系
设计不成立。改为生图直接出**纯绿幕底**（prompt: solid bright green
background, flat chroma key green screen），键控天然区分角色与背景，
腿间封闭绿块按色直接扣。remove_bg 加 snap 吸附参数（绿幕标定 80：
先把你色距在 snap 内的像素归一化到背景色再键控，抗背景渐变/条带；
白底流程不要开）。atlas 用 `--snap 80 --erode 3`（erode 3 切绿边）。
注意 atlas 单行重跑必须传全行清单，否则其余行会被清空。
交互按物种分：人类角色 = 👋打招呼（waving 行）/ 🎁送礼物（excited
状态→图集跳跃行 + 爱心）/ 💬聊聊天；猫科（橘猫/芒果，pet.json 加
"species":"cat"）保留 🍪喂食 / 🖐摸摸头。双击同理（人=打招呼，猫=摸
头）。气泡为矩形浅蓝半透明方框（边框 #5DADE2、底 #D6EAF8 走
pet/glass.xbm 87.5% 镂空露出键色=真透桌面），无尾巴箭头，对话区压
矮到两行贴住头顶。

```
main.py                    入口（Windows DPI 感知）
run.bat                    双击启动（pythonw）
pet/
  config.py                全局参数：键色、速度、橘猫配色与台词
  characters.py            内置角色库：外观预设（Canvas 少女）+ 台词包
  custom.py                自定义角色注册表（custom_characters.json，不入库）
  drawutil.py              共享绘制：镜像助手 / 气泡（独立对话区） / 粒子
  sprites.py               橘猫 Canvas 逐帧绘制
  girl_sprites.py          Q 版少女参数化绘制（图片帧缺失时的回落）
  photo_sprites.py         图片精灵播放器（assets/ 帧目录）
  hatch_sprites.py         hatch-pet 图集桌宠播放器（hatched/ 图集包）
  behavior.py              状态机 idle/walk/sleep/drag/fall/happy/excited
  screens.py               EnumDisplayMonitors + 工作区（GetMonitorInfoW）
  pet_window.py            主窗口：透明置顶、右键菜单、角色切换、主循环
tools/
  build_sprites.py         高清精灵构建（抠图→清理→伪姿势帧，240px）
  hatch_pet.py             hatch-pet 生成管线（z-image-turbo 生姿势→图集）
  comfy_hatch.py           本地 ComfyUI 生图后端（gen 单张 / atlas 图集组装）
  add_character.py         角色添加接口（CLI / 可编程）
  character_server.py      本地上传网页 http://127.0.0.1:8765
tests/test_smoke.py        19 项冒烟测试（会短暂弹窗）
assets/                    高清精灵帧（入库，5 个动漫角色；三次元与 yui 已移除）
hatched/<id>/              图集桌宠包：pet.json + spritesheet.png（入库）；
                           build/ 与 qa/ 为生成中间产物（不入库）
localgen/                  本地生图评估产物与报告（REPORT.md，**不入库**）
reference/pictures/        用户提供的参考图（**不入库**）
custom_characters.json     接口生成的自定义角色（**不入库**）
~/.desktop_pet.json        用户上次选择的角色（运行时写入）
```

## 2. 新电脑环境搭建

1. Python 3.10+（tkinter 必须有；Windows 自带）。
2. 运行宠物：`python main.py` 或 `run.bat`。仅此时不需要任何第三方库。
3. 开发/构建才需要：
   ```bash
   pip install pillow numpy requests "rembg[cpu]"
   ```
   （hatch_pet.py 生成管线只需 pillow+numpy+requests；rembg 仅
   build_sprites/add_character 抠参考图照片时用到。）
4. **rembg 模型下载**：首次调用会从 GitHub 下载 onnx 模型；若遇
   SSL 证书错误（常见于企业代理），用 curl 绕过并放到 rembg 的模型目录：
   ```bash
   mkdir -p ~/.u2net
   curl -kL -o ~/.u2net/u2net.onnx \
     https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net.onnx
   curl -kL -o ~/.u2net/isnet-anime.onnx \
     https://github.com/danielgatis/rembg/releases/download/v0.0.0/isnet-anime.onnx
   ```
   模型选择：真人照片 `u2net`，动漫插画 `isnet-anime`。
5. 测试：`python -m unittest tests.test_smoke -v`（19 项；弹一下测试窗口属正常）。

## 3. 构建与角色流程

- **高清精灵**：`python tools/build_sprites.py`（`--only nino` 单建，
  `--sheet` 出拼图预览）。管线：rembg 抠图 → 丢弃小连通域（背景杂物，
  阈值 18% 面积）→ 收缩 1px 过渡带 + alpha 二值化 + 边缘渗色去黑晕 →
  缩放 240px → 各状态伪姿势帧（朝右/朝左两套）+ manifest.json。
- **hatch-pet 图集桌宠**（hatch-pet 分支）：借鉴 OpenAI Codex 的
  hatch-pet skill，图集契约与其一致（1536x1872 = 8 列 x 9 行，格
  192x208，行序固定 idle/running-right/running-left/waving/jumping/
  failed/waiting/running/review，未用格全透明）。
  `python tools/hatch_pet.py --id mango --name 芒果 --prompt '...' [--style sticker]`：
  z-image-turbo 先出 base 定形象（形象描述原样复述进每条提示当"身份锁"，
  该 API 无参考图输入），再逐行生成姿势条带（running-left 由
  running-right 逐帧镜像派生），确定性管线抠底→连通域检帧→行内统一
  缩放（防帧间大小跳）→合成图集→契约校验→QA 联络表/GIF→打包
  `hatched/<id>/`。重跑安全：build/ 下条带已存在即跳过（--force 重生）。
  运行时 pet/hatch_sprites.py 按状态映射行：idle→idle、walk→
  running-right/left、happy→waving、fall/drag/excited→jumping、
  sleep→sleep_row（pet.json 指定，如第 6 行；未指定回落 idle 第 0
  帧）；waiting/running/review 为 Codex 应用专属行，桌宠暂不用。
  `--import-atlas x.webp` 可导入 Codex 孵化的现成图集。
- **本地生图替换（2026-09-05）**：`tools/comfy_hatch.py` 把生图源换成本地
  ComfyUI（需先启动 `D:\AAA_code\python\ComfyUI\启动ComfyUI.bat`，API
  http://127.0.0.1:8188）。`gen` 子命令出单张（`--ckpt` 选底模 /
  `--zimage` 用 Z-Image GGUF / `--init`+`--denoise` 图生图）；
  `atlas` 子命令以 base 图逐帧图生图组装 `hatched/<id>/`（行规格、抠底、
  合成、QA 全复用 hatch_pet）。已上线 `nino`（白底绿幕混合）与
  `lillie`/`dawn`/`lusamine`（绿幕流程）图集，`guan`（写实向）已随
  三次元移除，评估与配方见 `localgen/REPORT.md`。实测**逐帧
  图生图完胜条带**（本地模型同样不听"一行 n 帧"版式指令）；出图时间
  与分辨率无关（权重流式是瓶颈），直接用最好质量；图生图的 latent
  尺寸跟 init 走（先 fit 再编码，gen 已内置）；写实图背景靠 rembg
  抠底换纯色，动漫图参考图 i2i 0.6 直接风格化（背景杂物会被甩掉）。
- **添加角色**：
  - 网页：`python tools/character_server.py` → http://127.0.0.1:8765
  - CLI：`python tools/add_character.py --image x.png --id mychar --name 名字
    --talk '台词'`（透明底 PNG 免抠图、免装 rembg）
  - 产物：`assets/<id>/` + `custom_characters.json` 条目；宠物右键菜单
    **重新打开时**刷新（不用重启）。删除角色 = 删 json 条目 + 删 assets 目录。

## 4. 关键约束与踩坑（务必记住）

**透明窗口**
- 透明用 `-transparentcolor`（KEY_COLOR=#010101）键色方案：alpha 不是
  二值的像素会先与近黑键色混合再上屏 → 暗边。**所有精灵帧的 alpha 必须
  二值化**，并做边缘渗色（rembg 输出的 alpha 是软 matte，几乎没有 255，
  且外围 RGB 混着背景色——直接缩放会有背景色晕）。
- 背景杂物（照片里的台灯/羽毛/悬空伞碎片）rembg 会一起抠出来 →
  按连通域面积过滤，阈值 18%（台灯实测占比 14.2%，阈值太小漏放行）。

**右键菜单（Windows）**
- `menu.tk_popup` 会阻塞直到菜单关闭，但 `after` 定时器在菜单打开期间
  **照常触发**；主循环里 `_menu_open` 为真时要跳过窗口移动/置顶压制，
  否则每帧 SetWindowPos 会把刚弹出的菜单挤掉（实测踩坑）。
- 菜单锚定：底边压住对话区底边并**微盖宠物头顶**（15% 边长，2026-09-06
  按用户要求从"窗顶上方"下移拉近）。高度按 26px/项估算（实测 ~22px，
  宁大勿小——估小了菜单会沉到宠物后面被键色窗口盖住）。

**精灵帧**
- tkinter 的 PhotoImage **不能运行时翻转/旋转** → 所有镜像与姿势变换
  在构建期烘焙（每状态 [朝右×N, 朝左×N]）。
- 帧必须铺满整个窗口画布（240×240），运行时 `create_image` 整帧贴。
- 每张参考图只有一个姿势；走路=倾斜/剪切段、睡觉=压扁蹲姿是被逼的
  伪姿势。真·多姿势需要 Stable Diffusion + ControlNet(OpenPose) 或
  Live2D（后者与 tkinter 集成不现实）。

**对话气泡**
- 气泡画在窗口顶部独立加高的对话区画布（`cv_bubble`），**永不遮挡
  人物**；矩形无尾巴，菜单锚定压住对话区底边（可微盖宠物头顶）。

**落地高度（跨机器自适应）**
- 气泡改造后窗口 = 对话区 + 宠物区，**脚底在窗口底边**。地面必须取
  显示器**工作区**（`GetMonitorInfoW` 的 rcWork，`EnumDisplayMonitors`
  只给整屏矩形）底边，并把窗口底边对齐过去：`地面 = 工作区底边 -
  (size + 对话区高)`。曾按"窗口顶 = 整屏底 - size"落位，脚底沉到屏幕外
  约一个对话区高度（125% DPI 下 111px，整只掉出屏幕）；低分屏沉得少看
  不出来，换台电脑就露馅——落地必须按工作区自适应，不能写死。
- 拖进任务栏区域（地面以下）松手要在 `_on_release` 里贴回地面站好，
  不能让宠物留在屏幕外/被任务栏挡住。

**hatch-pet 生成（hatch-pet 分支）**
- 文生图模型**不听版式指令**：提示词写"单行横排 n 帧"，z-image-turbo
  实测画成 4x3 网格（好在形象一致性不错）→ 确定性切帧不能按等分槽位
  切，必须抠底后按连通域检测每个角色、行优先排序取帧（extract_frames）。
- 无参考图输入可用，行与行之间身份会有漂移；行内一致性远好于行间。
  行内统一缩放防帧间大小跳；不用的行（failed/review 实测偏大/偏小）
  漂移可容忍，缺行运行时回落 idle（available_rows 写进 pet.json）。
- tkinter 不认 webp：图集落 PNG；运行时用 tk 命令 `copy -from` 从大图
  裁格（Python 3.12 的 `PhotoImage.copy()` 不带参数），不必拆小文件。
- 透明像素 RGB 必须清零（与键色窗口同一硬性要求，hatch-pet 契约的
  transparency invariant 也是这条）。

**UI 预览/自动化截图**
- 外部进程驱动宠物 UI 时，驱动脚本必须自己 `SetProcessDpiAwareness(1)`
  （main.py 的设置不随 import 生效）：tk 坐标在 125% 缩放下会被虚拟化
  成 1/1.25，外部按物理坐标截图全部扑空。
- 杀宠物进程别用 `taskkill /IM python.exe`——会把 ComfyUI 等一并杀掉
  （实测踩过：图集生成中途暴毙）。按 PID 或命令行过滤杀。
- tk_popup 菜单可在驱动进程里用假 event 直接调 `_on_menu` 打开，
  不必模拟鼠标右键（键色透明区点击会穿透）。
- 键色窗口上的"半透明"用 Canvas stipple（gray75）实现：镂空点露出
  键色背景=桌面，等效 75% 不透明，无需分层窗口。
- hatch 图集白边：源图边缘"人物与白底反锯齿混合像素"会整体保留成白
  描边，`hatch_pet.place_row(erode=2)` 在源分辨率上腐蚀蒙版去除
  （实测近白边界像素 89% -> 4%）。

**抠图空腔与帧连贯（2026-09-06）**
- remove_bg：2x2 块洪泛 + **封闭近背景色空腔判背景**（两腿间/臂弯被
  人物围住的底色洪泛到不了）。阈值 0.33*tol 实测标定：真底色空腔色距
  ~0-11，人物内部浅肤/阴影空腔 ~19-27（判错会破大腿/胸口）。
- 帧连贯防闪烁：同一行共用种子 + 低重绘（idle 0.3/行走挥手 0.45/
  跳 0.5），行内帧差从均值 4.17 降到 0.89；idle 全同帧，呼吸感由
  运行时 draw_frame 的 1px 正弦微动补。
- 睡觉姿势行：借用图集第 6 行槽位（hatch-pet 契约不变），pet.json
  `"sleep_row": 6` + available_rows 含 6 时播睡觉姿势，否则回落
  idle 第 0 帧定格。睡姿 base 单独 txt2img（站姿 i2i 变不出躺姿），
  灰渐变底图生图刷不白，直接 rembg(isnet-anime) 抠出贴纯白底。
- 气泡自定义透明度：canvas stipple 只认内建名或 "@文件" 语法，
  BitmapImage 的 data= 在本机 Tk 解析失败、image 名也不注册为
  bitmap——用 pet/glass.xbm（8x8 每行 1 透点=87.5%）+ "@路径"。

**角色对号**
- 批量看参考图会把照片和人对错号（毛晓彤/王玉雯踩过）：核对时必须用
  **带文件名标签的拼图**，不要凭记忆。

## 5. 验证方法（GUI 项目的冒烟）

1. 单元测试：`python -m unittest tests.test_smoke -v`。
2. **截图冒烟**（验证透明、置顶、真实观感）：
   - Python 侧先 `SetProcessDpiAwareness(1)`（与 main.py 一致）；
   - 用 PowerShell 截屏，**两侧都要 DPI 感知**，否则高分屏缩放下
     截图区域错位（200% 缩放会截到放大错位的区域）：
     ```powershell
     Add-Type -TypeDefinition 'using System.Runtime.InteropServices;
       public class Dpi { [DllImport("shcore.dll")]
       public static extern int SetProcessDpiAwareness(int v); }'
     [Dpi]::SetProcessDpiAwareness(2)
     Add-Type -AssemblyName System.Drawing
     $bmp = New-Object System.Drawing.Bitmap(w, h)
     $g = [System.Drawing.Graphics]::FromImage($bmp)
     $g.CopyFromScreen(x, y, 0, 0, $bmp.Size); $bmp.Save('out.png')
     ```
   - 菜单自动化：后台起宠物 → `SendKeys '{DOWN n}{ENTER}'` 选择角色
     （注意 Windows 菜单默认高亮第 0 项）；`SendWait('{ESC}')` 关菜单。
   - `tk_popup` 打开期间定时器仍触发 → 外部进程可截屏；主进程会被
     菜单阻塞，关闭菜单后才继续。
3. **写盘验证**：脚本里写入的文件要用**独立的后续命令**确认存在
   （防止沙箱/杀软等把写入吞掉——本会话踩过：接口测试写 assets/
   后立即断言通过与否受此干扰，排查半天，根因却是路径拼接 bug +
   目录漏建；两者都修后才稳定）。

## 6. Git 布局

- `main`：落地高度自适应 + 气泡独立对话区 + 角色添加接口 + AGENTS.md
- `hatch-pet`：图集桌宠（生成管线 + 播放器 + 芒果/二乃/莉莉艾/小光/
  露莎米奈图集 + 本地 ComfyUI 生图后端 + 交互/气泡/菜单重构），基于 main
- `pixel-art` 已废弃删除（2026-09，本地与远程均已删；像素方案用户不满意）
- 不入库：`reference/`、`custom_characters.json`、`tmp_*`、
  `hatched/*/build|qa/`、用户偏好
- 提交历史（概要）：
  1. `49ea981` 角色系统（Canvas Q 版少女 + 台词包 + 菜单上方弹出）
  2. `d6ebbf8` 高清图片精灵模式（构建管线 + 运行时播放器）
  3. `3af9822` 气泡独立对话区
  4. `41b3fcb` 角色添加接口（CLI + 网页）
  5. `8d4cdf6`（main）落地高度自适应：脚底对齐工作区底边
  6. （hatch-pet）hatch-pet 图集桌宠：生成管线 + 播放器
  7. （hatch-pet）本地 ComfyUI 绿幕流程：图集替换 4 角色 + 交互重构
     + 矩形半透明气泡 + 菜单拉近 + 去白边/空腔/防闪烁

## 7. 后续方向（未做）

- 三次元（真人）路线**已暂停**：2026-09-05 按需求把 6 位明星角色从宠物
  移除（characters.py preset + assets/ 帧 + hatched/guan 图集一起删），
  reference/pictures 里的真人照片保留；等找到更满意的写实生图方法再回加。
  评估数据与配方都在 localgen/REPORT.md。动漫侧：lillie/dawn/
  lusamine 已绿幕流程上线；yui（粉色和服锚点 3 连未中）与 cynthia
  （大衣锚点未中）暂缓，重试需强色/服装锚（如 (pink kimono:1.3)、
  fur-trimmed coat draped on shoulders）。
- 真·多姿势/更强一致性：给 hatch 管线接支持参考图的生图（image editing /
  IP-Adapter）或 ControlNet OpenPose（SD1.5 版 1.4GB，4GB 显存可跑），
  消除行间漂移、做出真步态；动漫形象一致性较好，真人会漂移。
- 逐像素透明窗口：换 PySide6（`WA_TranslucentBackground`）或 ctypes
  UpdateLayeredWindow（可零运行时依赖但气泡文字需自绘合成）。
- hatch 行的深度利用：waiting（等人）接"有话对你说"、running（专注
  干活）接工作状态等，让桌宠状态语义更丰富。
