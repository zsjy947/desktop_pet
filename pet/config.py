# -*- coding: utf-8 -*-
"""所有可调参数集中在这里，改这里即可定制你的宠物。"""

# ---------- 窗口 ----------
WINDOW_SIZE = 160        # 正方形窗口边长（上半部分留给头顶气泡，透明且可点击穿透）
PET_FOOT_Y = 150         # 宠物脚底在画布中的 y 坐标
FPS = 30                 # 动画帧率

# 透明键色：画布背景即“透明色”，显示时会抠掉，注意不要与宠物配色重复
KEY_COLOR = '#010101'

# ---------- 行为 ----------
WALK_SPEED = 2.2         # 走路速度（像素/帧）
GRAVITY = 0.6            # 被拖到半空松手后的下落加速度（像素/帧^2）
BOUNCE = 0.35            # 落地反弹系数
BLINK_PERIOD = 4.0       # 平均隔几秒眨一次眼
BLINK_DURATION = 0.15    # 眨眼持续秒数
IDLE_TALK_MIN = 25.0     # 随机碎碎念的最小间隔（秒）
IDLE_TALK_MAX = 50.0
SAY_DURATION = 3.0       # 气泡显示时长（秒）
NAP_HOUR_START = 23      # 深夜自动打盹：23 点之后
NAP_HOUR_END = 7         # ……到第二天早上 7 点前

# ---------- 配色 ----------
HEART = '#FF6B81'        # 爱心粒子
HEART_FADED = '#FFB9C4'
BUBBLE_BG = '#D6EAF8'    # 气泡底（tk 层走 stipple 半透明；Qt 层真 alpha）
BUBBLE_EDGE = '#5DADE2'  # 气泡边框（浅蓝）
BUBBLE_FG = '#17324D'    # 气泡文字（深蓝黑，浅底上清晰）
BUBBLE_STIPPLE = 'gray75'  # 兜底镂空；tk 层主用 drawutil 的 87.5% 自定义位图

FONT = ('Microsoft YaHei UI', 10)
