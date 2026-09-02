# 桌面宠物 · 橘猫 🐱

一个用 **Python 标准库（tkinter）** 实现的桌面宠物，零第三方依赖。
一只程序化画出来的橘猫在你的屏幕底边散步、打盹、卖萌。

![Python](https://img.shields.io/badge/Python-3.8%2B-blue)

## 运行

```bash
python main.py
```

或者直接双击 `run.bat`（Windows，使用 `pythonw` 启动，不带控制台窗口）。

## 交互

| 操作 | 效果 |
| --- | --- |
| 左键拖拽 | 把猫拎起来（四脚悬空乱蹬），松手会掉下来并落地反弹 |
| 双击 | 摸摸头，冒爱心 |
| 右键 | 菜单：喂食 / 摸摸头 / 打盹·叫醒 / 说句话 / 退出 |

## 它会做什么

- 在各显示器的任务栏上方散步（支持副屏，跨屏时会顺着“台阶”掉下去、爬不上去就掉头）
- 始终保持最顶层：每帧用 Win32 `SetWindowPos(HWND_TOPMOST)` 压回顶层，点过任务栏也不会被挡住
- 无聊时随机碎碎念（头顶气泡）
- 什么都不做时发呆、眨眼、摇尾巴，深夜（23 点～次日 7 点）自动打盹冒 Zzz
- 被拖到半空松手会自由落体，落地弹一下

## 项目结构

```
desktop_pet/
├── main.py            # 入口（含 Windows 高分屏 DPI 适配）
├── run.bat            # Windows 双击启动脚本
├── pet/
│   ├── config.py      # 所有可调参数：配色、速度、台词……
│   ├── sprites.py     # 逐帧绘制：橘猫全靠 Canvas 图元程序化画出
│   ├── behavior.py    # 行为状态机：idle/walk/sleep/drag/fall/happy
│   ├── screens.py     # 多显示器枚举与虚拟桌面边界（EnumDisplayMonitors）
│   └── pet_window.py  # 无边框透明置顶窗、鼠标交互、主循环
├── tests/
│   └── test_smoke.py  # 冒烟测试：交互与状态机流转
└── README.md
```

## 测试

```bash
python -m unittest tests.test_smoke -v
```

## 自定义

改 `pet/config.py` 即可：

- `BODY` / `BODY_DARK` / `CREAM` …… 换毛色（比如改成白猫、灰猫）
- `WALK_SPEED` / `FPS` 调节走路速度与流畅度
- `PHRASES` 等台词列表换成你喜欢的句子
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
