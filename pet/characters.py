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

GIRLS = [
    # ---- 动漫角色（reference/pictures） ----
    dict(
        id='nino', name='中野二乃', kind='girl',
        hair='#E97A5C', hair_dark='#C2543A', style='bob',
        eye='#4E7FB0', outfit='dress', c1='#8A55B4', c2='#54416E',
        leg='#46424E', shoes='#35323E',
        acc='bow', acc_color='#3A3440',
        phrases=_p(
            talk=['哼，才不是特意来陪你的', '无聊……陪我说会儿话',
                  '今天也这么忙吗？真是的'],
            feed=['别误会，我只是刚好饿了', '嗯……味道还算不错',
                  '下次还要喂我哦'],
            pet=['呀、摸什么摸！……又不是不喜欢', '头、头饰要歪了啦',
                 '……就、就再摸一下'],
            sleep=['我要睡了，不许偷看', '晚安……哼'],
            wake=['谁允许你叫醒我的？', '哼，我本来就睡够了'],
            drop=['呀！……看什么看，没站稳而已', '放、放下我！'],
            switch=['哼，找我有什么事吗？'],
        ),
    ),
    dict(
        id='lillie', name='莉莉艾', kind='girl',
        hair='#F4E3A7', hair_dark='#D9BE7A', style='long', braid=True,
        eye='#7FA86B', outfit='dress', c1='#FBFBF4', c2='#A9C9E2',
        leg='#F7F5EF', shoes='#EDE9DC',
        acc='hat', acc_color='#A9C9E2',
        phrases=_p(
            talk=['那个……今天也一起加油吧', '这里的一切都好新奇呢',
                  '大家都很温柔，我也想变勇敢'],
            feed=['谢、谢谢……我很喜欢', '呜……太好吃了吧'],
            pet=['呀……帽子要歪掉了啦', '唔……谢谢你'],
            sleep=['晚安，做个好梦……', '我有点困了……晚安'],
            wake=['咦？我睡着了吗？抱歉……', '早安……嘿嘿'],
            drop=['呀啊！吓、吓我一跳……', '呜哇——还好接住了'],
            switch=['请、请多指教哦……'],
        ),
    ),
    dict(
        id='dawn', name='小光', kind='girl',
        hair='#46618F', hair_dark='#35496E', style='long',
        eye='#5B8DB8', outfit='top_skirt', c1='#3A3A42', c2='#F5F2EA',
        leg=SKIN, shoes='#4A4A52',
        acc='beanie', acc_color='#F7F5EF', scarf='#D9536F',
        phrases=_p(
            talk=['出发出发！今天也要大冒险！', '呼哇——屏幕那头就是新大陆！',
                  '遇到难关之前，先休息一下嘛'],
            feed=['哇！谢谢你，我开动了！', '能量补满，元气十足！'],
            pet=['嘿嘿，被你夸得不好意思啦', '再摸摸头就更有干劲了！'],
            sleep=['呼啊……明天还要早起呢……', '先眯五分钟……Zzz'],
            wake=['唔哇！我睡过头了吗？！', '哦哦——精神百倍！'],
            drop=['哇呀！……安全着陆，成功！', '空中转体，落地——好痛'],
            switch=['交给我吧，包在我身上！'],
        ),
    ),
    dict(
        id='yui', name='由比滨结衣', kind='girl',
        hair='#E89A8A', hair_dark='#C97A6E', style='bob',
        eye='#B5495A', outfit='kimono', c1='#C96A83', c2='#8E3A4E',
        leg=SKIN, shoes='#8E3A4E',
        acc='flowers', acc_color='#F7F3EA',
        phrases=_p(
            talk=['呀哈罗-！今天也元气满满！', '唔嘿嘿，和你在一起最开心了',
                  '要来点团子吗？我请客！'],
            feed=['哇咔！我最喜欢这个了！', '好吃到跳起来了啦～'],
            pet=['诶嘿嘿……头发很好摸吗？', '呀，被摸头会害羞的啦'],
            sleep=['呼……Zzz……晚安……', '眼皮打架了……先睡啦……'],
            wake=['唔哇！现在几点了？！', '呼哇，睡得超香！'],
            drop=['呀啊啊——屁股好痛……', '呜哇，吓死我了啦！'],
            switch=['呀哈罗-！交给我吧！'],
        ),
    ),
    dict(
        id='cynthia', name='竹兰', kind='girl',
        hair='#F0D582', hair_dark='#C9AE62', style='buns',
        eye='#8A929E', outfit='coat', c1='#35323E', c2='#23212A',
        leg=SKIN, shoes='#2A2730',
        phrases=_p(
            talk=['你好，今天也请多指教。', '冠军的假期，就在这里度过吧',
                  '历史与传说，总是令人着迷呢'],
            feed=['谢谢，你很有心呢。', '呵呵，很合我的口味'],
            pet=['呵呵……发髻可别弄乱哦', '被你摸头，还真拿你没办法'],
            sleep=['那么，失陪片刻……晚安', '夜深了，你也早点休息'],
            wake=['哎呀……让你久等了', '嗯，休息得刚刚好'],
            drop=['哎呀，稍微失态了……', '呵，这种程度不算什么'],
            switch=['呵呵，又见面了。'],
        ),
    ),
    dict(
        id='lusamine', name='露莎米奈', kind='girl',
        hair='#F2E9B0', hair_dark='#D4C888', style='xlong',
        eye='#5FA86F', outfit='dress', c1='#FAFAF2', c2='#D9C463',
        leg='#F5F5F0', shoes='#FAFAF2',
        phrases=_p(
            talk=['真可爱……你也这么觉得吧？', '美丽的东西，要好好珍藏呢',
                  '遥远的世界，也很让人想念呢'],
            feed=['谢谢……你真温柔', '心意收到了，我很开心'],
            pet=['呵呵……孩子气的举动呢', '嗯……再靠近一点也可以哦'],
            sleep=['晚安……愿你有个好梦', '夜色真美，先睡了呢'],
            wake=['早安……睡得还好吗？', '呵，你一直守着我吗？'],
            drop=['哎呀……裙摆都乱了', '……真是淘气呢'],
            switch=['想我了吗？呵呵。'],
        ),
    ),
]

# id -> 预设（橘猫排最前）；少女预设的 photo 字段指向 assets/ 下
# 由 tools/build_sprites.py 生成的图片精灵（缺失时回落到 Canvas 绘制）
for _preset in GIRLS:
    _preset.setdefault('photo', _preset['id'])

CHARACTERS = OrderedDict((p['id'], p) for p in [CAT] + GIRLS)


def get(char_id):
    """按 id 取角色预设，未知 id 回落到橘猫。"""
    return CHARACTERS.get(char_id, CAT)
