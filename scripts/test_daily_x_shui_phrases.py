"""Verb or preposition + 谁 of 2026-10-20 (the user's 有谁、听谁、看谁、跟谁、没谁、就谁、
成谁、要谁、推谁、选谁、爱谁、爱谁谁、恨谁、打谁、吃谁、舔谁、拍谁、派谁、抽谁、丢谁, and
more of the kind; "谁的两个读音（shui、shei）都加入"): each word with 谁 read
shui and shei, in a more and a less frequent block, weighted as in
test_daily_bu_zai_qi_phrases (occurrences where the word is no part of a
longer dictionary word, the first word of a key led only with three times
its occurrences, below every more frequent word of the key). Words of the
batch of 2026-10-18 (选谁, 爱谁, 打谁, 给谁 ...) had shui only and get shei.
Read shui, most stay below the X水 of their key (打谁 under 打水)."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from test_daily_whitespace_phrases import read_rows
from test_daily_cuo_xiu_sha_shui_phrases import block, keys

HEADER_COMMON = "# Verb or preposition + 谁, 2026-10-20, the more frequent ones:"
HEADER_LESS = "# Verb or preposition + 谁, 2026-10-20, the less frequent ones"
REQUESTED = ("有谁 听谁 看谁 跟谁 没谁 就谁 成谁 要谁 推谁 选谁 爱谁 爱谁谁 恨谁 打谁 吃谁 舔谁 拍谁 "
             "派谁 抽谁 丢谁").split()
ROWS = tuple(row[:4] for row in block(HEADER_COMMON) + block(HEADER_LESS))


def shei(pinyin):
    return pinyin.replace("shui", "shei")


class DailyXShuiTests(unittest.TestCase):
    def test_blocks(self):
        common, less = block(HEADER_COMMON), block(HEADER_LESS)
        self.assertGreater(len(common), 40)
        self.assertEqual({"exact_rank_no_contains"}, {row[4] for row in common + less})
        self.assertEqual(len(ROWS), len({(row[0], row[1]) for row in ROWS}))
        self.assertTrue(all("谁" in row[1] and "誰" in row[2] for row in ROWS))
        self.assertNotIn("跟着谁", {row[1] for row in ROWS})

    def test_both_readings(self):
        rows = keys("sc")
        for word in REQUESTED:
            readings = {pinyin for pinyin, words in rows.items() if word in words}
            self.assertTrue(any("shei" in p for p in readings), word)
            self.assertTrue(any("shui" in p for p in readings), word)
        # A word of 2026-10-18 keeps its shui row and gets shei.
        for word, pinyin in (("选谁", "xuanshui"), ("给谁", "geishui"), ("打谁", "dashui")):
            self.assertIn(word, rows[pinyin], word)
            self.assertIn(word, rows[shei(pinyin)], word)

    def test_below_water(self):
        rows = keys("sc")
        self.assertLess(rows["dashui"]["打谁"], rows["dashui"]["打水"])

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
