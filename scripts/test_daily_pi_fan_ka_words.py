"""Words of 2026-11-03: X批, 好几X / 那几X / 那一X / 就一X, X反了, cards
and vouchers, crab words; the supplement manifest's rows at 0.00 weighted
anew; 呐喊 below 那好. The user: "输入naha，首选是“呐喊”，其次是“那好”，我觉得反了，
更常见应该是“那好”。另外，那你帮我添加：蟹卡、谢卡、反了、那一批、那几批、好几批、就一批、……；
然后，把那一批0.00（包括斜挎）的权重重新定权。" Weighted as test_daily_jiu_ma_suo_words
(occurrences where the word is no part of a longer dictionary word, nor
before one that its last character begins, nor after one that its first
character ends); a word stays under every more frequent word of its key."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from test_daily_whitespace_phrases import read_rows
from test_daily_cuo_xiu_sha_shui_phrases import block

HEADERS = {'common': "# Everyday words, 2026-11-03, the more frequent ones: 蟹卡, 谢卡, 反了, 那一批, 那几批, 好几批 and 就一批 (the user's examples; 反了 under the more frequent 翻了 and 犯了, 谢卡 low under 蟹卡, where the shared LM still puts it first without a context), X批 with a demonstrative or a number (那批, 两批, 三批, 第二批, 又一批, 同一批, 最后一批, 一批批), 好几X, 那几X, 那一X and 就一X with a measure word (好几遍, 好几家, 那几天, 那几年, 那一段, 那一套, 就一个, 就一句), cards and vouchers given as presents (购物卡, 礼品卡) and crab words (蟹壳). Weighted as the blocks of 2026-11-01 (occurrences where the word is no part of a longer dictionary word, nor before one that its last character begins, nor after one that its first character ends); a word stays under every more frequent word of its key, an import's weight included; a requested word at least 400 where no more frequent word holds it lower.", 'less': '# Everyday words, 2026-11-03, the less frequent ones (搞反了, 弄反了, 说反, 写反, 用反, 上一批, 好几回, 那几张, 那一眼, 就一口, 卡券, 蟹券, 感谢卡, 蟹钳, 毛蟹), by the same weights.'}
SIZES = {'common': 46, 'less': 55}
REQUESTED = ['蟹卡', '谢卡', '反了', '那一批', '那几批', '好几批', '就一批']
HEADER_FORCED = "# Weighted anew on 2026-11-03: the rows this manifest held at 0.00 (weight 1) for imports and early batches (斜挎, 夏末, 金丝, 净赚, 发胶, 心窝, 剧透, 新聘, 二挡, 踢伤, 棉绒, 清癯, 已付, 荫庇), import-weight words of the batch's kinds (一大批, 礼券, 河蟹, 青蟹, 梭子蟹, 海蟹), import-weight words that held one of them under them (拷贝 over 靠背, 高调 over 高吊, 隐喻 over 银鱼, 姨父 over 已付), weighted as the blocks above (隐喻 at 1000: at the rule's 601 it fell under 阴雨, at 1 it had been first); 蟹粉, which only the traditional dictionary had, at its weight there; and 呐喊 (1000) at 359, one under 那好, which comes first on naha where both are still being typed (the user's request). The rows at 0.00 of a function character before a word (过的, 也在) stay low."
FORCED = [('yidapi', '一大批', '一大批', 600), ('liquan', '礼券', '禮券', 400), ('xiefen', '蟹粉', '蟹粉', 363), ('xiebang', '蟹棒', '蟹棒', 80), ('hexie', '河蟹', '河蟹', 600), ('haixie', '海蟹', '海蟹', 200), ('qingxie', '青蟹', '青蟹', 400), ('suozixie', '梭子蟹', '梭子蟹', 400), ('yifu', '已付', '已付', 400), ('yinyu', '银鱼', '銀魚', 278), ('qingqu', '清癯', '清癯', 79), ('xiamo', '夏末', '夏末', 600), ('jutou', '剧透', '劇透', 289), ('erdang', '二挡', '二擋', 200), ('jingshi', '晶石', '晶石', 139), ('jingzhuan', '净赚', '淨賺', 400), ('fajiao', '发胶', '髮膠', 400), ('tishang', '踢伤', '踢傷', 200), ('xinpin', '新聘', '新聘', 279), ('gaodiao', '高吊', '高吊', 80), ('kaobei', '靠背', '靠背', 600), ('xiekua', '斜挎', '斜挎', 200), ('xinwo', '心窝', '心窩', 399), ('jinsi', '金丝', '金絲', 600), ('mianrong', '棉绒', '棉絨', 200), ('yinbi', '荫庇', '蔭庇', 200), ('yifu', '姨夫', '姨夫', 419), ('yinyu', '音域', '音域', 600), ('yinyu', '淫欲', '淫慾', 279), ('yinyu', '隐喻', '隱喻', 1000), ('jingshi', '经世', '經世', 138), ('gaodiao', '高调', '高調', 600), ('kaobei', '拷贝', '拷貝', 601), ('liquan', '力劝', '力勸', 201), ('liquan', '利权', '利權', 200), ('xiebang', '鞋帮', '鞋幫', 400), ('xiejiao', '斜角', '斜角', 301), ('jiefan', '劫犯', '劫犯', 80), ('yifu', '姨父', '姨父', 401), ('yinbi', '银币', '銀幣', 600), ('yinbi', '荫蔽', '蔭蔽', 400), ('nahan', '呐喊', '吶喊', 359)]
ROWS = tuple(row[:4] for header in HEADERS.values() for row in block(header))


class DailyPiFanKaWordsTests(unittest.TestCase):
    def test_blocks(self):
        for group, header in HEADERS.items():
            rows = block(header)
            self.assertEqual(SIZES[group], len(rows), group)
            self.assertEqual({"exact_rank_no_contains"}, {row[4] for row in rows}, group)
        self.assertEqual(len(ROWS), len({(row[0], row[1]) for row in ROWS}))
        texts = {row[1] for row in ROWS}
        for word in REQUESTED:
            self.assertIn(word, texts, word)

    def test_kinds(self):
        for pinyin, sc, tc, _weight in ROWS + tuple(row[:4] for row in FORCED):
            self.assertIn(len(sc), (2, 3, 4), sc)
            self.assertEqual(len(sc), len(tc), sc)
            self.assertNotIn("'", pinyin)
        # 那 and 哪 read na, 了 le, 几 ji.
        keys = {(row[0], row[1]) for row in ROWS}
        for pinyin, word in (("nayipi", "那一批"), ("najipi", "那几批"), ("haojipi", "好几批"),
                             ("jiuyipi", "就一批"), ("fanle", "反了"), ("xieka", "蟹卡"), ("xieka", "谢卡")):
            self.assertIn((pinyin, word), keys)

    def test_naha(self):
        # 那好 (nahao 360) above 呐喊 (nahan) where both are being typed (naha).
        forced = {(row[0], row[1]): row[3] for row in FORCED}
        self.assertEqual(359, forced[("nahan", "呐喊")])
        by_key = {}
        for (pinyin, text), fields in read_rows("dict_clean_sc.txt").items():
            by_key.setdefault(pinyin, {})[text] = int(fields[0])
        self.assertGreater(by_key["nahao"]["那好"], by_key["nahan"]["呐喊"])

    def test_order(self):
        by_key = {}
        for (pinyin, text), fields in read_rows("dict_clean_sc.txt").items():
            by_key.setdefault(pinyin, {})[text] = int(fields[0])
        for pinyin, word, _tc, weight in ROWS + tuple(FORCED):
            self.assertEqual(weight, by_key[pinyin][word], word)
            others = [text for text, value in by_key[pinyin].items() if text != word and value == weight]
            # Under a word at 1 (an import's weight) the batch's words go to 0,
            # where they cannot be ordered (只招 and 只找 under 支招).
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
