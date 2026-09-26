"""Check daily pronoun phrases without changing corpus or homophone evidence."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from validate_regression_samples import load_merged_dict

ROWS = (
    ("zaita", "\u5728\u4ed6", "\u5728\u4ed6", 420, True),
    ("zaita", "\u5728\u5979", "\u5728\u5979", 420, True),
    ("youni", "\u7531\u4f60", "\u7531\u4f60", 420, True),
    ("youni", "\u6709\u4f60", "\u6709\u4f60", 480, True),
    ("youwo", "\u6709\u6211", "\u6709\u6211", 480, True),
    ("youwo", "\u7531\u6211", "\u7531\u6211", 420, True),
    ("youta", "\u7531\u5979", "\u7531\u5979", 380, True),
    ("youta", "\u7531\u4ed6", "\u7531\u4ed6", 380, True),
    ("youta", "\u6709\u4ed6", "\u6709\u4ed6", 420, True),
    ("youta", "\u6709\u5979", "\u6709\u5979", 420, True),
    ("renni", "\u4efb\u4f60", "\u4efb\u4f60", 320, True),
    ("renwo", "\u4efb\u6211", "\u4efb\u6211", 320, True),
    ("renta", "\u4efb\u4ed6", "\u4efb\u4ed6", 320, True),
    ("renta", "\u4efb\u5979", "\u4efb\u5979", 320, True),
    ("qianta", "\u7275\u5979", "\u727d\u5979", 240, True),
    ("qianta", "\u7275\u4ed6", "\u727d\u4ed6", 240, True),
    ("qianta", "\u6b20\u4ed6", "\u6b20\u4ed6", 260, True),
    ("qianta", "\u6b20\u5979", "\u6b20\u5979", 260, True),
    ("qianta", "\u7b7e\u5979", "\u7c3d\u5979", 120, True),
    ("qianta", "\u7b7e\u4ed6", "\u7c3d\u4ed6", 120, True),
    ("qianni", "\u7275\u4f60", "\u727d\u4f60", 240, True),
    ("qianwo", "\u7b7e\u6211", "\u7c3d\u6211", 120, True),
    ("qianni", "\u7b7e\u4f60", "\u7c3d\u4f60", 120, True),
    ("qianwo", "\u7275\u6211", "\u727d\u6211", 240, True),
    ("qianni", "\u6b20\u4f60", "\u6b20\u4f60", 260, True),
    ("qianwo", "\u6b20\u6211", "\u6b20\u6211", 260, True),
    ("fangni", "\u9632\u4f60", "\u9632\u4f60", 220, True),
    ("fangwo", "\u9632\u6211", "\u9632\u6211", 220, True),
    ("fangta", "\u9632\u4ed6", "\u9632\u4ed6", 220, True),
    ("fangta", "\u9632\u5979", "\u9632\u5979", 220, True),
    ("suita", "\u968f\u5979", "\u96a8\u5979", 198, True),
    ("suita", "\u968f\u4ed6", "\u96a8\u4ed6", 198, True),
    ("suiwo", "\u968f\u6211", "\u96a8\u6211", 198, True),
)


class DailyPronounPhrasesTests(unittest.TestCase):
    def test_manifest_weights_are_reproducible(self):
        entries, _ = builder._parse_curated_daily_phrase_entries(
            (ROOT / "manifests/curated_daily_supplement_phrases.tsv").read_bytes(), 2)
        wanted = {(row[0], row[1]) for row in ROWS}
        selected = [row for row in entries if (row[3], row[0]) in wanted]
        regular, exact = builder._partition_curated_daily_post_rank_exact_entries(selected)
        self.assertFalse(regular)
        self.assertEqual(len(ROWS), len(exact))
        sc, tc = {}, {}
        expected = tuple({(row[0], row[index]): row[3] for row in ROWS} for index in (1, 2))
        for _ in range(2):
            builder._inject_curated_daily_post_rank_exact_entries(sc, tc, exact)
            self.assertEqual(expected, (sc, tc))

    def test_generated_rows_and_homophone_ranks(self):
        for variant, index in (("sc", 1), ("tc", 2)):
            path = ROOT / f"data/generated/dict_clean_{variant}.txt"
            with path.open(encoding="utf-8") as stream:
                rows = [line.rstrip("\r\n").split("\t") for line in stream]
            words = {tuple(row[:2]): row[2:] for row in rows}
            self.assertEqual(len(rows), len(words))
            for row in ROWS:
                with self.subTest(variant=variant, word=row[index]):
                    self.assertEqual([str(row[3]), "no_contains"], words[(row[0], row[index])])
            ranks = load_merged_dict([path])
            self.assertEqual(("\u6cb9\u817b", 660) if variant == "sc" else ("\u6cb9\u81a9", 660),
                             ranks["youni"][0])
            self.assertEqual(("\u6709\u6211", 480), ranks["youwo"][0])
            self.assertIn(("\u4f18\u6e25", 378) if variant == "sc" else ("\u512a\u6e25", 378),
                          ranks["youwo"])
            self.assertEqual(["198"], words[("suini", "\u968f\u4f60" if variant == "sc" else "\u96a8\u4f60")])

    def test_no_fabricated_completion_corpus_evidence(self):
        for variant, index in (("sc", 1), ("tc", 2)):
            with (ROOT / f"data/generated/dict_completion_prior_{variant}.txt").open(encoding="utf-8") as stream:
                priors = {tuple(row[:2]): tuple(map(int, row[2:]))
                          for row in (line.rstrip().split("\t") for line in stream)}
            for row in ROWS:
                with self.subTest(variant=variant, word=row[index]):
                    self.assertEqual((80, 0, 0, 0, 0, 0, 0), priors[(row[0], row[index])])


if __name__ == "__main__":
    unittest.main()
