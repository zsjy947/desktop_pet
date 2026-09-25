# AGENTS.md — 桌面宠物项目交接文档

给在新电脑/新会话上接手本项目的 agent（或未来的自己）：本文档浓缩了
整个开发与调优过程中的架构、构建流程、踩坑与验证方法。改代码前先读完。

## 1. 项目概览

> **分支说明**：本分支 `pokemon` = 宝可梦线，角色只有宝可梦×5
> （2026-09-25 起为 Pokémon Showdown 动画）；人物（少女/竹兰照片精灵/
> 芒果猫）与 Canvas 橘猫在别的分支（橘猫已从本分支删除）。运行时代码
> 两分支共享，角色内容不同。

桌面宠物，**双渲染层**（2026-09-25 重构，动机见 §3.2 诊断）：
- **Qt（主）**：PySide6 逐像素透明窗口（`WA_TranslucentBackground` +
  setMask 点击穿透）。帧推进 =「时长累加器 + 实际 dt」（帧边界与 tick
  严格对齐）；呼吸 = 整帧 scaleY 微变形（锚脚底）、落地 squash 挤压、
  朝向运行时镜像、真半透明气泡、QPainterPath 自绘软粒子。运行时依赖
  唯一新增 PySide6（`pip install PySide6`）。
- **tk（兜底，零依赖）**：原 tkinter 键色窗口原样保留，未装 PySide6
  或 `--renderer tk` 时启用；anims/ v2 资产 tk 不支持（宝可梦自动回落
  hatched 图集）。

多显示器漫游、置顶（不被任务栏遮挡）、右键菜单弹出在宠物头顶（可微
盖）两层通用。本分支角色 5 个：**宝可梦×5（皮卡丘/伊布/谢米陆上
形态/比克提尼/新叶喵）**——2026-09-25 起全部换 **Pokémon Showdown
官方动画**（25~33fps 透明 GIF 导入，见 §3.2），tricks 专属动作随图集
退役（tk 层 hatched/ 包仍带 tricks 兜底）。资产两级：`anims/` **v2 帧
序列**（主，Qt 用，软 alpha 保留）与 `hatched/` 图集（tk 用；Qt 也能
直接播图集）。anims 与 hatched/custom 同 id 时 **anims 优先**（图片
替换语义，名字台词沿用旧 preset，见 pet/registry.py）。
**绿幕流程（浅色服装角色必用）**：白底+空腔色距判罚会把白裙/白帽
当成"封闭浅色空腔"大面积抠掉（莉莉艾首版白裙全没），色距法对白色系
设计不成立。改为生图直接出**纯绿幕底**（prompt: solid bright green
background, flat chroma key green screen），键控天然区分角色与背景，
腿间封闭绿块按色直接扣。remove_bg 加 snap 吸附参数（绿幕标定 80：
先把你色距在 snap 内的像素归一化到背景色再键控，抗背景渐变/条带；
白底流程不要开）。atlas 用 `--snap 80 --erode 3`（erode 3 切绿边）。
注意 atlas 单行重跑必须传全行清单，否则其余行会被清空。
交互按物种分：人类角色 = 👋打招呼（waving 行）/ 🎁送礼物（excited
状态→图集跳跃行 + 爱心）/ 💬聊聊天；**宝可梦（"species":"pokemon"）
= 👋打招呼 / 🍓喂个树果，没有聊聊天——只有叫声（phrases 全是拟声词），
随机碎碎念关闭**；图集包空闲时随机触发专属动作 trick（behavior 的
trick 状态播 pet.json tricks 指定的图集行 7/8，配叫声气泡 + 特效粒子
spark/leaf/flower/fire/star，见 pet_window._tricks/_spawn_fx；Showdown
动画包无 tricks，菜单自动隐藏表演项）。双击 = 打招呼。默认角色
皮卡丘（偏好里的角色不存在时回落）。气泡为矩形浅蓝半透明方框（边框
#5DADE2、底 #D6EAF8），无尾巴箭头，对话区压矮到两行贴住头顶。tk 层
半透明走 pet/glass.xbm 87.5% 镂空；Qt 层是真 alpha。

## 3.1 宝可梦图集流程（2026-09-13）

Q 版宝可梦首批 5 只：pikachu/eevee/shaymin(land form)/victini/
sprigatito。与少女流程的差异：

- **形象来源**：NoobAI 的 danbooru 本体 tag 直接出正统形象
  （`pikachu / eevee / shaymin, land form / victini / sprigatito` +
  `pokemon (creature), chibi, flat color`），绿幕底同 §1。
- **base 筛选是大坑**：绿幕+chibi 下种子踩坑率 ~60%——马赛克乱纹、
  徽章构图、大头特写、形象过小、"2024 Shygromai" 类文字污染都有
  （见 localgen/pk_bases_sheet.png）。必须 3~4 个种子挑锚点、
  **带文件名标签拼图目检**；提示词加 `centered, large in frame` 能
  明显改善构图。最终锚点见 localgen/batch_pk.py 的 POKEMON 表。
- **base 用 14 步**（txt2img 与步数成正比：28 步 199s / 14 步 98s，
  平涂 Q 版质量无损）；**i2i 帧保持 28 步默认**（实测 i2i 耗时与
  steps/denoise 基本无关，~200s/张是硬成本，降步数不省时间）。
- **专属动作行**：`--trick7/--trick8 '姿势词|姿势词|...'` 借用图集
  第 7/8 行槽位（Codex 的 running/review 行桌宠不用），帧姿势词用
  | 分隔、不足循环复用。**trick 帧必须走 `--trick-txt2img`**（文生
  图）：i2i 被站姿 init 锁死，0.65 重绘都画不出放电/冲刺类大动作
  （实测）；正统宝可梦身份靠本体 tag 天然稳定，txt2img 直出动作帧。
  txt2img trick 三个坑：**提示词必须加 `solo`**（否则画一对）；常画
  一条贯穿地线且与脚连通——`_strip_ground_line` 按行宽中位数做列域
  裁剪（形态学开运算会切伤尾巴，弃用）；**姿势词要写具体的身体动作
  并锚定站姿**（`standing on all fours` / `standing on the ground`），
  energy/glowing/petals swirling 类词会引出能量光晕底、花田马赛克、
  天空形态飞行。**同种子换词会复现相同坏构图**（种子决定布局），
  废帧必须换种子重生成；批量修帧用"种子抽奖"模式——生成→提取→
  按尺寸（高 150~700px）验收→不合格换种子重试。`--extra-json` 把
  species/phrases(叫声)/tricks(name,row,fx,cry) 写进 pet.json。每只
  两个动作（皮卡丘=电气火花/电光一闪、伊布=摇尾巴/好奇歪头、
  谢米=花朵摇曳/草地打滚、比克提尼=胜利 V/喷小火苗、新叶喵=草叶
  飞舞/蹭脸理毛）；个别词反复出废图时直接砍到 2~3 个姿势词循环。
- **批量入口**：`python localgen/batch_pk.py [id...]`（重跑安全，
  build/ 已有帧即跳过）；base 候选生成 `python localgen/gen_pk_bases.py`。
- **本体含绿色/含白的角色不能走绿幕**（2026-09-13 用户复核：新叶喵
  本体深绿被键掉、比克提尼耳朵受损）：新叶喵整只换**蓝幕**（蓝底
  prompt 同款、`--trick-bg` 换动作行背景词、--snap 80 照旧）；比克
  提尼是 base 画错（红冠黑耳，官方为橙冠），换种子重抽 base。
- **init 缓存必须带 base mtime**（comfy_hatch 已修）：init_{row}.png
  固定文件名时换了 base 定形象图不会生效，i2i 会一直用旧 base——
  表现为"重建了但角色还是旧的/更白"。现在文件名是
  init_{row}_{base_mtime}.png，换 base 自动失效。
- txt2img trick 抽奖验收要查**键控率**（remove_bg 后 alpha==0 占比
  > 0.5），只验尺寸会收下"整张蓝卡"这种没键开的废图。
- 决定**不下载新模型**：NoobAI 对 5 只宝可梦还原全部达标，Hyper-SD
  蒸馏 LoRA 有洗掉平涂质感的风险且 i2i 耗时不与步数挂钩（省不了）。


## 3.2 Qt 运行时 + 动效根治 + 云端管线（2026-09-25）

### 闪帧/画质差的诊断结论（三层根因，全部核实过行号）

1. **素材无时序连贯（主因）**：逐帧独立 i2i（denoise 0.3~0.5）从同一
   init 去噪，帧间内容各自漂移；每动作仅 4~8 帧、110~280ms/帧。
2. **蒙版逐帧抖动**：绿幕键控 → alpha 二值化 → erode 3px，每帧边缘
   像素独立抖，表现为人形轮廓"闪"。
3. **播放层缺陷**：`_phase` 绝对时间取模与 33ms tick 不对齐（跳帧/
   重复帧）；每 tick 无条件 delete('all')×2 + geometry + SetWindowPos，
   键色窗口每秒整帧重合成 30 次。
4. **画质差** = NoobAI-XL 上限低（base 踩坑率 ~60%）+ 键色窗口只认
   二值 alpha（软边/阴影/光效全被砍，绿幕/erode/空腔判罚整条链都在
   伺服它）。**结论：键色窗口是万恶之源。**

### Qt 层的解法（pet/qt_app.py / qt_render.py）

- `qt_app.py`：组合根。Frameless + TranslucentBackground + Tool（不进
  任务栏）+ StaysOnTop；QTimer 30Hz；位移/下落按实际 dt 换算
  （config 的 per-frame 常量 ×FPS 换算成 px/s）；落地 squash 脉冲；
  QMenu 消费 menu.spec()（与 tk build 同一套分组，menu.py 重构）。
- `qt_render.py`：Renderer 双后端（anim/hatch）。advance() 播放头
  按逐帧时长累加；paint() 绘制帧 + 变换 + 粒子；body_region() 出命中
  蒙版。Canvas 角色绘制已随橘猫删除（girl_sprites 仍为人物线保留）。
- **蒙版（点击穿透）**：numpy 行程扫描帧 alpha → QRegion（横向 run +
  纵向同行程合并成条带矩形），app 层并上气泡多边形与粒子方块后
  setMask。**必须 translated(0, 对话区高)**（踩过：忘平移=宠物下半被
  裁，2026-09-25 实测）。
- **Qt/PySide6 踩坑（6.11 实测）**：
  - `QBitmap.fromImage` 会 **access violation**（offscreen 必崩）——
    蒙版别走 QBitmap，用行程扫描 QRegion。
  - `QRegion(QPainterPath)` C++ 有、**Python 绑定没有**——用
    `path.toFillPolygon().toPolygon()` 转 QPolygon。
  - `QImage(bytes)` 构造是**浅引用**，临时 bytes 回收后读悬空内存——
    立即 `.copy()`。
  - `QMenu.exec` 的 monkeypatch **不生效**（shiboken 重载在 C++ 层），
    测试菜单要用真实 exec + 嵌套循环里 QTimer 关菜单。
  - Qt6 自带 per-monitor DPI 感知，**不要再调** windowing 的
    SetProcessDpiAwareness（混用会坐标错乱）；qt 路径显示器用
    QScreen.availableGeometry()（逻辑坐标），tk 路径才用 screens.py。

### anims/ v2 资产格式（Qt 播放的主资产）

`anims/<id>/anim.json + frames/*.png`：逐帧 PNG（**软 alpha 保留**，
不再二值化/erode）、朝向运行时镜像（不再烘焙左右两行）。schema 见
pet/anims.py 模块注释（id/species/window/foot/phrases/tricks(state 键)/
states{idle,walk(flip_left),sleep,happy,jump,trick0…}，durations 逐帧
ms 或 fps）。状态回落与图集一致（excited→happy、fall/drag→jump、
缺行→idle，sleep 无行→定格 idle 第 0 帧）。**热重载**：运行时每 ~3s
取 anim.json + 逐帧文件 mtime 指纹（覆盖同名帧不改目录 mtime，必须逐
文件取），变了自动清帧/蒙版缓存——旧实例换资产不用重启。

- `python tools/convert_atlas.py [id...]`：hatched/ 图集一键转 v2
  （行 1→walk+flip_left、行 2 丢弃、sleep_row→sleep、tricks.row→
  trick{i}，时长沿用 ROW_SPECS）。**2026-09-25 起 5 只宝可梦已整体
  换 Showdown 动画，转换包不再使用**（工具保留，图集转换需求仍可用）。
- `python tools/import_gif.py --gif x.gif --id y --name 名`：GIF→v2
  （NEAREST 整数倍放大；脚底按全帧最低不透明行贴合；idle/walk/happy
  共用，sleep 定格首帧）。
- `python tools/import_showdown.py [id...]`：**宝可梦主力管线**——下载
  Pokémon Showdown ani 动画（play.pokemonshowdown.com/sprites/ani/
  <id>.gif，25~33fps 透明）→ 导入 v2 → 从 hatched/<id>/pet.json 继承
  displayName/species/phrases（叫声包用户无感知）。GIF 缓存在
  localgen/showdown/。tricks 随图集退役（GIF 无对应动画帧），菜单在
  behavior.tricks 为空时自动隐藏"✨ 表演一个动作"。
- `python tools/qt_smoke_shot.py <id> <out.png>`：后台起宠物按窗口
  标题前缀「桌面宠物 · 」枚举 HWND 截图（驱动进程自己
  SetProcessDpiAwareness(2)；别用 FindWindow 硬编码角色名，换角色就
  匹配不到——踩过）。
- **双重镜像踩坑（2026-09-25）**：走路朝左时精灵被裁得只剩碎片——
  `_anim_image` 在 flip 时已返回镜像帧图（蒙版按它构建），paint 又叠
  一次 QTransform 镜像 → 显示与蒙版左右错位，不对称帧 38% 像素落在
  蒙版外被裁。修复 = 镜像只在帧图层做（与蒙版同源），paint 不再套
  镜像变换；回归测试
  `test_mask_covers_painted_walk_both_facings` 断言两朝向 100% 覆盖。

### 云端生图/生视频管线（下一轮执行，本轮只定设计）

调研结论（2026-09 价格，以控制台为准；渠道**混合 PoC 后定主力**）：

| 用途 | 候选 | 参考价 | 备注 |
|---|---|---|---|
| 定稿图 | 火山方舟 Seedream 4.0/4.5 | ¥0.2/张 | 参考图一致性好、国内直付 |
| 定稿图 | OpenAI gpt-image | $0.02~0.17/张 | `background=transparent` 原生真透明底 |
| 定稿图 | Gemini Nano Banana Pro | ~$0.24/张 | 编辑一致性最强、14 参考图；原生透明不可靠、SynthID 水印 |
| 动画 | 火山方舟 Seedance 1.0 pro | ¥3.67/5s·1080p | 图生视频时序天然连贯 |
| 动画 | 可灵 / Vidu | 资源包计费 | Vidu 支持首尾帧（利于无缝循环） |

**动画主路线 = 图生视频抽帧**：定稿图作首帧 → 5s 绿幕/蓝幕视频 →
ffmpeg 抽帧 12~16fps → 本地键控（软 alpha）+ alpha 时域中值平滑 +
首帧 bbox 锚定 → 每动作 12~24 帧（成本 ¥1~4/动作）。兜底 = 关键帧
4~6 张 + 本地 RIFE 插帧到 24fps（大幅动作插帧易糊）。API Key 走
环境变量；接入代码 `tools/cloud_hatch.py`（adapter 换渠道），后处理
复用 hatch_pet 的键控/QA。本轮（用户决策）**暂不接付费 API**。

```
main.py                    兼容入口（run.bat 双击用；内部走 pet.__main__）
run.bat                    双击启动（pythonw，参数透传：run.bat --char pikachu）
pet/
  __main__.py              命令行入口：python -m pet [--char|--list|--quit|--renderer]
  qt_app.py                Qt 组合根：逐像素透明置顶窗、dt 主循环、拖拽/菜单
  qt_render.py             Qt 渲染器：双后端（anim/hatch）+ 播放头 +
                           变换（呼吸/挤压/镜像）+ 软粒子 + 半透明气泡 + 蒙版
  anims.py                 anims/ v2 资产加载器（anim.json schema 注释在此）
  app.py                   tk 组合根（兜底渲染层的窗口生命周期/交互/每帧协调）
  pet_window.py            兼容 shim（re-export PetApp 等，旧脚本不断链）
  windowing.py             Win32：DPI 感知（tk 用）、置顶压制、单实例互斥锁
  prefs.py                 用户偏好（~/.desktop_pet.json）+ 跨实例退出标志
  menu.py                  右键菜单：spec() 后端无关结构 + build() tk 渲染端
                           （Qt 端由 qt_app 消费同一 spec）
  registry.py              角色表合并：内置 + 自定义 + 图集 + anims（优先级
                           anims > hatched；include_anims=True 才带 anims）
  renderers.py             tk 渲染分发 + 状态归一化（excited/trick 回落规则）
  startup.py               开机自启（用户启动文件夹写 VBS，目录可注入测试）
  fx.py                    粒子生成/推进（爱心/Zzz/特效；绘制分 tk/Qt 两层）
  config.py                全局参数：键色、速度、粒子/气泡配色
  characters.py            人物线共享的少女绘制参数（本分支 CHARACTERS 为空）
  custom.py                自定义角色注册表（custom_characters.json，不入库）
  drawutil.py              tk 绘制共享：镜像助手 / 气泡（圆角+尾巴）/ 粒子
  girl_sprites.py          Q 版少女参数化绘制（图片帧缺失时的回落）
  photo_sprites.py         图片精灵播放器（assets/ 帧目录）
  hatch_sprites.py         hatch-pet 图集桌宠播放器（tk 层；Qt 层直接读同一图集）
  behavior.py              状态机 idle/walk/sleep/drag/fall/happy/excited/trick
  screens.py               EnumDisplayMonitors + 工作区（tk 层用；Qt 用 QScreen）
tools/
  import_showdown.py       Pokémon Showdown 动画批量导入（宝可梦主力管线）
  convert_atlas.py         hatched/ 图集 → anims/ v2 资产一键转换
  import_gif.py            GIF → anims/ v2（脚底贴合/整数倍放大）
  qt_smoke_shot.py         Qt 运行时截图冒烟（按窗口标题找 HWND）
  build_sprites.py         高清精灵构建（抠图→清理→伪姿势帧，240px）
  hatch_pet.py             hatch-pet 生成管线（z-image-turbo 生姿势→图集）
  comfy_hatch.py           本地 ComfyUI 生图后端（gen 单张 / atlas 图集组装）
  add_character.py         角色添加接口（CLI / 可编程）
  character_server.py      本地上传网页 http://127.0.0.1:8765
tests/test_smoke.py        冒烟测试（tk 层，会短暂弹窗）
tests/test_anim_pack.py    v2 资产 + Qt 渲染层测试（offscreen，不弹窗）
anims/<id>/                v2 动画资产：anim.json + frames/*.png（入库）
hatched/<id>/              图集桌宠包：pet.json + spritesheet.png（入库）；
                           build/ 与 qa/ 为生成中间产物（不入库）
localgen/                  本地生图评估产物与报告（REPORT.md，**不入库**）
reference/pictures/        用户提供的参考图（**不入库**）
custom_characters.json     接口生成的自定义角色（**不入库**）
~/.desktop_pet.json        用户上次选择的角色（运行时写入）
~/.desktop_pet.quit        跨实例退出标志（python -m pet --quit 写入）
```

### 启动方式（2026-09-25 更新）

- `run.bat` 双击启动（pythonw 无控制台，参数透传）。
- `python -m pet`：`--char ID` 以指定角色启动；`--list` 列出角色；
  `--quit` 请求运行中实例退出（单实例互斥锁 + 退出标志文件实现，
  重复启动第二个实例会直接退出）；`--renderer qt|tk` 指定渲染层
  （缺省 qt，未装 PySide6 或角色不支持时自动回落 tk 并提示）。
- 开机自启：右键菜单"🚀 开机自启"勾选，往用户启动文件夹写一个
  `desktop_pet_autostart.vbs`（pythonw 隐藏启动）；实现见 pet/startup.py。

## 2. 新电脑环境搭建

1. Python 3.10+（tkinter 必须有；Windows 自带）。
2. 运行宠物：`run.bat` 双击，或 `python -m pet`（可选
   --char/--list/--quit/--renderer，见 §1 启动方式）。tk 兜底层不需要
   任何第三方库；**Qt 主层需要** `pip install PySide6`（唯一运行时依赖）。
3. 开发/构建才需要：
   ```bash
   pip install pillow numpy requests "rembg[cpu]"
   ```
   （hatch_pet.py 生成管线只需 pillow+numpy+requests；rembg 仅
   build_sprites/add_character 抠参考图照片时用到；Qt 测试另需 PySide6。）
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
5. 测试：`python -m unittest tests.test_smoke tests.test_anim_pack -v`
   （42 项；test_smoke 会短暂弹 tk 测试窗口属正常，test_anim_pack 走
   Qt offscreen 不弹窗）。

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

**透明窗口（tk 键色层；Qt 层无此约束，见 §3.2）**
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

**精灵帧（tk 键色层）**
- tkinter 的 PhotoImage **不能运行时翻转/旋转** → 所有镜像与姿势变换
  在构建期烘焙（每状态 [朝右×N, 朝左×N]）。
- **PhotoImage 缓存必须挂在 canvas 组件上**（drawutil 字体缓存同款）：
  模块级缓存跨 Tk 实例会复用**已销毁实例的死图**，`copy -from` 报
  `TclError: image doesn't exist`，_tick 崩掉 after 链、动画冻结——
  且异常只打 stderr 极易漏看（hatch_sprites._caches，2026-09-25 暴露）。
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
- **ComfyUI 节点缓存是单槽的**（2026-09-13 实测）：只有相邻两次执行
  提示词完全相同才命中（2s）；中间插一个不同词的帧就被顶掉，重复词
  的帧重跑照样全价。frame 模式因此只生成**去重后的姿势词**，其余槽位
  克隆补位（comfy_hatch cmd_atlas 内置），否则行走行 8 帧会全价跑。
- txt2img 采样时间与步数成正比（28 步 199s / 14 步 98s，~7s/步）；
  **i2i 帧耗时与 steps/denoise 基本无关**（~200s/张硬成本），降步数
  不省时间。
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
- `hatch-pet`：**人物线**——图集桌宠管线 + 播放器 + 芒果/二乃/莉莉艾/
  小光/露莎米奈图集 + 竹兰照片精灵 + 本地 ComfyUI 生图后端 + 交互/
  气泡/菜单重构，基于 main
- `pokemon`：**宝可梦线**（本分支）——基于 hatch-pet，只保留 5 只
  宝可梦（皮卡丘/伊布/谢米/比克提尼/新叶喵）+ 叫声交互；人物内容
  （hatched 人物包/照片精灵帧/characters.py 人物预设）与 Canvas 橘猫
  （sprites.py/cat_qt.py）已删除，运行时代码与人物线共享。
  2026-09-25 增：Qt 渲染层（qt_app/qt_render）+ anims/ v2 资产
  + convert_atlas/import_gif/import_showdown 工具 + tests/test_anim_pack.py
  （42 项测试 = 27 tk 冒烟 + 15 资产/Qt）；5 只宝可梦全部换 Showdown
  动画（tricks 随图集退役，tk 层兜底不变）
- `pixel-art` 已废弃删除（2026-09，本地与远程均已删；像素方案用户不满意）
- 不入库：`reference/`、`custom_characters.json`、`tmp_*`、
  `hatched/*/build|qa/`、`localgen/`、用户偏好
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

- **云端生图/生视频管线（下一个大项）**：图生视频抽帧主路线 +
  关键帧 RIFE 插帧兜底，渠道混合 PoC 后定主力；设计已定稿见 §3.2
  "云端管线"小节（价格表 / 后处理链 / adapter 规划 / API Key 环境变量）。
  本轮（2026-09-25）按用户决策暂不接付费 API，Qt 层已就位等待素材。
- **Qt 层收尾**：girl/custom 照片角色不支持 Qt（回落 tk）；tk 层冻结名
  义维护（只修不加）。菜单"关于"提示当前渲染层未做。
- 三次元（真人）路线**已暂停**：2026-09-05 按需求把 6 位明星角色从宠物
  移除（characters.py preset + assets/ 帧 + hatched/guan 图集一起删），
  reference/pictures 里的真人照片保留；等找到更满意的写实生图方法再回加。
  评估数据与配方都在 localgen/REPORT.md。动漫侧：lillie/dawn/
  lusamine 已绿幕流程上线（在 hatch-pet 分支）；yui/cynthia 暂缓。
- 真·多姿势/更强一致性：云端图生视频主路线落地后此问题自动消解；
  本地 ControlNet OpenPose 方案搁置。
- ~~逐像素透明窗口~~ **已做**（2026-09-25，PySide6 WA_TranslucentBackground，
  见 §3.2）。
- hatch 行的深度利用：waiting（等人）接"有话对你说"、running（专注
  干活）接工作状态等，让桌宠状态语义更丰富。
