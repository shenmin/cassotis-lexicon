"""Preserve common exact ranks and reproducible SC/TC daily additions."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from validate_regression_samples import load_merged_dict

ROWS = (
    ("jieru", "\u63a5\u5165", "\u63a5\u5165", 800, False),
    ("tizi", "\u68af\u5b50", "\u68af\u5b50", 760, False),
    ("tizi", "\u5c49\u5b50", "\u5c5c\u5b50", 100, False),
    ("jiaojiao", "\u7f34\u4ea4", "\u7e73\u4ea4", 420, True),
    ("jiaoxin", "\u8f83\u65b0", "\u8f03\u65b0", 620, True),
    ("jiaojiu", "\u8f83\u65e7", "\u8f03\u820a", 520, True),
    ("gongzhang", "\u516c\u8d26", "\u516c\u8cec", 260, True),
    ("gonghu", "\u516c\u6237", "\u516c\u6236", 300, True),
    ("bule", "\u8865\u4e86", "\u88dc\u4e86", 420, True),
    ("jingshouyi", "\u51c0\u6536\u76ca", "\u6de8\u6536\u76ca", 520, True),
)


class DailyAccessAccountsTests(unittest.TestCase):
    def test_manifest_calibration_is_idempotent(self):
        entries, _ = builder._parse_curated_daily_phrase_entries(
            (ROOT / "manifests/curated_daily_supplement_phrases.tsv").read_bytes(), 2)
        wanted = {(query, sc) for query, sc, _, _, _ in ROWS}
        selected = [row for row in entries if (row[3], row[0]) in wanted]
        regular, exact = builder._partition_curated_daily_post_rank_exact_entries(selected)
        self.assertFalse(regular)
        self.assertEqual(len(ROWS), len(exact))
        sc = {(query, word): 1 for query, word, _, _, _ in ROWS}
        tc = {(query, word): 1000 for query, _, word, _, _ in ROWS}
        expected = tuple({(row[0], row[index]): row[3] for row in ROWS} for index in (1, 2))
        for _ in range(2):
            builder._inject_curated_daily_post_rank_exact_entries(sc, tc, exact)
            self.assertEqual(expected, (sc, tc))

    def test_generated_words_weights_and_flags(self):
        for variant, index in (("sc", 1), ("tc", 2)):
            path = ROOT / f"data/generated/dict_clean_{variant}.txt"
            with path.open(encoding="utf-8") as stream:
                rows = [line.rstrip("\r\n").split("\t") for line in stream]
            words = {tuple(row[:2]): row[2:] for row in rows}
            self.assertEqual(len(rows), len(words))
            for row in ROWS:
                expected = [str(row[3])] + (["no_contains"] if row[4] else [])
                with self.subTest(variant=variant, word=row[index]):
                    self.assertEqual(expected, words[(row[0], row[index])])
            ranks = load_merged_dict([path])
            self.assertEqual("\u63a5\u5165", ranks["jieru"][0][0])
            self.assertIn(("\u4ecb\u5165", 758), ranks["jieru"])
            self.assertEqual("\u68af\u5b50", ranks["tizi"][0][0])
            self.assertIn(("\u8e44\u5b50", 119), ranks["tizi"])

    def test_completion_priors_do_not_invent_corpus_evidence(self):
        for variant, index in (("sc", 1), ("tc", 2)):
            with (ROOT / f"data/generated/dict_completion_prior_{variant}.txt").open(encoding="utf-8") as stream:
                priors = {tuple(row[:2]): tuple(map(int, row[2:]))
                          for row in (line.rstrip().split("\t") for line in stream)}
            for row in ROWS:
                if row[4]:
                    with self.subTest(variant=variant, word=row[index]):
                        self.assertEqual((80, 0, 0, 0, 0, 0, 0), priors[(row[0], row[index])])


if __name__ == "__main__":
    unittest.main()
