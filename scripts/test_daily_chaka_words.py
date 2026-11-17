"""Words of 2026-11-17: the user's 插卡, 读卡, 销卡, 建卡 and 注卡, the words of a card's handling and the cards
themselves the lexicon lacked (办卡, 绑卡, 社保卡, 答题卡), and words of two syllables whose last one ends in a, which
the page showed with a word completed on that syllable or with a homophone (微辣, 喜茶, 改价, 婚假, 植发, 洗牙, 赏花,
督查, 谢啦). The user: "帮我再加一批：插卡、读卡、销卡、建卡、注卡、……；主要是类似这种 ka（或者la、ba等结尾的词，如果没有在词库，
就会看到 kan, lan, bang 等发音的字作为候选，所以类似这种情形的词，尽可能预先在词库里". Words of the families at an import
weight are weighted anew. Weighted as test_daily_donghang_words (occurrences where
the word is no part of a longer dictionary word, nor before one that its last character begins, nor after one that its
first character ends); a word stays under every more frequent word of its key."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from test_daily_whitespace_phrases import read_rows
from test_daily_cuo_xiu_sha_shui_phrases import block

HEADERS = {'common': "# Everyday words, 2026-11-17, the more frequent ones: the user's 插卡, 读卡, 销卡, 建卡 and 注卡, the words of a card's handling and the cards themselves the lexicon lacked (办卡, 换卡, 退卡, 年卡, 医保卡, 社保卡, 答题卡, 加油卡), and words of two syllables whose last one ends in a, which the page showed with a word completed on that syllable or with a homophone (微辣, 喜茶, 金价, 植发, 赏花, 督查, 走下, 黑化, 好嘛), and the user's 三家, 四家, 五家, 七家, 八家, 九家, 十家 and 二家 (a numeral before a count of households or firms) with 别家 and 某家, weighted by the general text as the batches before; 二家 and 十家 above words of an import weight that hold the last places of their keys, 别家 and 某家 above a word of their key that everyday conversation does not write; 酸化, 沙化, 消纳, 河沙, 插拔, 瘦马 and 诸法 under a word of their key that everyday conversation writes far more often.", 'less': '# Everyday words, 2026-11-17, the less frequent ones (拔卡, 绑卡, 地铁卡, 停车卡, 改价, 整家, 收假, 谢啦, 来嘛, 好怕, 剥虾, 亮瞎, 气炸), by the same weights; 验卡, 太卡, 特辣, 没啦, 欠打, 干哈 and other words the general text seldom writes as words, at 2.'}
SIZES = {'common': 667, 'less': 365}
REQUESTED = ['插卡', '读卡', '销卡', '建卡', '注卡', '三家', '四家', '五家', '七家', '八家', '九家', '十家', '二家']
HEADER_FORCED = '# Weighted anew on 2026-11-17: 白金卡 at an import weight, 局麻, 竹马, 煎炸, 买价, 婚假 and 划花, rows of the traditional dictionary that the simplified one lacked, at the weights the simplified key gives them.'
FORCED = [('baijinka', '白金卡', '白金卡', 400), ('juma', '局麻', '局麻', 400), ('zhuma', '竹马', '竹馬', 100), ('jianzha', '煎炸', '煎炸', 600), ('maijia', '买价', '買價', 101), ('hunjia', '婚假', '婚假', 422), ('huahua', '划花', '劃花', 9)]
ROWS = tuple(row[:4] for header in HEADERS.values() for row in block(header))


class DailyChakaWordsTests(unittest.TestCase):
    def test_blocks(self):
        for group, header in HEADERS.items():
            rows = block(header)
            self.assertEqual(SIZES[group], len(rows), group)
            self.assertEqual({"exact_rank_no_contains"}, {row[4] for row in rows}, group)
        self.assertEqual(len(ROWS), len({(row[0], row[1]) for row in ROWS}))
        texts = {row[1] for row in ROWS} | {row[1] for row in FORCED}
        for word in REQUESTED:
            self.assertIn(word, texts, word)

    def test_kinds(self):
        for pinyin, sc, tc, _weight in ROWS + tuple(row[:4] for row in FORCED):
            self.assertIn(len(sc), (2, 3, 4, 5, 6), sc)
            self.assertEqual(len(sc), len(tc), sc)
            self.assertNotIn("'", pinyin)
        keys = {(row[0], row[1]) for row in ROWS + tuple(FORCED)}
        # Readings by the meaning: 牛扒 (pa), 急刹 (sha), 名刹 (cha), 当差 (chai), 厦大 (xia), 长芽 (zhang).
        for pinyin, word in (("niupa", "牛扒"), ("jisha", "急刹"), ("mingcha", "名刹"), ("dangchai", "当差"),
                             ("xiada", "厦大"), ("zhangya", "长芽")):
            self.assertIn((pinyin, word), keys)

    def test_order_on_shared_keys(self):
        # The everyday words of a key stay above the batch's: none listed.
        for variant, index in (("sc", 0), ("tc", 1)):
            rows = read_rows(f"dict_clean_{variant}.txt")
            for pinyin, pair in ():
                (high, low) = (word[index] for word in pair)
                self.assertGreater(int(rows[(pinyin, high)][0]), int(rows[(pinyin, low)][0]), (variant, pinyin))

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
