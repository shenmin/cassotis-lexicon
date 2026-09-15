"""Keep preheating ahead of the contextual phrase in both script variants."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from validate_regression_samples import load_merged_dict

WORDS = {
    "sc": {"\u9884\u70ed": 760, "\u9047\u70ed": 320},
    "tc": {"\u9810\u71b1": 760, "\u9047\u71b1": 320},
}


class PreheatingWeightTests(unittest.TestCase):
    def test_post_rank_calibration_overrides_both_high_and_low_weights(self):
        payload = (ROOT / "manifests/curated_daily_supplement_phrases.tsv").read_bytes()
        entries, _ = builder._parse_curated_daily_phrase_entries(payload, 2)
        selected = [entry for entry in entries if entry[3] == "yure"]
        regular, exact = builder._partition_curated_daily_post_rank_exact_entries(selected)
        self.assertFalse(regular)
        self.assertEqual(2, len(exact))
        sc = {("yure", "\u9884\u70ed"): 1, ("yure", "\u9047\u70ed"): 700}
        tc = {("yure", "\u9810\u71b1"): 336, ("yure", "\u9047\u71b1"): 224}
        expected = tuple({("yure", text): weight for text, weight in WORDS[v].items()}
                         for v in ("sc", "tc"))
        builder._inject_curated_daily_post_rank_exact_entries(sc, tc, exact)
        self.assertEqual(expected, (sc, tc))
        builder._inject_curated_daily_post_rank_exact_entries(sc, tc, exact)
        self.assertEqual(expected, (sc, tc))

    def test_generated_weights_and_order(self):
        for variant, expected in WORDS.items():
            with self.subTest(variant=variant):
                path = ROOT / f"data/generated/dict_clean_{variant}.txt"
                rows = load_merged_dict([path])["yure"]
                self.assertEqual(len(rows), len({word for word, _ in rows}))
                self.assertEqual(next(iter(expected)), rows[0][0])
                for text, weight in expected.items():
                    self.assertIn((text, weight), rows[:3])
                with path.open(encoding="utf-8") as stream:
                    actual = [line.rstrip("\r\n").split("\t") for line in stream
                              if line.startswith("yure\t")]
                self.assertTrue(all(len(fields) == 3 for fields in actual))


if __name__ == "__main__":
    unittest.main()
