"""The everyday sequencing phrase survives dictionary regeneration."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from test_daily_whitespace_phrases import read_rows

ROWS = (
    ("xianzuo", "先做", "先做", 500),
    ("danyou", "但又", "但又", 450),
    ("quehai", "却还", "卻還", 450),
    ("tidiao", "踢掉", "踢掉", 500),
)


class DailySequenceTests(unittest.TestCase):
    def test_explicit_reading_and_weight_survive_rebuild(self):
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

    def test_generated_entry_and_no_fabricated_corpus_support(self):
        for index, variant in enumerate(("sc", "tc"), 1):
            rows = read_rows(f"dict_clean_{variant}.txt")
            priors = read_rows(f"dict_completion_prior_{variant}.txt")
            for row in ROWS:
                key = (row[0], row[index])
                self.assertEqual([str(row[3]), "no_contains"], rows[key])
                self.assertEqual((80, 0, 0, 0, 0, 0, 0), tuple(map(int, priors[key])))
            self.assertNotIn(("quehuan", ROWS[2][index]), rows)


if __name__ == "__main__":
    unittest.main()
