"""Historical titles remain selectable without overriding common homophones."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder

WORDS = {
    "sc": [("renzong", "\u4ec1\u5b97", 360), ("renzu", "\u8ba4\u7956", 200),
           ("xiaozong", "\u5b5d\u5b97", 260), ("mingzong", "\u660e\u5b97", 240)],
    "tc": [("renzong", "\u4ec1\u5b97", 360), ("renzu", "\u8a8d\u7956", 200),
           ("xiaozong", "\u5b5d\u5b97", 260), ("mingzong", "\u660e\u5b97", 240)],
}


class DailyHistoryTitlesTests(unittest.TestCase):
    def test_manifest_injects_canonical_readings_after_calibration(self):
        payload = (ROOT / "manifests/curated_daily_supplement_phrases.tsv").read_bytes()
        entries, _ = builder._parse_curated_daily_phrase_entries(payload, 2)
        targets = {text for _, text, _ in WORDS["sc"]}
        selected = [entry for entry in entries if entry[0] in targets]
        regular, exact = builder._partition_curated_daily_post_rank_exact_entries(selected)
        self.assertFalse(regular)
        self.assertEqual(4, len(exact))
        actual = ({}, {})
        expected = tuple({(py, text): weight for py, text, weight in WORDS[v]}
                         for v in ("sc", "tc"))
        for _ in range(2):
            builder._inject_curated_daily_post_rank_exact_entries(*actual, exact)
            self.assertEqual(expected, actual)

    def test_generated_weights_and_common_homophone_priority(self):
        for variant, words in WORDS.items():
            with (ROOT / f"data/generated/dict_clean_{variant}.txt").open(encoding="utf-8") as stream:
                rows = [line.rstrip().split("\t") for line in stream]
            for py, text, weight in words:
                with self.subTest(variant=variant, word=text):
                    self.assertEqual([[py, text, str(weight), "no_contains"]],
                                     [row for row in rows if row[1] == text])
            homophones = {row[1]: int(row[2]) for row in rows if row[0] == "renzu"}
            self.assertEqual(216, homophones["\u4eba\u65cf"])
            self.assertGreater(homophones["\u4eba\u65cf"], homophones[words[1][1]])

    def test_completion_priors_cover_each_added_entry(self):
        for variant, words in WORDS.items():
            with (ROOT / f"data/generated/dict_completion_prior_{variant}.txt").open(encoding="utf-8") as stream:
                rows = [line.rstrip().split("\t") for line in stream]
            for py, text, _ in words:
                with self.subTest(variant=variant, word=text):
                    matches = [row for row in rows if row[:2] == [py, text]]
                    self.assertEqual(1, len(matches))
                    self.assertEqual(9, len(matches[0]))

    def test_ancestral_phrase_completion_is_anchored(self):
        for variant in WORDS:
            phrase = ("\u8ba4\u7956\u5f52\u5b97" if variant == "sc"
                      else "\u8a8d\u7956\u6b78\u5b97")
            with (ROOT / f"data/generated/dict_completion_lookup_{variant}.txt").open(encoding="utf-8") as stream:
                rows = [line.rstrip().split("\t") for line in stream
                        if line.startswith("renzu\trenzuguizong\t")]
            with self.subTest(variant=variant):
                self.assertEqual(1, len(rows))
                self.assertEqual(phrase, rows[0][2])
                self.assertEqual("1", rows[0][11])


if __name__ == "__main__":
    unittest.main()
