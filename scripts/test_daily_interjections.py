"""Whole-word interjections must survive dictionary rebuilds: the acknowledgement oo and laughter after a
(ahaha .. ahahahahaha), which the engine finds typed in full and abbreviated (ahh .. ahhhhh)."""
from pathlib import Path
import unittest

import build_external_cedict as builder
from test_daily_whitespace_phrases import read_rows


ROOT = Path(__file__).resolve().parents[1]
WORDS = {
    "oo": "哦哦",
    "ahaha": "啊哈哈",
    "ahahaha": "啊哈哈哈",
    "ahahahaha": "啊哈哈哈哈",
    "ahahahahaha": "啊哈哈哈哈哈",
}


class DailyInterjectionsTests(unittest.TestCase):
    def test_curated_reading(self):
        entries, _ = builder._parse_curated_daily_phrase_entries(
            (ROOT / "manifests/curated_daily_phrases.tsv").read_bytes(), 2
        )
        for pinyin, word in WORDS.items():
            with self.subTest(word=word):
                matches = [entry for entry in entries if entry[0] == word]
                self.assertEqual(1, len(matches))
                self.assertEqual(word, matches[0][1])
                self.assertEqual(pinyin, matches[0][3])

    def test_both_generated_dictionaries_and_priors(self):
        for variant in ("sc", "tc"):
            rows = read_rows(f"dict_clean_{variant}.txt")
            priors = read_rows(f"dict_completion_prior_{variant}.txt")
            for pinyin, word in WORDS.items():
                with self.subTest(variant=variant, word=word):
                    self.assertIn((pinyin, word), rows)
                    self.assertGreater(int(rows[(pinyin, word)][0]), 0)
                    self.assertIn((pinyin, word), priors)

    def test_laughter_completes_from_its_prefixes(self):
        # The completion lookup holds each longer laugh under every shorter one, as 哈哈哈 under haha.
        laughter = [pinyin for pinyin in WORDS if pinyin.startswith("a")]
        for variant in ("sc", "tc"):
            lookup = set()
            text = (ROOT / "data/generated" / f"dict_completion_lookup_{variant}.txt").read_text(encoding="utf-8")
            for line in text.splitlines():
                if line and not line.startswith("#"):
                    lookup.add(tuple(line.split("\t")[:3]))
            for prefix in ["aha"] + laughter:
                for pinyin in laughter:
                    if len(pinyin) > len(prefix) and pinyin.startswith(prefix):
                        with self.subTest(variant=variant, prefix=prefix, word=WORDS[pinyin]):
                            self.assertIn((prefix, pinyin, WORDS[pinyin]), lookup)


if __name__ == "__main__":
    unittest.main()
