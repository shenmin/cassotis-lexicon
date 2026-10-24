"""Everyday words of 2026-10-24 (the user's 巡检, 旧版 and 老版, and more of their
kinds): versions and models, old and new things of work, inspections. Weighted
as test_daily_suo_bijiao_phrases; existing words of the same kinds at an import
weight (年检, 老电脑, 老客户, 新功能) are weighted by the same rules.
(Copied from the batch before:) common words the lexicon
lacked (答题, 配图, 插画, 绘本, 埋点, 高亮, 逆变器, 矫正, 顺丰, 会议纪要 ...), found by
a user's typing statistics and reviewed by hand (genuine words only, well-known
names in); the statistics gave the words and
their readings, never a weight. Weighted as test_daily_suo_bijiao_phrases
(occurrences where the word is no part of a longer dictionary word, nor
before one that its last character begins, nor after one that its first
character ends); a word leads its key only with three times the occurrences
of its first word (大类 above 打雷) and stays below every more frequent word
of the key (取值 under 屈指). Existing words of the batch's keys at an import
weight that the general text holds more often than the new word are weighted
by the same rules (人为, 校验, 寓言, 书评 ...); the traditional dictionary gets
將死."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from test_daily_whitespace_phrases import read_rows
from test_daily_cuo_xiu_sha_shui_phrases import block, keys

HEADER_COMMON = "# Everyday words, 2026-10-24 (versions, old and new things of work, inspections), the more frequent ones:"
HEADER_LESS = "# Everyday words, 2026-10-24 (versions, old and new things of work, inspections), the less frequent ones"
HEADER_FORCED = "# Existing words of the kinds of the batch of 2026-10-24 at an import weight"
REQUESTED = "旧版 老版".split()
# (pinyin, word, other): word above other on the key
ABOVE = []
BELOW = [("laoban", "老版", "老板")]
FORCED = {
    ("laodiannao", "老电脑"): 200,
    ("laokehu", "老客户"): 600,
    ("xingongneng", "新功能"): 600,
    ("nianjian", "年检"): 600,
}
# Reweighted words the traditional dictionary lacked: added with the contains flag.
TC_ADDED = {
    ("nianjian", "年檢"): 600,
}
ROWS = tuple(row[:4] for row in block(HEADER_COMMON) + block(HEADER_LESS))


class DailyJiubanLaobanTests(unittest.TestCase):
    def test_blocks(self):
        common, less = block(HEADER_COMMON), block(HEADER_LESS)
        self.assertEqual(16, len(common))
        self.assertEqual(23, len(less))
        self.assertEqual({"exact_rank_no_contains"}, {row[4] for row in common + less})
        self.assertEqual(len(ROWS), len({(row[0], row[1]) for row in ROWS}))
        texts = {row[1] for row in ROWS}
        for word in REQUESTED:
            self.assertIn(word, texts, word)
        self.assertIn(("jiuban", "旧版", "舊版"), {row[:3] for row in ROWS})
        # Taiwan's forms: 著 is 着 there (扛著), 爲 is no form of it.
        self.assertTrue(all("爲" not in row[2] for row in ROWS))

    def test_order(self):
        rows = keys("sc")
        for pinyin, word, other in ABOVE:
            self.assertGreater(rows[pinyin][word], rows[pinyin][other], word)
        for pinyin, word, other in BELOW:
            self.assertLess(rows[pinyin][word], rows[pinyin][other], word)
        # No weight of the batch ties with another word of its key.
        by_key = {}
        for (pinyin, text), fields in read_rows("dict_clean_sc.txt").items():
            by_key.setdefault(pinyin, {})[text] = int(fields[0])
        for pinyin, word, _tc, weight in ROWS + tuple((p, w, "", v) for (p, w), v in FORCED.items()):
            others = [text for text, value in by_key[pinyin].items() if text != word and value == weight]
            self.assertFalse(others, (pinyin, word))

    def test_reweighted_words(self):
        forced = block(HEADER_FORCED)
        self.assertEqual({"exact_rank"}, {row[4] for row in forced})
        self.assertEqual(FORCED, {(row[0], row[1]): row[3] for row in forced})
        text = (ROOT / "manifests/curated_daily_supplement_phrases.tsv").read_text(encoding="utf-8")
        for (_pinyin, word), _weight in FORCED.items():
            self.assertFalse([line for line in text.splitlines()
                              if line.split("\t")[0] == word and line.split("\t")[2:3] == ["0.01"]], word)
        clean = read_rows("dict_clean_sc.txt")
        for (pinyin, word), weight in FORCED.items():
            self.assertEqual(str(weight), clean[(pinyin, word)][0], word)
        tc_rows = read_rows("dict_clean_tc.txt")
        for key, weight in TC_ADDED.items():
            self.assertEqual([str(weight)], tc_rows[key], key)

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


if __name__ == "__main__":
    unittest.main()
