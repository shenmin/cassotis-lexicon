"""Authentication terms remain exact choices without replacing common words."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from test_daily_whitespace_phrases import read_rows

ROWS = (
    ("jianquan", "鉴权", "鑑權", 500),
    ("jianmi", "鉴密", "鑑密", 180),
)


class DailyAuthenticationTests(unittest.TestCase):
    def test_explicit_readings_and_weights_survive_rebuild(self):
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

    def test_generated_entries_and_common_homophone(self):
        for index, variant in enumerate(("sc", "tc"), 1):
            rows = read_rows(f"dict_clean_{variant}.txt")
            for row in ROWS:
                self.assertEqual([str(row[3]), "no_contains"], rows[(row[0], row[index])])
            self.assertGreater(int(rows[("jianquan", "健全")][0]),
                               int(rows[("jianquan", ROWS[0][index])][0]))

    def test_no_fabricated_corpus_support(self):
        for index, variant in enumerate(("sc", "tc"), 1):
            rows = read_rows(f"dict_completion_prior_{variant}.txt")
            for row in ROWS:
                self.assertEqual((80, 0, 0, 0, 0, 0, 0),
                                 tuple(map(int, rows[(row[0], row[index])])))


if __name__ == "__main__":
    unittest.main()
