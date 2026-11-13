"""The whole-word acknowledgement oo must survive dictionary rebuilds."""
from pathlib import Path
import unittest

import build_external_cedict as builder
from test_daily_whitespace_phrases import read_rows


ROOT = Path(__file__).resolve().parents[1]
WORD = "\u54e6\u54e6"


class DailyInterjectionsTests(unittest.TestCase):
    def test_curated_reading(self):
        entries, _ = builder._parse_curated_daily_phrase_entries(
            (ROOT / "manifests/curated_daily_phrases.tsv").read_bytes(), 2
        )
        matches = [entry for entry in entries if entry[0] == WORD]
        self.assertEqual(1, len(matches))
        self.assertEqual(WORD, matches[0][1])
        self.assertEqual("oo", matches[0][3])

    def test_both_generated_dictionaries_and_priors(self):
        for variant in ("sc", "tc"):
            with self.subTest(variant=variant):
                rows = read_rows(f"dict_clean_{variant}.txt")
                self.assertIn(("oo", WORD), rows)
                self.assertGreater(int(rows[("oo", WORD)][0]), 0)
                self.assertIn(
                    ("oo", WORD), read_rows(f"dict_completion_prior_{variant}.txt")
                )


if __name__ == "__main__":
    unittest.main()
