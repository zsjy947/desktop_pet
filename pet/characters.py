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
    # ---- 明星小姐姐（reference/pictures） ----
    dict(
        id='guan', name='关晓彤', kind='girl',
        hair='#2E2B33', hair_dark='#211F26', style='ponytail',
        eye='#5A4636', outfit='shirt_skirt', c1='#BFD7F0', c2='#F7F5EF',
        leg='#C9DEF2', shoes='#F2F2EE',
        acc='bow', acc_color='#2A2730',
        phrases=_p(
            talk=['长腿也要一步一步好好走嘛', '今天这身衬衫，好看吗？',
                  '学习累了，就来找我玩呀'],
            feed=['谢谢啦！正饿着呢！', '唔，补充能量，满血复活！'],
            pet=['哈哈，头发都被你摸乱啦', '嘿嘿，再多摸一会儿也行'],
            sleep=['先眯一会儿……别吵我哦', '困了困了，晚安～'],
            wake=['嗯？几点了？！', '醒啦——继续元气满满！'],
            drop=['哇！还好反应快！', '哎呀，膝盖磕了一下'],
            switch=['换我上场啦！'],
        ),
    ),
    dict(
        id='qiwei', name='戚薇', kind='girl',
        hair='#6B4A38', hair_dark='#54382A', style='long',
        eye='#6B4A38', outfit='dress', c1='#C7D9E6', c2='#E8B7C6',
        leg=SKIN, shoes='#D8A7B0',
        acc='flowerband', acc_color='#E8A7B8',
        phrases=_p(
            talk=['花好看，你也是～', '甜一点的日子才好过嘛',
                  '今天也要做甜甜的女孩子哦'],
            feed=['唔，甜甜的，谢谢～', '好吃！心情都变甜了'],
            pet=['嘿嘿，再摸摸也可以哦', '呀，花环要歪啦'],
            sleep=['晚安啦，好梦～', '先睡啦，梦里见'],
            wake=['早呀～今天也要甜甜的', '唔……让我再赖一会儿嘛'],
            drop=['哎呀呀，摔了个小跟头', '哇啊——裙子都飞起来了'],
            switch=['又见面啦，想我了吗？'],
        ),
    ),
    dict(
        id='mao', name='毛晓彤', kind='girl',
        hair='#26242B', hair_dark='#1D1B22', style='long',
        eye='#4A3A30', outfit='dress', c1='#FAFAF6', c2='#E8E4DC',
        leg='#F7F5EF', shoes='#2A2730',
        acc='headband', acc_color='#FBFAF6', necklace=True,
        phrases=_p(
            talk=['今天的风，软软的呢', '安安静静地，陪你一会儿',
                  '白裙子要干干净净的才好'],
            feed=['谢谢……我会好好珍藏的', '嗯，很温柔的味道'],
            pet=['唔……发饰都要歪了', '……嗯，很舒服呢'],
            sleep=['晚安，愿星星守护你', '夜安……做个安静的梦'],
            wake=['早安……昨晚睡得好吗', '嗯，新的一天，请多关照'],
            drop=['呀……膝盖有点疼', '呜……珍珠项链都飞出去了'],
            switch=['嗯，请多指教。'],
        ),
    ),
    dict(
        id='wang', name='王玉雯', kind='girl',
        hair='#4A3830', hair_dark='#382A24', style='long',
        eye='#5A4636', outfit='tutu', c1='#D98A93', c2='#E8ADB4',
        leg='#E3A0A8', shoes='#D98A93',
        acc='flowers', acc_color='#F2A9B8',
        phrases=_p(
            talk=['踮起脚尖，梦就开始旋转', '今天也要优雅地度过哦',
                  '想听一段天鹅湖吗？'],
            feed=['谢谢～你真贴心呀', '跳完舞确实饿了呢'],
            pet=['呀，发饰别弄坏啦', '嗯……像谢幕一样开心呢'],
            sleep=['夜太美，先睡啦……', '晚安，愿星光伴你'],
            wake=['唔……演出开始了吗？', '呵，睡了个美容觉'],
            drop=['哎呀——还好舞步够稳！', '旋转落地，完美……大概'],
            switch=['登台喽——请多鼓掌！'],
        ),
    ),
    dict(
        id='zhao', name='赵今麦', kind='girl',
        hair='#3E3228', hair_dark='#2E241C', style='long',
        eye='#5A4636', outfit='dress', c1='#1E6B4E', c2='#15523B',
        leg=SKIN, shoes='#E8D9C8',
        phrases=_p(
            talk=['绿裙子配今天的心情，正好', '忙归忙，也要记得喝水呀',
                  '偶尔发发呆，也很重要哦'],
            feed=['谢谢～你怎么这么好', '唔，能量满了，继续！'],
            pet=['哈哈，好啦好啦，别闹啦', '再摸头要骄傲了哦'],
            sleep=['我眯一会儿，你看家', '晚安，明天见'],
            wake=['嗯～睡得刚刚好', '醒啦，继续保持优雅'],
            drop=['哎哟！……没事没事', '哇，差点摔个优雅跤'],
            switch=['登场！请多关照～'],
        ),
    ),
    dict(
        id='chen', name='陈都灵', kind='girl',
        hair='#26242B', hair_dark='#1D1B22', style='long',
        eye='#4A3A30', outfit='shorts', c1='#FAFAF6', c2='#F2EFE6',
        leg=SKIN, shoes='#F2F2EE',
        glasses=True, tie='#4C7A3E',
        phrases=_p(
            talk=['书看累了，歇一会儿', '这道题……其实我也不太会',
                  '眼镜擦干净，才看得清你呀'],
            feed=['谢谢，你也很优秀哦', '唔，甜食有助于思考呢'],
            pet=['喂喂，眼镜要掉啦', '呵呵，勉为其难让你摸一下'],
            sleep=['伏案小憩……别拔我眼镜', '先睡五分钟……Zzz'],
            wake=['啊，我睡着了吗？失礼了', '唔，精神回来了'],
            drop=['哎呀，眼镜没事就好', '哇！……人没事就好'],
            switch=['已上线，有问题请提问～'],
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
