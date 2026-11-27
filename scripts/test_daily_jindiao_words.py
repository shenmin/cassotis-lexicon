"""Words of 2026-11-27: the user's words and their kinds: a verb before 掉, 拆 with an adverb
before it or a complement after it, a numeral before 倍, a pronoun before a verb of one character, a place or a
vessel before 里, a verb before 的, 得, 到, 个, 好 and 新, 请 and 该 before a verb, 个 before a word of contempt, 不, 别
and 没 before a verb, and a verb before the particles 啊, 嘛 and 吗. The user: "日常库（其中有一个应该加入专有名词层）帮我再添加：
禁掉、会话中、不拆、重拆（chongchai）、拆啊、还拆（haichai）、别拆、千倍、万倍、……、乘彼白鹿（专有名称层）、让出来、该从、该如何、该往、该怎么、该选、
我无、……"; 乘彼白鹿 is a word of the proper-noun layer (manifests/vertical/proper_nouns.tsv). Words of the families'
keys at an import weight are weighted anew. Weighted as test_daily_wohen_words (occurrences where the word is no part
of a longer dictionary word, nor before one that its last character begins, nor after one that its first character
ends); a word stays under every more frequent word of its key."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from test_daily_whitespace_phrases import read_rows
from test_daily_cuo_xiu_sha_shui_phrases import block

HEADERS = {'common': "# Everyday words, 2026-11-27, the more frequent ones: the user's 禁掉, 会话中, 不拆, 重拆, 拆啊, 还拆, 别拆, 千倍, 万倍, 你写到, 我写到, 他写到, 她写到, 你制订, 我制订, 他制订, 她制订, 你制定, 你指定, 我指定, 我制定, 他指定, 他制定, 她制定, 她指定, 我到时候, 我到, 可以把, 坑里, 洞里, 穴里, 屄里, 房里, 抓得, 抓的, 拆吗, 拆嘛, 拆的, 拆得, 不交, 交嘛, 交啊, 你叫, 她叫, 他叫, 你教, 你交, 你脚, 我教, 我交, 我脚, 他脚, 她脚, 他交, 他教, 她交, 她教, 请对, 请就, 请上, 请下, 请发, 请送, 请收, 请查, 请听, 请闻, 请走, 请跳, 请调, 请睡, 请躺, 请打, 请答, 请按, 请开, 请关, 请烧, 修到, 搞一版, 弄一版, 做一版, 发一版, 提一版, 没算, 算吗, 算嘛, 算的, 算得, 你算, 我算, 她算, 他算, 算到, 设备数, 写个, 拉个, 走个, 去个, 听个, 发个, 送个, 收个, 查个, 个屁, 关个, 修个, 休到, 休个, 个鬼, 个蛋, 交个, 教个, 叫个, 连好, 开新, 开新卡, 我也没, 他也没, 你也没, 她也没, 该版本, 你点, 她点, 他点, 你操作, 我操作, 他操作, 她操作, 让出来, 该从, 该如何, 该往, 该怎么, 该选, 我无 (and, asked for afterwards, 拆光, 拆错, 帮拆, 她订, 按嘛 and 别闻, which neither corpus holds) and their kinds the lexicon lacked: a verb before 掉 (铲掉, 砸掉, 掐掉), 拆 with an adverb before it or a complement after it (被拆, 先拆, 拆包, 拆完), a numeral before 倍 (四倍, 数倍, 八倍), a pronoun before a verb of one character (他写, 你选, 她到, 您点), a place or a vessel before 里 (水里, 河里, 田里, 箱里), a verb before 的 and 得 (交的, 提的, 开得, 烧的), before 到 (吃到, 点到, 卖到, 玩到), before 个 (点个, 说个, 卖个, 拍个) and before 好 (建好, 戴好, 接好, 插好), a verb before 新 (上新, 建新, 发新, 推新), 请 before a verb (请点, 请给, 请出, 请写), 该 before a verb or a preposition (该点, 该由, 该被, 该在), 个 before a word of contempt (个球, 个毛, 个卵), 不 and 没 before a verb (不叫, 不调, 不填, 没教) and a verb before 吗 (点吗), weighted by the general text as the batches before; 八倍, 按到, 打到, 喝到, 玩到, 选到, 查的, 禁的, 烧的, 调的, 该对, 该叫, 补个, 画个, 听个, 洗个, 点好, 拍好, 签好, 池里, 地里, 省里, 水里, 桶里, 窝里, 箱里, 不交, 不叫, 不调, 没教, 点吗, 请按, 请打, 请点 and 发新 above a word of their key by everyday conversation; 别拉, 你收, 瓶里 and 库里 at 2, under 别啦, 你瘦, 评理 and 苦力, which the short choice would otherwise put them above; 调到 below 跳到 and 调吗 below 跳嘛 (they read diao as well); the user's 该从 above their 改从 of 2026-11-24, which the general text writes five times as seldom.", 'less': '# Everyday words, 2026-11-27, the less frequent ones (verbs before 掉, 到, 个, 好, 的, 得 and 新, 拆 with an adverb or a complement, pronouns before a verb, places and vessels before 里, 请, 该, 不, 别 and 没 before a verb, verbs before 啊, 嘛 and 吗 and numerals before 倍 that the general text seldom writes), by the same weights; words the general text seldom writes as words at 2 or below.'}
SIZES = {'common': 375, 'less': 208}
REQUESTED = ['禁掉', '会话中', '不拆', '重拆', '拆啊', '还拆', '别拆', '千倍', '万倍', '你写到', '我写到', '他写到', '她写到', '你制订', '我制订', '他制订', '她制订', '你制定', '你指定', '我指定', '我制定', '他指定', '他制定', '她制定', '她指定', '我到时候', '我到', '可以把', '坑里', '洞里', '穴里', '屄里', '房里', '抓得', '抓的', '拆吗', '拆嘛', '拆的', '拆得', '不交', '交嘛', '交啊', '你叫', '她叫', '他叫', '你教', '你交', '你脚', '我教', '我交', '我脚', '他脚', '她脚', '他交', '他教', '她交', '她教', '请对', '请就', '请上', '请下', '请发', '请送', '请收', '请查', '请听', '请闻', '请走', '请跳', '请调', '请睡', '请躺', '请打', '请答', '请按', '请开', '请关', '请烧', '修到', '搞一版', '弄一版', '做一版', '发一版', '提一版', '没算', '算吗', '算嘛', '算的', '算得', '你算', '我算', '她算', '他算', '算到', '设备数', '写个', '拉个', '走个', '去个', '听个', '发个', '送个', '收个', '查个', '个屁', '关个', '修个', '休到', '休个', '个鬼', '个蛋', '交个', '教个', '叫个', '连好', '开新', '开新卡', '我也没', '他也没', '你也没', '她也没', '该版本', '你点', '她点', '他点', '你操作', '我操作', '他操作', '她操作', '让出来', '该从', '该如何', '该往', '该怎么', '该选', '我无', '拆光', '拆错', '帮拆', '她订', '按嘛', '别闻']
HEADER_FORCED = "# Weighted anew on 2026-11-27: the words of the batch's keys at an import weight by the general text (暗格, 杯里, 背离, 尝到, 肠道, 持刀, 创利, 大盗, 代号, 地力, 毒力, 独力, 公厘, 巩俐, 管的, 官吏, 观礼, 合力, 河狸, 滑倒, 滑到, 花格, 尖刀, 尖厉, 减薪, 净利, 警力, 静立, 麦道, 目力, 平利, 轻缓, 清浅, 轻浅, 情伤, 青史, 青松, 青蒜, 清甜, 轻吻, 上心, 时隔, 跳到, 晚辈, 晚祷, 往里, 文蛤, 邪心, 贻贝, 组阁); 臂力, 布丁, 典礼, 该罚, 嗝屁, 公历, 公理, 邻里, 情诗, 撞到 and 清茶 above a word of their key by everyday conversation (清茶 above 清查); 背离 and 代号 just above 贝利 and 带好, as their keys showed them without a context before; 轻佻 above 轻挑 by more (the general text writes it eight times as often); 浅焙 below 谦卑 and the user's 千倍, which the general text writes 126 and 15 times as often."
FORCED = [('qianbei', '浅焙', '淺焙', 150), ('qingtiao', '轻佻', '輕佻', 600), ('ange', '暗格', '暗格', 200), ('beili', '杯里', '杯裡', 200), ('beili', '背离', '背離', 624), ('bili', '臂力', '臂力', 598), ('buding', '布丁', '布丁', 199), ('changdao', '尝到', '嚐到', 599), ('changdao', '肠道', '腸道', 600), ('chidao', '持刀', '持刀', 600), ('chuangli', '创利', '創利', 200), ('dadao', '大盗', '大盜', 279), ('daihao', '代号', '代號', 701), ('dianli', '典礼', '典禮', 600), ('dili', '地力', '地力', 353), ('duli', '毒力', '毒力', 400), ('duli', '独力', '獨力', 399), ('gaifa', '该罚', '該罰', 200), ('gepi', '嗝屁', '嗝屁', 201), ('gongli', '公历', '公曆', 147), ('gongli', '公厘', '公釐', 144), ('gongli', '公理', '公理', 148), ('gongli', '巩俐', '鞏俐', 146), ('guande', '管的', '管的', 999), ('guanli', '官吏', '官吏', 600), ('guanli', '观礼', '觀禮', 400), ('heli', '合力', '合力', 600), ('heli', '河狸', '河狸', 399), ('huadao', '滑倒', '滑倒', 600), ('huadao', '滑到', '滑到', 599), ('huage', '花格', '花格', 136), ('jiandao', '尖刀', '尖刀', 598), ('jianli', '尖厉', '尖厲', 87), ('jianxin', '减薪', '減薪', 400), ('jingli', '净利', '淨利', 512), ('jingli', '警力', '警力', 513), ('jingli', '静立', '靜立', 400), ('linli', '邻里', '鄰里', 600), ('maidao', '麦道', '麥道', 400), ('muli', '目力', '目力', 200), ('pingli', '平利', '平利', 200), ('qingcha', '清茶', '清茶', 600), ('qinghuan', '轻缓', '輕緩', 400), ('qingqian', '清浅', '清淺', 600), ('qingqian', '轻浅', '輕淺', 200), ('qingshang', '情伤', '情傷', 400), ('qingshi', '情诗', '情詩', 124), ('qingshi', '青史', '青史', 123), ('qingsong', '青松', '青松', 600), ('qingsuan', '青蒜', '青蒜', 400), ('qingtian', '清甜', '清甜', 463), ('qingwen', '轻吻', '輕吻', 200), ('shangxin', '上心', '上心', 468), ('shige', '时隔', '時隔', 119), ('tiaodao', '跳到', '跳到', 600), ('wanbei', '晚辈', '晚輩', 600), ('wandao', '晚祷', '晚禱', 200), ('wangli', '往里', '往裡', 974), ('wenge', '文蛤', '文蛤', 400), ('xiexin', '邪心', '邪心', 221), ('yibei', '贻贝', '貽貝', 231), ('zhuangdao', '撞到', '撞到', 695), ('zuge', '组阁', '組閣', 400)]
ROWS = tuple(row[:4] for header in HEADERS.values() for row in block(header))


class DailyJindiaoWordsTests(unittest.TestCase):
    def test_blocks(self):
        for group, header in HEADERS.items():
            rows = block(header)
            self.assertEqual(SIZES[group], len(rows), group)
            self.assertEqual({"exact_rank_no_contains"}, {row[4] for row in rows}, group)
        self.assertEqual(len(ROWS), len({(row[0], row[1]) for row in ROWS}))
        texts = {row[1] for row in ROWS} | {row[1] for row in FORCED}
        for word in REQUESTED:
            self.assertIn(word, texts, word)
        forced = block(HEADER_FORCED)
        self.assertEqual({"exact_rank"}, {row[4] for row in forced})
        self.assertEqual({row[:4] for row in FORCED}, {tuple(row[:4]) for row in forced})

    def test_kinds(self):
        for pinyin, sc, tc, _weight in ROWS + tuple(row[:4] for row in FORCED):
            self.assertIn(len(sc), (2, 3, 4), sc)
            self.assertEqual(len(sc), len(tc), sc)
            self.assertNotIn("'", pinyin)
        keys = {(row[0], row[1]) for row in ROWS + tuple(FORCED)}
        # Readings the user gave and readings by the meaning: 重 chong, 还 hai, 调 tiao, 没 mei, 系 ji of tying.
        for pinyin, word in (("chongchai", "重拆"), ("haichai", "还拆"), ("qingtiao", "请调"), ("meisuan", "没算"),
                             ("woyemei", "我也没"), ("jihao", "系好")):
            self.assertIn((pinyin, word), keys)

    def test_proper_noun(self):
        listed = [line.split("\t") for line in (ROOT / "manifests/vertical/proper_nouns.tsv").read_text(
            encoding="utf-8").splitlines() if line and not line.startswith("#")]
        self.assertIn(["乘彼白鹿", "乘彼白鹿", "0.78", "chengbibailu"], listed)
        for variant in ("sc", "tc"):
            rows = read_rows(f"dict_clean_{variant}.txt")
            self.assertEqual("579", rows[("chengbibailu", "乘彼白鹿")][0])

    def test_order(self):
        by_key = {}
        for (pinyin, text), fields in read_rows("dict_clean_sc.txt").items():
            by_key.setdefault(pinyin, {})[text] = int(fields[0])
        for pinyin, word, _tc, weight in ROWS + tuple(FORCED):
            self.assertEqual(weight, by_key[pinyin][word], word)
            others = [text for text, value in by_key[pinyin].items() if text != word and value == weight]
            if weight > 0:
                self.assertFalse(others, (pinyin, word))

    def test_explicit_ranks_survive_rebuild(self):
        entries, _ = builder._parse_curated_daily_phrase_entries(
            (ROOT / "manifests/curated_daily_supplement_phrases.tsv").read_bytes(), 2)
        wanted = {(row[0], row[1]) for row in ROWS}
        selected = [entry for entry in entries if (entry[3], entry[0]) in wanted]
        regular, exact = builder._partition_curated_daily_post_rank_exact_entries(selected)
        self.assertFalse(regular)
        self.assertEqual(len(ROWS), len(exact))
        maps = ({}, {})
        builder._inject_curated_daily_post_rank_exact_entries(*maps, exact)
        for index, mapping in enumerate(maps, 1):
            self.assertEqual({(row[0], row[index]): row[3] for row in ROWS}, mapping)

    def test_generated_entries_and_prior(self):
        for index, variant in enumerate(("sc", "tc"), 1):
            rows = read_rows(f"dict_clean_{variant}.txt")
            prior = read_rows(f"dict_completion_prior_{variant}.txt")
            for row in ROWS:
                self.assertEqual([str(row[3]), "no_contains"], rows[(row[0], row[index])])
                self.assertEqual(["80", "0", "0", "0", "0", "0", "0"], prior[(row[0], row[index])])
            for row in FORCED:
                self.assertEqual(str(row[3]), rows[(row[0], row[index])][0])


if __name__ == "__main__":
    unittest.main()
