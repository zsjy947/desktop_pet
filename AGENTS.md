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
  photo_sprites.py         图片精灵播放器（assets_pixel/ 优先于 assets/）
  behavior.py              状态机 idle/walk/sleep/drag/fall/happy
  screens.py               EnumDisplayMonitors 多显示器
  pet_window.py            主窗口：透明置顶、右键菜单、角色切换、主循环
tools/
  build_sprites.py         高清精灵构建（抠图→清理→伪姿势帧，240px）
  build_pixel_sprites.py   像素版构建（64px 量化+剪切段走路，pixel-art 分支）
  add_character.py         角色添加接口（CLI / 可编程）
  character_server.py      本地上传网页 http://127.0.0.1:8765
tests/test_smoke.py        15 项冒烟测试（会短暂弹窗）
assets/                    高清精灵帧（入库，~8.7MB）
assets_pixel/              像素精灵帧（pixel-art 分支，~739KB）
reference/pictures/        用户提供的参考图（**不入库**）
custom_characters.json     接口生成的自定义角色（**不入库**）
~/.desktop_pet.json        用户上次选择的角色（运行时写入）
```

## 2. 新电脑环境搭建

1. Python 3.10+（tkinter 必须有；Windows 自带）。
2. 运行宠物：`python main.py` 或 `run.bat`。仅此时不需要任何第三方库。
3. 开发/构建才需要：
   ```bash
   pip install pillow "rembg[cpu]"
   ```
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
5. 测试：`python -m unittest tests.test_smoke -v`（15 项；弹一下测试窗口属正常）。

## 3. 构建与角色流程

- **高清精灵**：`python tools/build_sprites.py`（`--only nino` 单建，
  `--sheet` 出拼图预览）。管线：rembg 抠图 → 丢弃小连通域（背景杂物，
  阈值 18% 面积）→ 收缩 1px 过渡带 + alpha 二值化 + 边缘渗色去黑晕 →
  缩放 240px → 各状态伪姿势帧（朝右/朝左两套）+ manifest.json。
- **像素版**（pixel-art 分支）：`python tools/build_pixel_sprites.py`。
  64px 像素分辨率 + 24 色量化 + 3x 最近邻放大；全身像（高宽比≥1.5）
  走路帧用上下半身水平错位伪装迈步。产物在 `assets_pixel/`，
  运行时**优先于** `assets/` 加载，删目录即回落高清版。
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

- `main`：气泡独立对话区 + 角色添加接口 + AGENTS.md（本文档）
- `pixel-art`：像素版精灵分支（基于 main，含全部 main 功能）
- 不入库：`reference/`、`custom_characters.json`、`tmp_*`、用户偏好
- 提交历史（本会话）：
  1. `49ea981` 角色系统（Canvas Q 版少女 + 台词包 + 菜单上方弹出）
  2. `d6ebbf8` 高清图片精灵模式（构建管线 + 运行时播放器）
  3. `3af9822` 气泡独立对话区
  4. `f96e8ac`（pixel-art）像素版精灵
  5. `41b3fcb` 角色添加接口（CLI + 网页）
  6. AGENTS.md（本文档）

## 7. 后续方向（未做）

- 真·多姿势：Stable Diffusion + ControlNet(OpenPose) + 角色一致性
  （IP-Adapter / reference-only）；动漫角色一致性较好，真人会漂移。
- 逐像素透明窗口：换 PySide6（`WA_TranslucentBackground`）或 ctypes
  UpdateLayeredWindow（可零运行时依赖但气泡文字需自绘合成）。
- 真人像素化：`python tools/build_pixel_sprites.py --all`（管线已支持，
  默认只建 6 位动漫角色）。
