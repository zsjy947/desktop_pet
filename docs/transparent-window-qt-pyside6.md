# PySide6 逐像素透明窗口踩坑实录（Windows）

> 姊妹篇：《Windows 键色透明窗口踩坑实录：tkinter `-transparentcolor`
> 方案的全部代价》。本文来自同一个 Python 桌面宠物项目 2026-09 的
> 迁移实录，PySide6 6.11 实测。目标形态：无边框、置顶、不进任务栏、
> 逐像素 alpha、非窗口区域完全点击穿透。

## 基本形态

```python
class PetWindow(QWidget):
    def __init__(self):
        super().__init__(flags=Qt.FramelessWindowHint
                         | Qt.WindowStaysOnTopHint
                         | Qt.Tool)          # Tool：不进任务栏
        self.setAttribute(Qt.WA_TranslucentBackground)   # 真 alpha
        self.setMouseTracking(True)
```

点击穿透用 `setMask(QRegion)`：蒙版外区域完全穿透（连拖拽都收不到），
蒙版内正常接收鼠标。所以**蒙版 = 所有可见内容的并集**：精灵本体
∪ 气泡多边形 ∪ 粒子方块，每帧更新。

`QTimer` 30Hz 驱动，位移/下落按**实际 dt** 换算成 px/s（别按"每帧
常量"写——定时器漂移会让速度随机），动画播放头用"时长累加器"推进
（帧边界与 tick 严格对齐；用绝对时间取模会因 tick 不对齐产生跳帧/
重复帧）。

## 坑 1：`QBitmap.fromImage` access violation

从帧 alpha 构建 1bpp 蒙版的第一反应是：

```python
mask = QBitmap.fromImage(frame.createMaskFromColor(...))   # 崩
```

PySide6 6.11 实测：offscreen 环境（CI/无窗口会话）**必崩 access
violation**，前台有时也崩。别走 QBitmap——用 numpy 对帧 alpha 做
**行程扫描**，横向 run 合并、纵向同行程再合并成条带矩形，出一个
紧凑的 QRegion（还能顺带把蒙版矩形数量从 O(像素) 压到 O(轮廓)）：

```python
def region_from_alpha(img) -> QRegion:
    a = np.array(img)[:, :, 3] > 0
    region = QRegion()
    runs_by_row = {}                      # (run_start, run_len) -> rows
    for y, row in enumerate(a):
        x = 0
        while x < len(row):
            if row[x]:
                x0 = x
                while x < len(row) and row[x]:
                    x += 1
                runs_by_row.setdefault((x0, x - x0), []).append(y)
            else:
                x += 1
    for (x0, w), rows in runs_by_row.items():
        ys = np.array(rows)               # 同行程的纵向连续段合成条带
        splits = np.where(np.diff(ys) != 1)[0]
        for seg in np.split(ys, splits + 1):
            region += QRegion(x0, int(seg[0]), w, len(seg))
    return region
```

## 坑 2：`QRegion(QPainterPath)` 的 Python 绑定不存在

C++ 有 `QRegion(const QPainterPath &)` 构造，但 PySide6 **没有这个
签名**（TypeError）。气泡圆角矩形要从路径转多边形再进 QRegion：

```python
polygon = path.toFillPolygon().toPolygon()
region = QRegion(polygon)                 # QRegion(QPolygon, Qt.OddEvenFill)
```

## 坑 3：`QImage(bytes)` 是浅引用

`QImage(bytes, w, h, fmt)` 直接包住 Python bytes 的内存，**不拷贝**；
临时 bytes 被回收后继续读就是悬空内存（花屏/随机崩溃）。构造后立即
`.copy()`：

```python
img = QImage(buf, w, h, QImage.Format_RGBA8888).copy()
```

## 坑 4：`QMenu.exec` 的 monkeypatch 不生效

想在测试里拦截 `QMenu.exec` 防阻塞——常规 Python 打补丁没用，因为
PySide6 的方法解析发生在 shiboken/C++ 层，类属性替换**拦不到**。
测试要开真菜单：真实 `exec` + 在 `QTimer.singleShot` 里
`menu.close()`（菜单打开期间定时器照常触发，这点和 tkinter 相同）。

## 坑 5：Qt6 自带 per-monitor DPI 感知，别再调 Win32 的

Qt6 进程默认就是 per-monitor DPI aware；如果应用其他部分（或驱动
脚本）又调 `SetProcessDpiAwareness`，两套感知混用会**坐标错乱**。
规则：

- Qt 路径：显示器几何用 `QScreen.availableGeometry()`（**逻辑坐标**，
  与 QWidget 坐标一致），落地高度同样按工作区底边自适应；
- 只有 tk 兜底路径才需要自己 `SetProcessDpiAwareness` + 物理坐标。

外部进程驱动截图时同理：驱动进程自己 DPI 感知，否则 125% 缩放下
tk 坐标被虚拟化成 1/1.25，按物理坐标截图全部扑空。

## 坑 6：蒙版忘了平移对话区

窗口 = 顶部对话区（气泡）+ 宠物区，而精灵帧的蒙版是从帧图（宠物区
局部坐标）构建的。并进气泡多边形后 `setMask` 之前，**必须
`translated(0, 对话区高)`**——踩过：忘平移 = 宠物下半身整块落在
蒙版外被裁掉，看起来像"宠物缺了半截"。

## 坑 7：双重镜像（蒙版与显示错位）

走路朝左时精灵被裁得只剩碎片。根因是镜像做了两次：

- `_anim_image` 在 flip 时**已返回镜像帧图**（蒙版按它构建）；
- `paintEvent` 又套了一层 `QTransform` 水平镜像。

结果显示与蒙版左右错位——不对称帧约 38% 的像素落在蒙版外被裁。
修复：**镜像只在帧图层做一次**（帧图与蒙版同源），paint 不再套镜像
变换。回归测试断言两个朝向下蒙版 100% 覆盖绘制像素
（`test_mask_covers_painted_walk_both_facings`）。

原则：同一几何变换只允许出现在一层，蒙版与绘制必须消费同一份
变换后的图像。

## 坑 8：软 alpha 回来了，资产链跟着简化

`WA_TranslucentBackground` 真合成后，帧不再需要二值化 alpha——
逐帧 PNG 直接保留软 alpha（阴影/光效/抗锯齿边缘都能显示）。键色
方案时代的五道资产工序（二值化/渗色/腐蚀/空腔判罚/透明像素 RGB
清零）全部退役，资产格式从"1536x1872 大图集 + 左右朝向烘焙两行"
简化为"逐帧 PNG + 运行时镜像"（朝向翻转在帧图层做，见坑 7）。

## 坑 9：呼吸/挤压动画的锚点

呼吸 = 整帧 `scaleY` 微变形（0.98~1.02 正弦），**锚点必须设在脚底**
（`foot` y 坐标），否则宠物会"悬浮"；被拎起/落地的 squash = 落地
瞬间脉冲挤压（scaleY<1, scaleX>1，按落地速度衰减），同样锚脚底。
变换在 `paintEvent` 里对帧图整体应用，蒙版用放松余量（呼吸形变量
小于蒙版预留边距）避免逐帧重建蒙版——只在精灵位移/换帧时重建。

## 收尾对比

| | tk 键色 | PySide6 逐像素 |
| --- | --- | --- |
| alpha | 二值（键色判定） | 8bit 真 alpha |
| 半透明 | stipple/镂空位图近似 | 原生 |
| 镜像 | 构建期烘焙两套帧 | 运行时帧图层一次 |
| 资产工序 | 5 道伺服工序 | 保留软 alpha 即可 |
| 依赖 | 零（标准库） | PySide6 |
| 典型死法 | 暗边/色晕/整帧重合成闪帧 | QBitmap AV、浅引用、双镜像 |

结论：Windows 上做精灵级桌宠，直接上 PySide6；tkinter 键色方案只
配当零依赖兜底。
