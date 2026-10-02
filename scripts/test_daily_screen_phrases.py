"""Screen states and common daily phrases retain conservative exact ranks."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder

ROWS = (
    ("xiping", "\u606f\u5c4f", "\u606f\u5c4f", 560),
    ("haoji", "\u597d\u8bb0", "\u597d\u8a18", 0),
    ("yiji", "\u6613\u8bb0", "\u6613\u8a18", 360),
    ("liangping", "\u4eae\u5c4f", "\u4eae\u5c4f", 420),
    ("zheliangxiang", "\u8fd9\u4e24\u9879", "\u9019\u5169\u9805", 520),
    ("sixian", "\u6b7b\u7ebf", "\u6b7b\u7dda", 320),
    ("huoxian", "\u6d3b\u7ebf", "\u6d3b\u7dda", 240),
    ("zhelia", "\u8fd9\u4fe9", "\u9019\u5006", 480),
    ("nalia", "\u90a3\u4fe9", "\u90a3\u5006", 480),
)


class DailyScreenPhraseTests(unittest.TestCase):
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
        builder._inject_curated_daily_post_rank_exact_entries(*maps, exact)
        for index, mapping in enumerate(maps, 1):
            self.assertEqual({(row[0], row[index]): row[3] for row in ROWS}, mapping)

    def test_generated_entries_are_unique_and_exact_ranked(self):
        for index, variant in enumerate(("sc", "tc"), 1):
            rows = {}
            for line in (ROOT / f"data/generated/dict_clean_{variant}.txt").read_text(
                    encoding="utf-8").splitlines():
                fields = line.split("\t")
                key = tuple(fields[:2])
                self.assertNotIn(key, rows)
                rows[key] = fields[2:]
            for row in ROWS:
                self.assertEqual([str(row[3]), "no_contains"], rows[(row[0], row[index])])
            for query, preferred, new_word in (
                    ("haoji", "\u597d\u51e0" if variant == "sc" else "\u597d\u5e7e", ROWS[1][index]),
                    ("yiji", "\u4ee5\u53ca", ROWS[2][index]),
                    ("huoxian", "\u706b\u7ebf" if variant == "sc" else "\u706b\u7dda", ROWS[6][index])):
                self.assertGreater(int(rows[(query, preferred)][0]), int(rows[(query, new_word)][0]))

    def test_added_terms_do_not_fabricate_corpus_support(self):
        for index, variant in enumerate(("sc", "tc"), 1):
            priors = {}
            for line in (ROOT / f"data/generated/dict_completion_prior_{variant}.txt").read_text(
                    encoding="utf-8").splitlines():
                fields = line.split("\t")
                priors[tuple(fields[:2])] = tuple(map(int, fields[2:]))
            for row in ROWS:
                self.assertEqual((80, 0, 0, 0, 0, 0, 0), priors[(row[0], row[index])])


if __name__ == "__main__":
    unittest.main()
