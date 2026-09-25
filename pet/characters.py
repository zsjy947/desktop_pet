# -*- coding: utf-8 -*-
"""角色库：宝可梦线的角色全部来自 anims/（v2 动画包，见 pet/anims.py）
与 hatched/（图集，见 pet/hatch_sprites.py），本模块只承载人物线
（hatch-pet 分支）共享的少女绘制参数，本分支 CHARACTERS 为空。

外观参数说明（供人物线分支的 girl 预设使用）：
  hair/hair_dark  头发主色 / 描边（阴影）色
  style           发型：bob 短发 | long 长发 | xlong 超长发 |
                  twin 双马尾 | ponytail 马尾 | buns 侧发髻
  eye             瞳色
  outfit          服装：dress 连衣裙 | shirt_skirt 衬衫+裙 |
                  shorts 衬衫+短裤 | top_skirt 上衣+短裙 |
                  coat 大衣 | kimono 和服 | tutu 芭蕾纱裙
  c1/c2           服装主色 / 辅色（裙摆、领结、滚边……）
  leg             腿部颜色（肤色=F7D7C4，或长筒袜/裤袜颜色）
  shoes           鞋子颜色
  acc             头饰：bow 蝴蝶结 | hat 宽檐帽 | beanie 毛线帽 |
                  headband 发箍+头纱 | flowerband 花环发带 | flowers 花朵
  acc_color       头饰颜色
  glasses/necklace/scarf/tie/braid  眼镜 / 珍珠项链 / 围巾 / 领带 / 侧编发
"""
from collections import OrderedDict

SKIN = '#F9DCC4'          # 少女肤色
SKIN_DARK = '#D9A886'     # 肤色描边
FACE_LINE = '#8A6B5C'     # 五官描边

# 人物预设（中野二乃/莉莉艾/小光/竹兰/露莎米奈）只在 hatch-pet
# （人物线）分支；本分支是宝可梦线，角色只有 anims/ 宝可梦。
GIRLS = []

# id -> 预设（少女预设的 photo 字段指向 assets/ 下由
# tools/build_sprites.py 生成的图片精灵，缺失时回落到 Canvas 绘制）
CHARACTERS = OrderedDict((p['id'], p) for p in GIRLS)
