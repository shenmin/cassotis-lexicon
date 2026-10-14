"""Colloquial verb phrases with zai, a final particle, gai or a line count
keep explicit readings and moderate exact ranks."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from test_daily_whitespace_phrases import read_rows

# Readings are written as they are typed, without a syllable separator: an
# input of "wana" does not return an entry stored as "wan'a".
REQUESTED = (
    ("zaigao", "在搞", "在搞", 420),
    ("zaigao", "再搞", "再搞", 360),
    ("zainong", "在弄", "在弄", 400),
    ("zainong", "再弄", "再弄", 340),
    ("zaiwan", "在玩", "在玩", 460),
    ("zaiwan", "再玩", "再玩", 400),
    ("zailushang", "在路上", "在路上", 480),
    ("zaicheshang", "在车上", "在車上", 360),
    ("cibiao", "词表", "詞表", 450),
    ("rizhili", "日志里", "日誌裡", 300),
    ("tiaozhengguo", "调整过", "調整過", 320),
    ("pengdaoguo", "碰到过", "碰到過", 200),
    ("tuiba", "推吧", "推吧", 260),
    ("songba", "送吧", "送吧", 300),
    ("gaoba", "搞吧", "搞吧", 320),
    ("nongba", "弄吧", "弄吧", 300),
    ("siba", "死吧", "死吧", 240),
    ("daziqian", "打字前", "打字前", 200),
    ("huia", "会啊", "會啊", 420),
    ("laia", "来啊", "來啊", 460),
    ("qua", "去啊", "去啊", 420),
    ("zoua", "走啊", "走啊", 420),
    ("gaoa", "搞啊", "搞啊", 300),
    ("nonga", "弄啊", "弄啊", 300),
    ("wana", "玩啊", "玩啊", 360),
    ("sia", "死啊", "死啊", 300),
    ("yaoa", "要啊", "要啊", 400),
    ("wanhang", "万行", "萬行", 300),
    ("baihang", "百行", "百行", 240),
    ("qianhang", "千行", "千行", 280),
    ("jialemei", "加了没", "加了沒", 240),
    ("jialeme", "加了么", "加了麼", 220),
    ("jiaa", "加啊", "加啊", 300),
    ("gaian", "改按", "改按", 120),
    ("gainong", "改弄", "改弄", 160),
    ("gaizuo", "改做", "改做", 120),
    ("gaiwan", "改玩", "改玩", 160),
    ("gaigao", "改搞", "改搞", 160),
    ("nabuqi", "拿不齐", "拿不齊", 200),
    ("zhuande", "赚得", "賺得", 300),
    ("zhuandeduo", "赚得多", "賺得多", 320),
    ("zhuandeshao", "赚得少", "賺得少", 280),
)

# Phrases of the same patterns for which the engine offered no whole candidate
# or a rarer homophone first.
RELATED = (
    ("zaizhao", "在找", "在找", 420),
    ("zaizhao", "再找", "再找", 360),
    ("zaishuo", "在说", "在說", 100),
    ("zaicha", "在查", "在查", 340),
    ("zaicha", "再查", "再查", 320),
    ("zaiwan", "再晚", "再晚", 300),
    ("sheia", "谁啊", "誰啊", 460),
    ("nenga", "能啊", "能啊", 340),
    ("shuoa", "说啊", "說啊", 400),
    ("zuoa", "做啊", "做啊", 320),
    ("chia", "吃啊", "吃啊", 380),
    ("maia", "买啊", "買啊", 320),
    ("kuaia", "快啊", "快啊", 380),
    ("shanga", "上啊", "上啊", 340),
    ("chonga", "冲啊", "衝啊", 340),
    ("paoa", "跑啊", "跑啊", 320),
    ("denga", "等啊", "等啊", 320),
    ("yonga", "用啊", "用啊", 320),
    ("gaia", "改啊", "改啊", 300),
    ("faa", "发啊", "發啊", 300),
    ("tuia", "推啊", "推啊", 240),
    ("songa", "送啊", "送啊", 240),
    ("kana", "看啊", "看啊", 360),
    ("gaichi", "改吃", "改吃", 160),
    ("gaikan", "改看", "改看", 160),
    ("gaizou", "改走", "改走", 160),
    ("gaiqu", "改去", "改去", 160),
    ("gaimai", "改买", "改買", 140),
    ("meihang", "每行", "每行", 360),
    ("yiqianhang", "一千行", "一千行", 240),
    ("zhuandao", "赚到", "賺到", 300),
    ("zhuanbudao", "赚不到", "賺不到", 280),
    ("nabuqi", "拿不起", "拿不起", 300),
    ("cibiaoli", "词表里", "詞表裡", 240),
    ("peizhili", "配置里", "配置裡", 260),
    ("cipin", "词频", "詞頻", 300),
    ("dazihou", "打字后", "打字後", 200),
    ("dazishi", "打字时", "打字時", 200),
    ("zaiwangshang", "在网上", "在網上", 400),
)

ROWS = REQUESTED + RELATED

# pinyin, the commoner word (simplified, traditional), the added word
# (simplified, traditional) that stays below it.
COMMON_FIRST = (
    ("zaishuo", "再说", "再說", "在说", "在說"),
    ("tuiba", "退吧", "退吧", "推吧", "推吧"),
    ("siba", "四八", "四八", "死吧", "死吧"),
    ("gaizuo", "该做", "該做", "改做", "改做"),
    ("gaiwan", "改完", "改完", "改玩", "改玩"),
    ("gaigao", "改稿", "改稿", "改搞", "改搞"),
    ("zhuande", "赚的", "賺的", "赚得", "賺得"),
    ("zhuandao", "转到", "轉到", "赚到", "賺到"),
    ("cipin", "次品", "次品", "词频", "詞頻"),
)

# A line count is read hang, never xing.
WRONG_READINGS = (
    ("wanxing", "万行", "萬行"),
    ("baixing", "百行", "百行"),
    ("qianxing", "千行", "千行"),
    ("meixing", "每行", "每行"),
    ("yiqianxing", "一千行", "一千行"),
)


class DailyParticleTests(unittest.TestCase):
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

    def test_generated_entries_and_reading(self):
        for index, variant in enumerate(("sc", "tc"), 1):
            rows = read_rows(f"dict_clean_{variant}.txt")
            for row in ROWS:
                self.assertEqual([str(row[3]), "no_contains"], rows[(row[0], row[index])])
            for wrong in WRONG_READINGS:
                self.assertNotIn((wrong[0], wrong[index]), rows)

    def test_preserve_common_homophones(self):
        for variant, common_index, added_index in (("sc", 1, 3), ("tc", 2, 4)):
            rows = read_rows(f"dict_clean_{variant}.txt")
            for pair in COMMON_FIRST:
                self.assertGreater(int(rows[(pair[0], pair[common_index])][0]),
                                   int(rows[(pair[0], pair[added_index])][0]), pair)

    def test_no_fabricated_corpus_support(self):
        for index, variant in enumerate(("sc", "tc"), 1):
            rows = read_rows(f"dict_completion_prior_{variant}.txt")
            for row in ROWS:
                self.assertEqual((80, 0, 0, 0, 0, 0, 0),
                                 tuple(map(int, rows[(row[0], row[index])])))


if __name__ == "__main__":
    unittest.main()
