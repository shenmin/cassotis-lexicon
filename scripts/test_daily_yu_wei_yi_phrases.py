"""Comparisons and limits of 2026-10-19 (the user's 早于、晚于、迟于、先于、后于、后与、
未满、未到、未达、已满、已达, and more of their kinds, only words in use): X于 of
time and degree with 不X于 and X于预期, and 未 / 已 + 满 / 到 / 达 / 超 ... with
what is reached. Weights as in test_daily_cuo_xiu_sha_shui_phrases; a
requested word leads its key at one and a half times the occurrences (晚于
above 晚育), never above a word at the top weight (先于 under 陷于); a row
stays below a more frequent word of its key at weight 100 or more (未逾 under
未予, 已至 under 一支; 先于 under 限于, five times as frequent). 后与 is no
word of its own (随后与, 之后与) and stays below 后于; 已及 is not added (以及).
甚于 stays at 200: at the weight of its occurrences it took the syllables
shen yu of a name in the long benchmark sentences."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from test_daily_whitespace_phrases import read_rows
from test_daily_cuo_xiu_sha_shui_phrases import block, keys

HEADER_COMMON = "# Comparisons and limits, 2026-10-19, the more frequent ones:"
HEADER_LESS = "# Comparisons and limits, 2026-10-19, the less frequent ones"
REQUESTED = "早于 晚于 迟于 先于 后于 后与 未满 未到 未达 已满 已达".split()
LEADS = {"后于": "鲎鱼", "晚于": "晚育", "迟于": "驰誉", "未满": "帷幔", "已满": "役满"}
BELOW = {"早于": "遭遇", "先于": "限于", "未到": "味道", "未达": "伟大", "已达": "一大", "后与": "后于",
         # Below a more frequent word of the key that is not the first.
         "未逾": "未予", "已至": "一支", "已逾": "意欲", "轻于": "清淤", "慢于": "满语"}
ROWS = tuple(row[:4] for row in block(HEADER_COMMON) + block(HEADER_LESS))


class DailyYuWeiYiTests(unittest.TestCase):
    def test_blocks(self):
        common, less = block(HEADER_COMMON), block(HEADER_LESS)
        self.assertGreater(len(common), 40)
        self.assertGreater(len(less), 20)
        self.assertEqual({"exact_rank_no_contains"}, {row[4] for row in common + less})
        self.assertTrue(all(row[3] >= 400 for row in common))
        self.assertTrue(all(row[3] < 400 for row in less))
        self.assertEqual(len(ROWS), len({(row[0], row[1]) for row in ROWS}))
        self.assertTrue(all("於" in row[2] for row in ROWS if row[1].endswith("于")))
        texts = {row[1] for row in ROWS}
        self.assertNotIn("已及", texts)
        self.assertIn(("shenyu", "甚于", "甚於", 200), [row[:4] for row in less])
        for word in REQUESTED:
            self.assertIn(word, texts, word)

    def test_requested_order(self):
        rows = keys("sc")
        for word, first in list(LEADS.items()) + list(BELOW.items()):
            pinyin = next(row[0] for row in ROWS if row[1] == word)
            if word in LEADS:
                self.assertGreater(rows[pinyin][word], rows[pinyin][first], word)
            else:
                self.assertLess(rows[pinyin][word], rows[pinyin][first], word)

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
