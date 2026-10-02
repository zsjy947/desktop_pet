# 桌面宠物 🐾（已结档）

> ## ⛔ 本项目已于 2026-10-02 正式停止维护
>
> 按《VibeCoding 项目有效性评估报告》的结论封存：同类赛道拥挤
> （BongoCat 23.7K★ / VPet 6.8K★ 均远超本项目定位），基础交互
> （喂食/换装/气泡）为成熟功能复刻，继续投入性价比不足。
> 不再接受新功能；报 bug 请自行参考 [AGENTS.md](AGENTS.md) 排查。
>
> - **最值钱的部分已抽走**：绿幕生图 → 确定性抠底 → 图集/逐帧
>   资产打包的完整工艺链，见独立仓库
>   [`deskpet-asset-pipeline`](../deskpet-asset-pipeline)（角色无关、
>   无 IP、MIT，含离线冒烟测试）。
> - **踩坑沉淀两篇**（可作博客/gist 发布）：
>   [Windows 键色透明窗口（tkinter）踩坑实录](docs/transparent-window-tk-keycolor.md) ·
>   [PySide6 逐像素透明窗口踩坑实录](docs/transparent-window-qt-pyside6.md)
> - **IP 边界**：本仓库 `anims/` 与 `hatched/` 内含宝可梦官方素材
>   （Pokémon Showdown 动画 / 宝可梦图集），**仅限个人本地使用，
>   禁止分发、转载或再授权**；仓库请保持私有。

## 最终状态（pokemon 分支，tag `v1.0.0-final`）

Windows 桌面宠物，双渲染层：

- **Qt 主层**（PySide6）：逐像素透明置顶窗（`WA_TranslucentBackground`
  + `setMask` 点击穿透），30Hz 实际 dt 主循环，呼吸/落地挤压/运行时
  镜像，真半透明气泡，软粒子；蒙版 = 行程扫描 QRegion。
- **tk 兜底层**（零依赖 tkinter）：键色窗口方案，未装 PySide6 或
  `--renderer tk` 时启用（已冻结，只修不加）。

角色：皮卡丘 / 伊布 / 谢米（陆上形态）/ 比克提尼 / 新叶喵，全部使用
Pokémon Showdown 官方动画导入的 v2 逐帧资产（`anims/`）。交互按物种
分：👋打招呼、🍓喂个树果（叫声拟声词），空闲随机触发专属动作。

## 使用（归档快照）

```bash
pip install PySide6          # 唯一运行时依赖（tk 兜底层零依赖）
python -m pet                # 或双击 run.bat；--char/--list/--quit/--renderer
python -m unittest tests.test_smoke tests.test_anim_pack -v   # 42 项
```

详细的架构、启动方式、标定参数与全部踩坑记录见
[AGENTS.md](AGENTS.md)——它比本 README 完整得多，是本项目真正的
交接文档。

## 分支去向（三分支归档说明）

| 分支 | 内容 | 去向 |
| --- | --- | --- |
| `pokemon` | 宝可梦线：5 只 Showdown 动画 + Qt 渲染层 + anims/ v2 资产 | **最终活跃线**，封版 tag `v1.0.0-final` |
| `hatch-pet` | 人物线：图集生成管线 + 芒果/二乃/莉莉艾/小光/露莎米奈图集 + 照片精灵 | 归档快照，不再更新 |
| `main` | 早期线：Canvas 橘猫 + 落地高度自适应 + 角色添加接口 | 归档快照，不再更新 |
| ~~`pixel-art`~~ | 像素版精灵（用户不满意） | 2026-09 已删（本地+远程） |

人物线角色如需复活：切 `hatch-pet` 分支自取，图集重新生成可用
[deskpet-asset-pipeline](../deskpet-asset-pipeline)。

## 历史脉络

1. `main`：Canvas 程序化绘制橘猫 → 高清图片精灵 → 气泡独立对话区 →
   角色添加接口 → 落地高度工作区自适应
2. `hatch-pet`：AI 生成图集桌宠（绿幕流程 + 确定性抠底合成 + QA），
   人物角色上线
3. `pokemon`：宝可梦线；Qt 渲染层根治闪帧 + Showdown 官方动画替换
   自产图集 → 结档（2026-10-02）
