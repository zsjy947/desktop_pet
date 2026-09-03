# AGENTS.md — 桌面宠物项目交接文档

给在新电脑/新会话上接手本项目的 agent（或未来的自己）：本文档浓缩了
整个开发与调优过程中的架构、构建流程、踩坑与验证方法。改代码前先读完。

## 1. 项目概览

Python 标准库（tkinter）桌面宠物，运行时**零第三方依赖**；图片精灵的
生成在开发期完成（pillow + rembg）。多显示器漫游、置顶（不被任务栏
遮挡）、右键菜单弹出在宠物上方、13+ 个可切换角色（各有独立台词）。

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
  behavior.py              状态机 idle/walk/sleep/drag/fall/happy
  screens.py               EnumDisplayMonitors + 工作区（GetMonitorInfoW）
  pet_window.py            主窗口：透明置顶、右键菜单、角色切换、主循环
tools/
  build_sprites.py         高清精灵构建（抠图→清理→伪姿势帧，240px）
  hatch_pet.py             hatch-pet 生成管线（z-image-turbo 生姿势→图集）
  add_character.py         角色添加接口（CLI / 可编程）
  character_server.py      本地上传网页 http://127.0.0.1:8765
tests/test_smoke.py        19 项冒烟测试（会短暂弹窗）
assets/                    高清精灵帧（入库，~8.7MB）
hatched/<id>/              图集桌宠包：pet.json + spritesheet.png（入库）；
                           build/ 与 qa/ 为生成中间产物（不入库）
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
  running-right/left、happy→waving、fall/drag→jumping、sleep→idle
  第 0 帧；waiting/running/review 为 Codex 应用专属行，桌宠暂不用。
  `--import-atlas x.webp` 可导入 Codex 孵化的现成图集。
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
- 菜单锚定：底边贴窗口顶边（对话区）上方，高度按 26px/项估算
  （实测 ~22px，宁大勿小——估小了菜单会沉到宠物后面被键色窗口盖住）。

**精灵帧**
- tkinter 的 PhotoImage **不能运行时翻转/旋转** → 所有镜像与姿势变换
  在构建期烘焙（每状态 [朝右×N, 朝左×N]）。
- 帧必须铺满整个窗口画布（240×240），运行时 `create_image` 整帧贴。
- 每张参考图只有一个姿势；走路=倾斜/剪切段、睡觉=压扁蹲姿是被逼的
  伪姿势。真·多姿势需要 Stable Diffusion + ControlNet(OpenPose) 或
  Live2D（后者与 tkinter 集成不现实）。

**对话气泡**
- 气泡画在窗口顶部独立加高的对话区画布（`cv_bubble`），尾巴指向下方
  宠物，**永不遮挡人物**；菜单锚定在窗口顶边之上，避免盖住气泡区。

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
- `hatch-pet`：图集桌宠（生成管线 + 播放器 + 已孵化示例「芒果」），基于 main
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

## 7. 后续方向（未做）

- 真·多姿势/更强一致性：给 hatch 管线接支持参考图的生图（image editing /
  IP-Adapter），消除行间漂移；动漫形象一致性较好，真人会漂移。
- 逐像素透明窗口：换 PySide6（`WA_TranslucentBackground`）或 ctypes
  UpdateLayeredWindow（可零运行时依赖但气泡文字需自绘合成）。
- hatch 行的深度利用：waiting（等人）接"有话对你说"、running（专注
  干活）接工作状态等，让桌宠状态语义更丰富。
