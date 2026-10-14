"""Zai (progressive or again) before a verb, a verb or qing before a pronoun
object, and request phrases keep explicit readings and moderate exact ranks."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from test_daily_whitespace_phrases import read_rows

# Readings are written as they are typed, without a syllable separator.
REQUESTED = (
    ("zaideng", "在等", "在等", 420),
    ("zaideng", "再等", "再等", 380),
    ("zaice", "在册", "在冊", 300),
    ("zaifa", "在发", "在發", 180),
    ("zaikai", "在开", "在開", 400),
    ("zaikai", "再开", "再開", 340),
    ("zaiguan", "在关", "在關", 300),
    ("zaiguan", "再关", "再關", 260),
    ("zaimo", "在摸", "在摸", 280),
    ("zaimo", "再摸", "再摸", 220),
    ("qingwo", "请我", "請我", 380),
)

# Phrases of the same patterns for which the engine offered no whole candidate
# or a rarer homophone first.
RELATED = (
    ("zaixi", "在洗", "在洗", 340),
    ("zaixi", "再洗", "再洗", 280),
    ("zaichuan", "在传", "在傳", 320),
    ("zaichuan", "再传", "再傳", 280),
    ("zaitiao", "在调", "在調", 320),
    ("zaitiao", "再调", "再調", 300),
    ("zaitiao", "在跳", "在跳", 280),
    ("zaitiao", "再跳", "再跳", 240),
    ("zaihua", "在画", "在畫", 260),
    ("zaishan", "在删", "在刪", 280),
    ("zaishan", "再删", "再刪", 260),
    ("zaisong", "在送", "在送", 300),
    ("zaisong", "再送", "再送", 280),
    ("zaidu", "在堵", "在堵", 220),
    ("zaizou", "在走", "在走", 300),
    ("zaizou", "再走", "再走", 240),
    ("zaiku", "在哭", "在哭", 340),
    ("zaiku", "再哭", "再哭", 260),
    ("zaixiao", "在笑", "在笑", 340),
    ("zaixiao", "再笑", "再笑", 240),
    ("zaijiao", "在叫", "在叫", 340),
    ("zaijiao", "在教", "在教", 320),
    ("zaijiao", "再叫", "再叫", 300),
    ("zaijiao", "再教", "再教", 260),
    ("zaijiang", "在讲", "在講", 360),
    ("zaijiang", "再讲", "再講", 320),
    ("zaitan", "在谈", "在談", 340),
    ("zaitan", "再谈", "再談", 320),
    ("zaifei", "在飞", "在飛", 260),
    ("zaipai", "在拍", "在拍", 320),
    ("zaipai", "在排", "在排", 300),
    ("zaipai", "再拍", "再拍", 280),
    ("zaipai", "再排", "再排", 240),
    ("zaishou", "在收", "在收", 260),
    ("zaishou", "再收", "再收", 240),
    ("zaisuan", "在算", "在算", 300),
    ("zaisuan", "再算", "再算", 280),
    ("zailian", "在练", "在練", 300),
    ("zailian", "再练", "再練", 280),
    ("zaizhui", "在追", "在追", 300),
    ("zaizhui", "再追", "再追", 240),
    ("zaibei", "在背", "在背", 260),
    ("zaibei", "再背", "再背", 240),
    ("zaiqiang", "在抢", "在搶", 280),
    ("zaiqiang", "再抢", "再搶", 240),
    ("zaima", "在骂", "在罵", 300),
    ("zaima", "再骂", "再罵", 240),
    ("zaichao", "在吵", "在吵", 300),
    ("zaichao", "再吵", "再吵", 280),
    ("zaichao", "在炒", "在炒", 240),
    ("zaishao", "在烧", "在燒", 260),
    ("zaishao", "再烧", "再燒", 220),
    ("zaizhu", "在煮", "在煮", 260),
    ("zaizhu", "再煮", "再煮", 220),
    ("zaichong", "在充", "在充", 240),
    ("zaichong", "再充", "再充", 220),
    ("zailu", "在录", "在錄", 280),
    ("zailu", "再录", "再錄", 260),
    ("zaibo", "在播", "在播", 260),
    ("zaina", "再拿", "再拿", 240),
    ("zaina", "在拿", "在拿", 220),
    ("zaifang", "在放", "在放", 300),
    ("zaifang", "再放", "再放", 280),
    ("zaihuan", "再换", "再換", 320),
    ("zaihuan", "在换", "在換", 300),
    ("zaidai", "在带", "在帶", 260),
    ("zaidai", "再带", "再帶", 240),
    ("zaijie", "再接", "再接", 280),
    ("zaijie", "在接", "在接", 260),
    ("zaijie", "再借", "再借", 240),
    ("zaibang", "在帮", "在幫", 300),
    ("zaibang", "再帮", "再幫", 280),
    ("zaipei", "在陪", "在陪", 280),
    ("zaipei", "再陪", "再陪", 240),
    ("zaiyue", "再约", "再約", 320),
    ("zaiding", "再定", "再定", 320),
    ("zaiding", "再订", "再訂", 280),
    ("zaiding", "在盯", "在盯", 260),
    ("zaiding", "在订", "在訂", 240),
    ("zaiban", "在办", "在辦", 320),
    ("zaiban", "再办", "再辦", 280),
    ("zaibao", "再报", "再報", 240),
    ("zaitian", "在填", "在填", 260),
    ("zaitian", "再填", "再填", 240),
    ("zaidian", "再点", "再點", 320),
    ("zaidian", "在点", "在點", 280),
    ("zaian", "再按", "再按", 300),
    ("zaizhang", "在涨", "在漲", 320),
    ("zaizhang", "再涨", "再漲", 300),
    ("zaidie", "在跌", "在跌", 300),
    ("zaidie", "再跌", "再跌", 280),
    ("zaibian", "在变", "在變", 300),
    ("zaibian", "再变", "再變", 240),
    ("zaidong", "在动", "在動", 300),
    ("zaidong", "再动", "再動", 280),
    ("zaizhuan", "在转", "在轉", 300),
    ("zaizhuan", "再转", "再轉", 280),
    ("zaizhuan", "在赚", "在賺", 260),
    ("zaizhuan", "再赚", "再賺", 240),
    ("zaiao", "在熬", "在熬", 260),
    ("zaiao", "再熬", "再熬", 240),
    ("zaichou", "在抽", "在抽", 260),
    ("zaichou", "再抽", "再抽", 240),
    ("zaihan", "在喊", "在喊", 260),
    ("zaihan", "再喊", "再喊", 240),
    ("zairen", "再忍", "再忍", 260),
    ("zairen", "在忍", "在忍", 220),
    ("zaituo", "再拖", "再拖", 300),
    ("zaituo", "在拖", "在拖", 280),
    ("zaiguang", "在逛", "在逛", 300),
    ("zaiguang", "再逛", "再逛", 260),
    ("zaisou", "在搜", "在搜", 300),
    ("zaisou", "再搜", "再搜", 280),
    ("zaikao", "在考", "在考", 300),
    ("zaikao", "再考", "再考", 280),
    ("zaizheng", "在整", "在整", 260),
    ("zaizheng", "再整", "再整", 240),
    ("zaijian", "在减", "在減", 240),
    ("zaishu", "在数", "在數", 260),
    ("zaishu", "在输", "在輸", 240),
    ("zaishang", "在上", "在上", 320),
    ("zaishang", "再上", "再上", 300),
    ("zaixia", "再下", "再下", 180),
    ("zaiwen", "在问", "在問", 320),
    ("zaicun", "在存", "在存", 240),
    ("zaicun", "再存", "再存", 220),
    ("zailing", "在领", "在領", 240),
    ("zailing", "再领", "再領", 220),
    ("zaitie", "在贴", "在貼", 240),
    ("zaitie", "再贴", "再貼", 220),
    ("zaica", "在擦", "在擦", 240),
    ("zaica", "再擦", "再擦", 220),
    ("zaisao", "在扫", "在掃", 240),
    ("zaisao", "再扫", "再掃", 220),
    ("zaishai", "在晒", "在曬", 240),
    ("zaikui", "在亏", "在虧", 260),
    ("zaikui", "再亏", "再虧", 220),
    ("zaifen", "再分", "再分", 240),
    ("zaichai", "在拆", "在拆", 240),
    ("zaichai", "再拆", "再拆", 220),
    ("zaiwa", "在挖", "在挖", 240),
    ("zaiyang", "在养", "在養", 240),
    ("zaiwei", "在喂", "在餵", 240),
    ("zaihong", "在哄", "在哄", 240),
    ("zaiquan", "在劝", "在勸", 240),
    ("zaiquan", "再劝", "再勸", 220),
    ("zaicui", "在催", "在催", 280),
    ("zaicui", "再催", "再催", 260),
    ("zaicai", "在猜", "在猜", 240),
    ("zaicai", "再猜", "再猜", 220),
    ("zaigua", "在挂", "在掛", 240),
    ("zaigua", "再挂", "再掛", 220),
    ("zaicheng", "再撑", "再撐", 260),
    ("zaicheng", "在撑", "在撐", 240),
    ("zaiguanzhu", "在关注", "在關注", 360),
    ("zaimoyu", "在摸鱼", "在摸魚", 340),
    ("dengjizaice", "登记在册", "登記在冊", 300),
    ("zaicerenyuan", "在册人员", "在冊人員", 260),
    ("jiaowo", "教我", "教我", 400),
    ("jiaoni", "教你", "教你", 400),
    ("jiaota", "教他", "教他", 380),
    ("jiaota", "教她", "教她", 360),
    ("pianwo", "骗我", "騙我", 420),
    ("pianni", "骗你", "騙你", 420),
    ("pianta", "骗他", "騙他", 360),
    ("pianta", "骗她", "騙她", 340),
    ("mawo", "骂我", "罵我", 380),
    ("mani", "骂你", "罵你", 360),
    ("mata", "骂他", "罵他", 340),
    ("mata", "骂她", "罵她", 320),
    ("songwo", "送我", "送我", 420),
    ("songni", "送你", "送你", 440),
    ("songta", "送他", "送他", 360),
    ("songta", "送她", "送她", 340),
    ("jiewo", "接我", "接我", 440),
    ("jiewo", "借我", "借我", 420),
    ("jieni", "接你", "接你", 420),
    ("jieni", "借你", "借你", 380),
    ("jieta", "接他", "接他", 360),
    ("jieta", "接她", "接她", 340),
    ("yuewo", "约我", "約我", 380),
    ("yueni", "约你", "約你", 380),
    ("yueta", "约他", "約他", 340),
    ("yueta", "约她", "約她", 320),
    ("guaiwo", "怪我", "怪我", 440),
    ("guaini", "怪你", "怪你", 420),
    ("guaita", "怪他", "怪他", 360),
    ("guaita", "怪她", "怪她", 340),
    ("liwo", "理我", "理我", 420),
    ("lini", "理你", "理你", 400),
    ("lita", "理他", "理他", 360),
    ("haini", "害你", "害你", 380),
    ("haita", "害他", "害他", 340),
    ("haita", "害她", "害她", 320),
    ("cuiwo", "催我", "催我", 400),
    ("cuini", "催你", "催你", 380),
    ("cuita", "催他", "催他", 340),
    ("cuita", "催她", "催她", 320),
    ("hanwo", "喊我", "喊我", 380),
    ("hanni", "喊你", "喊你", 360),
    ("hanta", "喊他", "喊他", 340),
    ("hanta", "喊她", "喊她", 320),
    ("kuani", "夸你", "誇你", 380),
    ("kuata", "夸他", "誇他", 340),
    ("kuata", "夸她", "誇她", 320),
    ("xiawo", "吓我", "嚇我", 420),
    ("xiani", "吓你", "嚇你", 380),
    ("fanni", "烦你", "煩你", 400),
    ("fanta", "烦他", "煩他", 340),
    ("fanta", "烦她", "煩她", 320),
    ("xinwo", "信我", "信我", 400),
    ("xinni", "信你", "信你", 420),
    ("xinta", "信他", "信他", 360),
    ("xinta", "信她", "信她", 340),
    ("shuowo", "说我", "說我", 420),
    ("shuoni", "说你", "說你", 440),
    ("shuota", "说他", "說他", 400),
    ("shuota", "说她", "說她", 380),
    ("huiwo", "回我", "回我", 420),
    ("huini", "回你", "回你", 400),
    ("huita", "回他", "回他", 340),
    ("huita", "回她", "回她", 320),
    ("baowo", "抱我", "抱我", 380),
    ("baoni", "抱你", "抱你", 380),
    ("baota", "抱他", "抱他", 320),
    ("xuanni", "选你", "選你", 340),
    ("xuanta", "选他", "選他", 320),
    ("xuanta", "选她", "選她", 300),
    ("dongwo", "懂我", "懂我", 400),
    ("dongni", "懂你", "懂你", 420),
    ("dongta", "懂他", "懂他", 340),
    ("dongta", "懂她", "懂她", 320),
    ("kaowo", "靠我", "靠我", 380),
    ("kaoni", "靠你", "靠你", 400),
    ("kaota", "靠他", "靠他", 340),
    ("kaota", "靠她", "靠她", 320),
    ("tiwo", "替我", "替我", 260),
    ("tini", "替你", "替你", 260),
    ("tita", "替他", "替他", 260),
    ("tita", "替她", "替她", 240),
    ("zhuiwo", "追我", "追我", 380),
    ("zhuini", "追你", "追你", 380),
    ("qiwo", "气我", "氣我", 400),
    ("qini", "气你", "氣你", 380),
    ("qita", "气他", "氣他", 300),
    ("qita", "气她", "氣她", 280),
    ("peiwo", "赔我", "賠我", 380),
    ("peini", "赔你", "賠你", 360),
    ("peita", "赔他", "賠他", 320),
    ("peita", "赔她", "賠她", 300),
    ("xianni", "嫌你", "嫌你", 340),
    ("xianta", "嫌他", "嫌他", 320),
    ("xianta", "嫌她", "嫌她", 300),
    ("hongwo", "哄我", "哄我", 380),
    ("hongni", "哄你", "哄你", 360),
    ("hongta", "哄她", "哄她", 340),
    ("hongta", "哄他", "哄他", 320),
    ("yangni", "养你", "養你", 380),
    ("yangta", "养他", "養他", 300),
    ("yangta", "养她", "養她", 280),
    ("qingren", "请人", "請人", 300),
    ("qingchi", "请吃", "請吃", 260),
    ("qinghe", "请喝", "請喝", 240),
    ("qingshuo", "请说", "請說", 300),
    ("qingjiang", "请讲", "請講", 240),
    ("qinghui", "请回", "請回", 260),
    ("qingqu", "请去", "請去", 80),
    ("qinghuifu", "请回复", "請回覆", 360),
    ("qingchashou", "请查收", "請查收", 400),
    ("qingwochi", "请我吃", "請我吃", 320),
    ("qingwohe", "请我喝", "請我喝", 300),
    ("huiwoyixia", "回我一下", "回我一下", 340),
    ("zaimai", "在买", "在買", 2),
    ("zaimai", "在卖", "在賣", 1),
    ("zaishua", "在刷", "在刷", 1),
    ("zaifan", "在翻", "在翻", 2),
    ("zaifan", "再翻", "再翻", 1),
    ("xiata", "吓他", "嚇他", 2),
    ("xiata", "吓她", "嚇她", 1),
    ("jieta", "借他", "借他", 2),
    ("jieta", "借她", "借她", 1),
    ("zaiguan", "在管", "在管", 2),
    ("zaiguan", "再管", "再管", 1),
    ("yangwo", "养我", "養我", 1),
    ("baota", "抱她", "抱她", 1),
    ("zaibu", "在补", "在補", 2),
    ("zaibu", "再补", "再補", 1),
    ("zainao", "在闹", "在鬧", 2),
    ("zainao", "再闹", "再鬧", 1),
    ("zaidu", "再读", "再讀", 1),
    ("qingdao", "请到", "請到", 2),
    ("zaidadianhua", "在打电话", "在打電話", 1),
    ("zailiao", "在聊", "在聊", 1),
    ("zaixue", "在学", "在學", 1),
    ("zaipin", "在拼", "在拼", 1),
    ("zhuita", "追她", "追她", 1),
    ("zaiban", "在搬", "在搬", 1),
)

ROWS = REQUESTED + RELATED

# pinyin, the commoner word (simplified, traditional), the added word
# (simplified, traditional) that stays below it.
COMMON_FIRST = (
    ("zaifa", "再发", "再發", "在发", "在發"),
    ("zaixiao", "在校", "在校", "在笑", "在笑"),
    ("zaima", "在吗", "在嗎", "在骂", "在罵"),
    ("zaiwen", "再问", "再問", "在问", "在問"),
    ("zaijian", "再见", "再見", "在减", "在減"),
    ("zaina", "在哪", "在哪", "再拿", "再拿"),
    ("zaiban", "再版", "再版", "在办", "在辦"),
    ("zaipei", "栽培", "栽培", "在陪", "在陪"),
    ("zaixia", "在下", "在下", "再下", "再下"),
    ("zaihua", "栽花", "栽花", "在画", "在畫"),
    ("qingqu", "轻取", "輕取", "请去", "請去"),
    ("jiaowo", "叫我", "叫我", "教我", "教我"),
    ("jiaoni", "叫你", "叫你", "教你", "教你"),
    ("jiaota", "叫他", "叫他", "教他", "教他"),
    ("liwo", "离我", "離我", "理我", "理我"),
    ("lini", "离你", "離你", "理你", "理你"),
    ("lita", "离他", "離他", "理他", "理他"),
    ("qita", "其他", "其他", "气他", "氣他"),
    ("peiwo", "陪我", "陪我", "赔我", "賠我"),
    ("peini", "陪你", "陪你", "赔你", "賠你"),
    ("peita", "陪他", "陪他", "赔他", "賠他"),
    ("qingren", "情人", "情人", "请人", "請人"),
    ("qinghe", "庆贺", "慶賀", "请喝", "請喝"),
    ("qingqu", "情趣", "情趣", "请去", "請去"),
    ("tiwo", "踢我", "踢我", "替我", "替我"),
    ("tini", "踢你", "踢你", "替你", "替你"),
    ("tita", "踢他", "踢他", "替他", "替他"),
    ("baota", "宝塔", "寶塔", "抱他", "抱他"),
    ("zaimai", "再买", "再買", "在买", "在買"),
    ("zaishua", "再刷", "再刷", "在刷", "在刷"),
    ("zaifan", "再犯", "再犯", "在翻", "在翻"),
    ("xiata", "下榻", "下榻", "吓他", "嚇他"),
    ("yangwo", "仰卧", "仰臥", "养我", "養我"),
    ("zaibu", "再不", "再不", "在补", "在補"),
    ("zaidu", "在读", "在讀", "再读", "再讀"),
    ("qingdao", "青岛", "青島", "请到", "請到"),
    ("baota", "宝塔", "寶塔", "抱她", "抱她"),
    ("zailiao", "再聊", "再聊", "在聊", "在聊"),
)

# pinyin, the added word (simplified, traditional), the existing word
# (simplified, traditional) it was asked to go above.
ABOVE = (
    ("qingwo", "请我", "請我", "轻握", "輕握"),
)

# Rows (pinyin, simplified) that stay at the lowest weights: at an ordinary
# weight they took the first place of a commoner word or changed a benchmark
# sentence. The last four change the first choice of their reading even so
# (zaixue, zhuita; zaipin and zaiban in the traditional dictionary), which was
# accepted when they were added.
LOW_WEIGHT = (
    ("zaimai", "在买"),
    ("zaimai", "在卖"),
    ("zaishua", "在刷"),
    ("zaifan", "在翻"),
    ("zaifan", "再翻"),
    ("xiata", "吓他"),
    ("xiata", "吓她"),
    ("jieta", "借他"),
    ("jieta", "借她"),
    ("zaiguan", "在管"),
    ("zaiguan", "再管"),
    ("yangwo", "养我"),
    ("baota", "抱她"),
    ("zaibu", "在补"),
    ("zaibu", "再补"),
    ("zainao", "在闹"),
    ("zainao", "再闹"),
    ("zaidu", "再读"),
    ("qingdao", "请到"),
    ("zaidadianhua", "在打电话"),
    ("zailiao", "在聊"),
    ("zaixue", "在学"),
    ("zaipin", "在拼"),
    ("zhuita", "追她"),
    ("zaiban", "在搬"),
)


class DailyZaiObjectTests(unittest.TestCase):
    def test_rows_are_distinct(self):
        self.assertEqual(len(ROWS), len({(row[0], row[1]) for row in ROWS}))
        self.assertEqual(len(ROWS), len({(row[0], row[2]) for row in ROWS}))
        # Homophones among the additions never tie.
        weights = {}
        for row in ROWS:
            weights.setdefault(row[0], []).append(row[3])
        for pinyin, values in weights.items():
            self.assertEqual(len(values), len(set(values)), pinyin)

    def test_explicit_readings_and_ranks_survive_rebuild(self):
        entries, _ = builder._parse_curated_daily_phrase_entries(
            (ROOT / "manifests/curated_daily_supplement_phrases.tsv").read_bytes(), 2)
        wanted = {(row[0], row[1]) for row in ROWS}
        selected = [entry for entry in entries if (entry[3], entry[0]) in wanted]
        regular, exact = builder._partition_curated_daily_post_rank_exact_entries(selected)
        self.assertFalse(regular)
        self.assertEqual(len(ROWS), len(exact))
        maps = ({}, {})
        builder._inject_curated_daily_post_rank_exact_entries(*maps, exact)
        builder._inject_curated_daily_post_rank_exact_entries(*maps, exact)
        for index, mapping in enumerate(maps, 1):
            self.assertEqual({(row[0], row[index]): row[3] for row in ROWS}, mapping)

    def test_generated_entries(self):
        for index, variant in enumerate(("sc", "tc"), 1):
            rows = read_rows(f"dict_clean_{variant}.txt")
            for row in ROWS:
                self.assertEqual([str(row[3]), "no_contains"], rows[(row[0], row[index])])

    def test_preserve_common_homophones(self):
        for variant, common_index, added_index in (("sc", 1, 3), ("tc", 2, 4)):
            rows = read_rows(f"dict_clean_{variant}.txt")
            for pair in COMMON_FIRST:
                self.assertGreater(int(rows[(pair[0], pair[common_index])][0]),
                                   int(rows[(pair[0], pair[added_index])][0]), pair)

    def test_requested_order(self):
        for variant, added_index, existing_index in (("sc", 1, 3), ("tc", 2, 4)):
            rows = read_rows(f"dict_clean_{variant}.txt")
            for pair in ABOVE:
                self.assertGreater(int(rows[(pair[0], pair[added_index])][0]),
                                   int(rows[(pair[0], pair[existing_index])][0]), pair)

    def test_low_weight_rows_stay_low(self):
        weights = {(row[0], row[1]): row[3] for row in ROWS}
        for key in LOW_WEIGHT:
            self.assertLessEqual(weights[key], 2, key)

    def test_no_fabricated_corpus_support(self):
        for index, variant in enumerate(("sc", "tc"), 1):
            rows = read_rows(f"dict_completion_prior_{variant}.txt")
            for row in ROWS:
                self.assertEqual((80, 0, 0, 0, 0, 0, 0),
                                 tuple(map(int, rows[(row[0], row[index])])))


if __name__ == "__main__":
    unittest.main()
