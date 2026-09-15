"""Keep highlighting and counterintuitive-expression entries reproducible."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder

WORDS = {
    "sc": [("biaohong", "\u6807\u7ea2", 620),
           ("fanzhijue", "\u53cd\u76f4\u89c9", 460)],
    "tc": [("biaohong", "\u6a19\u7d05", 620),
           ("fanzhijue", "\u53cd\u76f4\u89ba", 460)],
}


class DailyHighlightPhrasesTests(unittest.TestCase):
    def test_manifest_preserves_weights_after_calibration(self):
        payload = (ROOT / "manifests/curated_daily_supplement_phrases.tsv").read_bytes()
        entries, _ = builder._parse_curated_daily_phrase_entries(payload, 2)
        selected = [entry for entry in entries
                    if entry[0] in {word for _, word, _ in WORDS["sc"]}]
        regular, exact = builder._partition_curated_daily_post_rank_exact_entries(selected)
        self.assertFalse(regular)
        self.assertEqual(2, len(exact))
        actual = ({}, {})
        expected = tuple({(py, word): weight for py, word, weight in WORDS[variant]}
                         for variant in ("sc", "tc"))
        for _ in range(2):
            builder._inject_curated_daily_post_rank_exact_entries(*actual, exact)
            self.assertEqual(expected, actual)

    def test_generated_entries_have_canonical_readings_and_weights(self):
        for variant, words in WORDS.items():
            with (ROOT / f"data/generated/dict_clean_{variant}.txt").open(encoding="utf-8") as stream:
                rows = [line.rstrip().split("\t") for line in stream]
            for py, word, weight in words:
                with self.subTest(variant=variant, word=word):
                    self.assertEqual([[py, word, str(weight), "no_contains"]],
                                     [row for row in rows if row[1] == word])

    def test_completion_priors_cover_new_entries(self):
        for variant, words in WORDS.items():
            with (ROOT / f"data/generated/dict_completion_prior_{variant}.txt").open(encoding="utf-8") as stream:
                priors = [line.rstrip().split("\t") for line in stream]
            for py, word, _ in words:
                with self.subTest(variant=variant, word=word):
                    matches = [row for row in priors if row[:2] == [py, word]]
                    self.assertEqual(1, len(matches))
                    self.assertEqual(9, len(matches[0]))

    def test_three_syllable_phrase_is_in_prefix_completion_pool(self):
        for variant in WORDS:
            py, word, weight = WORDS[variant][1]
            path = ROOT / f"data/generated/dict_completion_lookup_{variant}.txt"
            with path.open(encoding="utf-8") as stream:
                rows = [line.rstrip().split("\t") for line in stream
                        if line.startswith(f"fanzhi\t{py}\t")]
            with self.subTest(variant=variant):
                self.assertEqual(1, len(rows))
                self.assertEqual(13, len(rows[0]))
                self.assertEqual(["fanzhi", py, word, str(weight)], rows[0][:4])


if __name__ == "__main__":
    unittest.main()
