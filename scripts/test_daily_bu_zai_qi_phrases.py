"""Everyday phrases of 2026-10-20 (the user's 涨上天、涨回、混用、不搞、不弄、不玩、不晚、
不得（dei）、不坏、不美、美哉、岂不、不归、不贵、不跪, and more of their kinds, "根据实际
分别加入高频和低频组，并赋予适当的权重"): prices going up and back (涨回, 跌回, 涨上天),
mixed use (混用, 混装), 不X of everyday speech, 不得 read dei, X哉 and 岂X.
The two blocks are frequency groups: the more frequent ones (occurrences per
100M characters of the general text, where the word is no part of a longer
dictionary word, plus five times per 1M characters of the chat sentences, at
least 10) and the less frequent ones. A word leads its key with three times
(a requested word: one and a half times) the occurrences of the key's first
word, and stays below every more frequent word of the key at weight 100 or
more and above every less frequent one, so a frequent word can stand low
(不搞 under 不高, 不香 under 不想). Existing words of the same kinds at the
import weight 10 are weighted by the same rules (不早, 不迟, 不配, 不愁, 不丑,
混住); 不借 and 不改 stay at 0 on purpose (the block of ambiguous productive
phrases)."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from test_daily_whitespace_phrases import read_rows
from test_daily_cuo_xiu_sha_shui_phrases import block, keys

HEADER_COMMON = "# Everyday phrases, 2026-10-20, the more frequent ones:"
HEADER_LESS = "# Everyday phrases, 2026-10-20, the less frequent ones"
HEADER_FORCED = "# Existing words of the same kinds at an import weight"
REQUESTED = "涨上天 涨回 混用 不搞 不弄 不晚 不得 不坏 不美 美哉 岂不 不归 不贵 不跪".split()
LEADS = {"不贵": "不轨", "不归": "不轨", "混用": "昏庸", "涨回": "张辉", "不读": "不独", "岂能": "奇能"}
BELOW = {"不晚": "不完", "不搞": "不高", "不跪": "不轨", "岂不": "起步", "不香": "不想",
         # above a less frequent word that is not the first
         "不迟": "不吃"}
ABOVE = {"不迟": "不啻", "不歇": "不协"}
FORCED = {("buzao", "不早"): 600, ("buchi", "不迟"): 604, ("bupei", "不配"): 601, ("buchou", "不愁"): 600,
          ("buchou", "不丑"): 400, ("hunzhu", "混住"): 200, ("zhaoshui", "找谁"): 600,
          # the traditional 不軌 was 987, above the requested 不歸 and 不貴
          ("bugui", "不轨"): 951}
ROWS = tuple(row[:4] for row in block(HEADER_COMMON) + block(HEADER_LESS))


class DailyBuZaiQiTests(unittest.TestCase):
    def test_blocks(self):
        common, less = block(HEADER_COMMON), block(HEADER_LESS)
        self.assertGreater(len(common), 70)
        self.assertGreater(len(less), 15)
        self.assertEqual({"exact_rank_no_contains"}, {row[4] for row in common + less})
        self.assertEqual(len(ROWS), len({(row[0], row[1]) for row in ROWS}))
        texts = {row[1] for row in ROWS}
        for word in REQUESTED:
            self.assertIn(word, texts, word)
        # Only words in use: no phrase with a particle or a measure word.
        for word in ("不玩了", "涨个不停", "混着用", "岂可以", "惜哉", "不输"):
            self.assertNotIn(word, texts, word)
        self.assertIn(("budei", "不得", "不得", 400), ROWS)
        self.assertTrue(all("著" not in row[2] and "爲" not in row[2] for row in ROWS))

    def test_requested_order(self):
        rows = keys("sc")
        for word, other in LEADS.items():
            pinyin = next(row[0] for row in ROWS if row[1] == word)
            self.assertGreater(rows[pinyin][word], rows[pinyin][other], word)
        for word, other in BELOW.items():
            pinyin = next(row[0] for row in ROWS if row[1] == word) if word != "不迟" else "buchi"
            self.assertLess(rows[pinyin][word], rows[pinyin][other], word)
        for word, other in ABOVE.items():
            pinyin = "buchi" if word == "不迟" else next(row[0] for row in ROWS if row[1] == word)
            self.assertGreater(rows[pinyin][word], rows[pinyin][other], word)
        # 不得 keeps its reading de.
        self.assertIn("不得", rows["bude"])

    def test_reweighted_words(self):
        forced = block(HEADER_FORCED)
        self.assertEqual({"exact_rank"}, {row[4] for row in forced})
        self.assertEqual(FORCED, {(row[0], row[1]): row[3] for row in forced})
        text = (ROOT / "manifests/curated_daily_supplement_phrases.tsv").read_text(encoding="utf-8")
        # The import's row at 0.01 is gone (找谁 keeps its row read shei).
        for (_pinyin, word), _weight in FORCED.items():
            self.assertFalse([line for line in text.splitlines()
                              if line.split("\t")[0] == word and line.split("\t")[2:3] == ["0.01"]], word)
        rows = keys("sc")
        for (pinyin, word), weight in FORCED.items():
            self.assertEqual(weight, rows[pinyin][word], word)
        self.assertEqual(951, keys("tc")["bugui"]["不軌"])
        self.assertEqual(0, rows["bujie"]["不借"])
        self.assertEqual(0, rows["bugai"]["不改"])

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
