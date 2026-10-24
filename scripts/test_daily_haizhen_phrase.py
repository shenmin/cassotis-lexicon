"""The everyday word of 2026-10-24 that the user asked for: 还真, read hai zhen
(还真是, 还真不错), on a key that held no word. Weighted as
test_daily_suo_bijiao_phrases (occurrences where the word is no part of a
longer dictionary word, nor before one that its last character begins, nor
after one that its first character ends): 600."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from test_daily_whitespace_phrases import read_rows
from test_daily_cuo_xiu_sha_shui_phrases import block, keys

HEADER = "# Everyday word, 2026-10-24 (还真):"
ROWS = tuple(row[:4] for row in block(HEADER))


class DailyHaizhenTests(unittest.TestCase):
    def test_block(self):
        self.assertEqual([("haizhen", "还真", "還真", 600, "exact_rank_no_contains")], block(HEADER))

    def test_first_on_its_key(self):
        for variant, text in (("sc", "还真"), ("tc", "還真")):
            rows = keys(variant)["haizhen"]
            self.assertEqual(text, max(rows, key=rows.get), variant)
            self.assertEqual(1, list(rows.values()).count(600), variant)

    def test_explicit_rank_survives_rebuild(self):
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

    def test_generated_entry_and_prior(self):
        for index, variant in enumerate(("sc", "tc"), 1):
            rows = read_rows(f"dict_clean_{variant}.txt")
            prior = read_rows(f"dict_completion_prior_{variant}.txt")
            for row in ROWS:
                self.assertEqual([str(row[3]), "no_contains"], rows[(row[0], row[index])])
                self.assertEqual(["80", "0", "0", "0", "0", "0", "0"], prior[(row[0], row[index])])


if __name__ == "__main__":
    unittest.main()
