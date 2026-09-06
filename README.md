# 桌面宠物 · 橘猫与小伙伴们 🐱

一个用 **Python 标准库（tkinter）** 实现的桌面宠物，零第三方依赖。
一只程序化画出来的橘猫在你的屏幕底边散步、打盹、卖萌；
右键菜单里可以切换成多位小伙伴：NoobAI 本地生成的**图集桌宠**
（多姿势、带睡觉行的大窗口）与参考图抠图的**高清精灵**（240px）。
每个角色都有自己的一套台词。

![Python](https://img.shields.io/badge/Python-3.8%2B-blue)

## 运行

```bash
python main.py
```

或者直接双击 `run.bat`（Windows，使用 `pythonw` 启动，不带控制台窗口）。

## 交互

| 操作 | 效果 |
| --- | --- |
| 左键拖拽 | 把它拎起来（四脚悬空乱蹬），松手会掉下来并落地反弹 |
| 双击 | 人类角色=打招呼（挥手）；猫=摸摸头，冒爱心 |
| 右键 | 菜单贴着宠物头顶弹出（可微盖）：人类=打招呼 / 送礼物（开心跳+爱心）/ 聊聊天；猫=喂食 / 摸摸头；打盹·叫醒 / 换角色 / 退出 |

头顶对话框是矩形浅蓝半透明方框（87.5% 镂空真透出桌面），
送礼物会触发开心到跳起来的动作。

## 它会做什么

- 在各显示器的任务栏上方散步（支持副屏，跨屏时会顺着“台阶”掉下去、爬不上去就掉头）
- 始终保持最顶层：每帧用 Win32 `SetWindowPos(HWND_TOPMOST)` 压回顶层，点过任务栏也不会被挡住
- 无聊时随机碎碎念（头顶半透明气泡，自动换行）
- 发呆时有呼吸微动；深夜（23 点～次日 7 点）自动打盹冒 Zzz（图集角色会播蜷睡姿势）
- 被拖到半空松手会自由落体，落地弹一下

## 角色

右键菜单里可以随时切换角色，选择会记住（存于 `~/.desktop_pet.json`），
每个角色的台词（聊天 / 送礼物 / 睡觉 / 叫醒 / 摔落）都不一样：

| 角色 | 形象来源 |
| --- | --- |
| 🐱 橘猫 | 程序化绘制的初始角色 |
| 🐣 中野二乃、莉莉艾、小光、露莎米奈 | 本地 ComfyUI 绿幕流程生成的图集桌宠（29 帧，含睡觉行） |
| 🐣 芒果 | 图集猫 |
| 🧚 竹兰 | 参考图高清抠图精灵 |

## 图集桌宠（本地生成）

`hatched/<id>/` 里的图集桌宠由本地 ComfyUI 离线生成（NoobAI-XL 绿幕流程：
纯绿幕底出图 → snap 键控 + 蒙版腐蚀去边 → 封闭空腔扣除 → 同种子逐帧保证
细节一致），运行时零依赖，只加载 PNG：

```bash
# 需先启动本地 ComfyUI（API http://127.0.0.1:8188）
python tools/comfy_hatch.py atlas --id <角色id> --name 名字 \
    --base 定形象.png --sleep-base 睡姿.png \
    --ckpt NoobAI-XL-v1.1.safetensors --snap 80 --erode 3 \
    --rows idle,running-right,waving,jumping,sleep \
    --identity '角色锚点 danbooru tags'
```

- 与 `pet/characters.py` 里同 id 的旧角色会被图集**替换**（名字台词沿用）
- 每行同一种子 + 低重绘幅度，衣服细节逐帧锁定不闪烁
- 详细标定与踩坑见 `AGENTS.md`

## 高清图片精灵（构建期工具）

`assets/` 里的精灵帧由 `tools/build_sprites.py` 从参考图离线生成
（运行时零依赖，只加载 PNG）：

```bash
pip install pillow "rembg[cpu]"     # 仅构建期需要；模型走 GitHub 下载
python tools/build_sprites.py       # 抠图 → 去黑晕 → 缩放 → 生成帧
python tools/build_sprites.py --only nino --sheet   # 只建一个 + 拼图预览
```

管线要点：

- **抠图**：rembg 本地 AI 抠图（动漫插画用 `isnet-anime`），
  图片不外传；自动丢弃与人物不相连的背景杂物（台灯、羽毛等小岛）
- **边缘清理**：收缩 1px 过渡带 + alpha 二值化 + 边缘像素用身体内部颜色渗色，
  避免键色透明窗口的暗边/背景色晕
- **伪姿势**：每张参考图只有一个姿势，各状态帧由仿射变换伪造——
  呼吸（纵向微缩放）、走路（左右倾斜 + 上下颠）、睡觉（压扁成蹲姿）、
  被拎/下落（纵向拉伸）；真·新姿势由图集桌宠流程承担

## 项目结构

```
desktop_pet/
├── main.py             # 入口（含 Windows 高分屏 DPI 适配）
├── run.bat             # Windows 双击启动脚本
├── pet/
│   ├── config.py       # 全局可调参数：配色、速度、键色、气泡配色……
│   ├── characters.py   # 角色库：外观预设 + 每个角色的台词包
│   ├── drawutil.py     # 共享绘制工具：镜像助手 / 气泡 / 粒子
│   ├── sprites.py      # 橘猫逐帧绘制（Canvas 图元程序化画出）
│   ├── girl_sprites.py # Q 版少女参数化逐帧绘制（无构建产物时回落）
│   ├── photo_sprites.py# 高清图片精灵播放器（加载 assets/ 预生成帧）
│   ├── hatch_sprites.py# 图集桌宠播放器（加载 hatched/ 图集包）
│   ├── behavior.py     # 行为状态机：idle/walk/sleep/drag/fall/happy/excited
│   ├── screens.py      # 多显示器枚举与虚拟桌面边界
│   └── pet_window.py   # 无边框透明置顶窗、右键菜单、角色切换、主循环
├── tools/
│   ├── comfy_hatch.py       # 本地 ComfyUI 生图后端（gen 单张 / atlas 图集组装）
│   ├── hatch_pet.py         # 远程 API 版图集管线（确定性抠底/合成复用）
│   ├── build_sprites.py     # 离线构建：参考图 → 抠图 → 精灵帧（需 pillow+rembg）
│   ├── add_character.py     # 角色添加接口：图片 → 新角色 + 台词（CLI 可编程调用）
│   └── character_server.py  # 本地上传网页（127.0.0.1:8765）
├── assets/             # 构建产物：各角色 PNG 帧 + manifest.json
├── hatched/<id>/       # 图集桌宠包：pet.json + spritesheet.png
├── tests/
│   └── test_smoke.py   # 冒烟测试：交互、状态机、角色库与切换
└── README.md
```

## 测试

```bash
python -m unittest tests.test_smoke -v
```

## 自定义

- 新增角色：在 `pet/characters.py` 里照抄一个预设，改外观参数和台词即可
- 换台词：直接改 `characters.py` 里对应角色的 `phrases`
- 橘猫配色：改 `pet/config.py` 的 `BODY` / `BODY_DARK` / `CREAM`……
- `WALK_SPEED` / `FPS` 调节走路速度与流畅度
- `KEY_COLOR` 是透明键色，请保证它不与宠物配色重复

## 添加新角色（接口）

传入一张图片即可生成新角色（抠图 → 精灵帧 → 台词注册，写入
`custom_characters.json`，宠物右键菜单重新打开时即可看到）：

```bash
# 方式一：本地上传网页（推荐），浏览器打开 http://127.0.0.1:8765
python tools/character_server.py

# 方式二：命令行（透明底 PNG 免抠图、免装 rembg）
python tools/add_character.py --image 人物.png --id mychar --name 我的人物     --talk '你好呀' --talk '今天也加油' --feed '谢谢投喂！'
```

- 带 `--id` 规则：小写字母开头，仅含小写字母/数字/下划线，不与内置角色冲突
- 抠图模型：动漫插画 `--model isnet-anime`
- 台词条目可省略（未填类别用通用台词），之后直接改 `custom_characters.json`
- 删除角色：从 `custom_characters.json` 移除条目并删掉 `assets/<id>/`

## 打包成 exe（可选）

```bash
pip install pyinstaller
pyinstaller --onefile --noconsole main.py
```

## 已知边界

- 透明窗口基于 Windows 的 `-transparentcolor` 实现，仅在 Windows 下有透明效果；
  其他平台会显示为一个小方块窗口（功能不受影响）。
- 宠物在虚拟桌面（所有显示器）范围内活动：跨屏散步时会掉落到隔壁屏的地面；
  若隔壁屏地面更高，它只会掉头走回来——不会爬台阶。
- 置顶与任务栏压制的 `SetWindowPos` 仅在 Windows 上生效。
- 右键菜单锚定位置按 Windows 默认菜单项高度估算；若系统菜单样式被大幅
  修改（超大字体等），菜单与宠物头顶之间可能出现一点空隙。
