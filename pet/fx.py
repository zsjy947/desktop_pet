# -*- coding: utf-8 -*-
"""粒子生成与推进：爱心 / Zzz / 宝可梦特效（电花、树叶、花朵…）。

只负责数据（dict 列表）；绘制在 drawutil.draw_particles。
k 为尺寸系数（相对 160 窗口），由调用方按窗口边长换算。
"""
import math
import random


def hearts(n=8, k=1.0):
    return [{'kind': 'heart',
             'x': 80 * k + random.uniform(-30 * k, 30 * k),
             'y': 70 * k + random.uniform(-15 * k, 15 * k),
             'vx': random.uniform(-8, 8),
             'vy': random.uniform(-55, -35),
             'age': 0.0,
             'life': random.uniform(1.2, 1.8),
             'size': random.randint(10, 16)} for _ in range(n)]


def zzz(k=1.0):
    return [{'kind': 'zzz',
             'x': 108 * k + random.uniform(-6 * k, 6 * k),
             'y': 60 * k,
             'vx': random.uniform(2, 8),
             'vy': -22.0,
             'age': 0.0,
             'life': 2.4,
             'size': 10}]


def burst(kind, n=6, k=1.0):
    """特效粒子雨（宝可梦专属动作/喂树果等）。"""
    return [{'kind': kind,
             'x': 80 * k + random.uniform(-45 * k, 45 * k),
             'y': 80 * k + random.uniform(-35 * k, 5 * k),
             'vx': random.uniform(-12, 12),
             'vy': random.uniform(-45, -20),
             'age': 0.0,
             'life': random.uniform(0.9, 1.4),
             'size': random.randint(11, 17)} for _ in range(n)]


def advance(particles, dt, t):
    """推进一帧并过滤到期的粒子，返回新列表。"""
    for p in particles:
        p['age'] += dt
        p['x'] += (p['vx'] + 12 * math.sin(t * 2 + p['y'])) * dt
        p['y'] += p['vy'] * dt
    return [p for p in particles if p['age'] < p['life']]
