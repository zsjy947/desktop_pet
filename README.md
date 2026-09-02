# 桌面宠物 · 橘猫与小伙伴们 🐱

一个用 **Python 标准库（tkinter）** 实现的桌面宠物，零第三方依赖。
一只程序化画出来的橘猫在你的屏幕底边散步、打盹、卖萌；
还可以在右键菜单里切换成 12 位由 `reference/pictures` 参考图
转化而来的 Q 版少女，每个角色都有自己的一套台词。

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
| 双击 | 摸摸头，冒爱心 |
| 右键 | 菜单在**宠物上方**弹出（不遮挡宠物）：喂食 / 摸摸头 / 打盹·叫醒 / 说句话 / 换角色 / 退出 |

## 它会做什么

- 在各显示器的任务栏上方散步（支持副屏，跨屏时会顺着“台阶”掉下去、爬不上去就掉头）
- 始终保持最顶层：每帧用 Win32 `SetWindowPos(HWND_TOPMOST)` 压回顶层，点过任务栏也不会被挡住
- 无聊时随机碎碎念（头顶气泡，自动换行）
- 什么都不做时发呆、眨眼、摇尾巴，深夜（23 点～次日 7 点）自动打盹冒 Zzz（猫会蜷成一团“猫面包”）
- 被拖到半空松手会自由落体，落地弹一下

## 角色

右键菜单里可以随时切换角色，选择会记住（存于 `~/.desktop_pet.json`），
每个角色的台词（碎碎念 / 喂食 / 摸头 / 睡觉 / 叫醒 / 摔落）都不一样：

| 角色 | 形象来源 |
| --- | --- |
| 🐱 橘猫 | 程序化绘制的初始角色 |
| 🧚 中野二乃、莉莉艾、小光、由比滨结衣、竹兰、露莎米奈 | `reference/pictures` 动漫角色参考图 |
| 🧚 关晓彤、戚薇、毛晓彤、王玉雯、赵今麦、陈都灵 | `reference/pictures` 参考照片 |

少女们按参考图特征参数化绘制：发色发型（双马尾 / 马尾 / 侧发髻 / 侧编发……）、
瞳色、服装（连衣裙 / 衬衫裙 / 和服 / 大衣 / 芭蕾纱裙……）、腿袜、
头饰（蝴蝶结 / 宽檐帽 / 毛线帽 / 花环 / 头纱……）、眼镜、围巾、领带、珍珠项链等。

## 项目结构

```
desktop_pet/
├── main.py             # 入口（含 Windows 高分屏 DPI 适配）
├── run.bat             # Windows 双击启动脚本
├── pet/
│   ├── config.py       # 全局可调参数：配色、速度、橘猫台词……
│   ├── characters.py   # 角色库：外观预设 + 每个角色的台词包
│   ├── drawutil.py     # 共享绘制工具：镜像助手 / 气泡 / 粒子
│   ├── sprites.py      # 橘猫逐帧绘制（Canvas 图元程序化画出）
│   ├── girl_sprites.py # Q 版少女参数化逐帧绘制
│   ├── behavior.py     # 行为状态机：idle/walk/sleep/drag/fall/happy
│   ├── screens.py      # 多显示器枚举与虚拟桌面边界
│   └── pet_window.py   # 无边框透明置顶窗、右键菜单、角色切换、主循环
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
  修改（超大字体等），菜单底边与宠物头顶之间可能出现一点空隙。
