"""Keep a common pronoun phrase ahead of the specialized homophone."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder

WORDS = {"sc": "\u6211\u5bf9", "tc": "\u6211\u5c0d"}


class DailyWoduiTests(unittest.TestCase):
    def test_manifest_survives_post_rank_calibration(self):
        payload = (ROOT / "manifests/curated_daily_supplement_phrases.tsv").read_bytes()
        entries, _ = builder._parse_curated_daily_phrase_entries(payload, 2)
        selected = [entry for entry in entries if entry[0] == WORDS["sc"]]
        regular, exact = builder._partition_curated_daily_post_rank_exact_entries(selected)
        self.assertFalse(regular)
        self.assertEqual(1, len(exact))
        actual = ({}, {})
        builder._inject_curated_daily_post_rank_exact_entries(*actual, exact)
        self.assertEqual(tuple({("wodui", WORDS[v]): 700} for v in ("sc", "tc")), actual)

    def test_generated_weights_preserve_the_existing_homophone(self):
        for variant, word in WORDS.items():
            with (ROOT / f"data/generated/dict_clean_{variant}.txt").open(encoding="utf-8") as stream:
                rows = [line.rstrip().split("\t") for line in stream if line.startswith("wodui\t")]
            with self.subTest(variant=variant):
                self.assertEqual([["wodui", word, "700", "no_contains"],
                                  ["wodui", "\u6e25\u5806", "351"]], rows)


if __name__ == "__main__":
    unittest.main()
