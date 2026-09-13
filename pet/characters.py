# -*- coding: utf-8 -*-
"""角色库：橘猫 + 由 reference/pictures 参考图转化的 Q 版少女们。

每个少女预设是一组参数（发色/发型/瞳色/服装/腿袜/头饰……），
由 girl_sprites.py 参数化画出；每个角色都有自己的一套台词。

外观参数说明：
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

from . import config as C

SKIN = '#F9DCC4'          # 少女肤色
SKIN_DARK = '#D9A886'     # 肤色描边
FACE_LINE = '#8A6B5C'     # 五官描边

CAT_SWITCH = ['喵～我回来啦！', '喵？叫我出来玩吗？']


def _p(talk=(), feed=(), pet=(), sleep=(), wake=(), drop=(), switch=()):
    return dict(talk=list(talk), feed=list(feed), pet=list(pet),
                sleep=list(sleep), wake=list(wake), drop=list(drop),
                switch=list(switch))


CAT = dict(
    id='cat', name='橘猫', kind='cat',
    phrases=_p(
        talk=C.PHRASES, feed=C.FEED_PHRASES, pet=C.PET_PHRASES,
        sleep=C.SLEEP_PHRASES, wake=C.WAKE_PHRASES, drop=C.DROP_PHRASES,
        switch=CAT_SWITCH,
    ),
)

# 人物预设（中野二乃/莉莉艾/小光/竹兰/露莎米奈）只在 hatch-pet
# （人物线）分支；本分支是宝可梦线，只保留橘猫 + hatched/ 宝可梦。
GIRLS = []


# id -> 预设（橘猫排最前）；少女预设的 photo 字段指向 assets/ 下
# 由 tools/build_sprites.py 生成的图片精灵（缺失时回落到 Canvas 绘制）
for _preset in GIRLS:
    _preset.setdefault('photo', _preset['id'])

CHARACTERS = OrderedDict((p['id'], p) for p in [CAT] + GIRLS)


def get(char_id):
    """按 id 取角色预设，未知 id 回落到橘猫。"""
    return CHARACTERS.get(char_id, CAT)
