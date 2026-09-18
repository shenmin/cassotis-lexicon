"""Cryptographic key aliases must coexist without changing unrelated readings."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from validate_regression_samples import load_merged_dict

MARKER = "# Cryptographic keys: retain existing readings and accept yao/yue, 2026-09-18."
WORDS = ("\u516c\u94a5", "\u79c1\u94a5", "\u5bc6\u94a5")
TRADITIONAL = ("\u516c\u9470", "\u79c1\u9470", "\u5bc6\u9470")
READINGS = (("gongyue", "gongyao"), ("siyue", "siyao"), ("miyue", "miyao"))


class DailyCryptoKeyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = (ROOT / "manifests/curated_daily_supplement_phrases.tsv").read_text(
            encoding="utf-8").split(MARKER, 1)[1].split("\n\n", 1)[0].encode("utf-8")
        entries, _ = builder._parse_curated_daily_phrase_entries(cls.payload, 2)
        cls.regular, cls.exact = builder._partition_curated_daily_post_rank_exact_entries(entries)
        cls.maps = ({}, {})
        builder._inject_curated_daily_post_rank_exact_entries(*cls.maps, cls.exact)

    def test_explicit_aliases_are_reproducible_and_do_not_replace_existing_readings(self):
        self.assertFalse(self.regular)
        self.assertEqual(4, len(self.exact))
        self.assertEqual((set(), set()), builder._parse_curated_contains_popularity_exclusions(self.payload))
        for index, words in enumerate((WORDS, TRADITIONAL)):
            expected = {(READINGS[0][0], words[0]): 420, (READINGS[0][1], words[0]): 420,
                        (READINGS[1][0], words[1]): 379, (READINGS[2][1], words[2]): 280}
            self.assertEqual(expected, self.maps[index])
        sc = {("miyue", WORDS[2]): 280, ("siyao", WORDS[1]): 379}
        tc = {("miyue", TRADITIONAL[2]): 280, ("siyao", TRADITIONAL[1]): 422}
        for _ in range(2):
            builder._inject_curated_daily_post_rank_exact_entries(sc, tc, self.exact)
        self.assertEqual(6, len(sc))
        self.assertEqual(6, len(tc))
        self.assertEqual(379, sc[("siyao", WORDS[1])])
        self.assertEqual(422, tc[("siyao", TRADITIONAL[1])])

    def test_generated_weights_and_popularity(self):
        for index, variant in enumerate(("sc", "tc")):
            for filename, expected in (
                (f"dict_clean_{variant}.txt", {k: [str(v)] for k, v in self.maps[index].items()}),
                (f"dict_completion_prior_{variant}.txt",
                 {k: ["80", "0", "0", "0", "0", "0", "0"] for k in self.maps[index]}),
            ):
                found = {}
                with (ROOT / "data/generated" / filename).open(encoding="utf-8") as stream:
                    for line in stream:
                        row = line.rstrip().split("\t")
                        key = tuple(row[:2])
                        if key in expected:
                            self.assertNotIn(key, found)
                            found[key] = row[2:]
                self.assertEqual(expected, found)

    def test_both_readings_are_on_the_first_page_in_both_scripts(self):
        for variant, words in (("sc", WORDS), ("tc", TRADITIONAL)):
            rows = load_merged_dict([ROOT / f"data/generated/dict_clean_{variant}.txt",
                                    ROOT / f"data/generated/dict_unihan_{variant}.txt"])
            for word, readings in zip(words, READINGS):
                for py in readings:
                    self.assertEqual(2, len(builder._runtime_parse_compact_pinyin(py)))
                    self.assertIn(word, [text for text, _ in rows[py][:2]])
            for py, sc, tc in (("gongyue", "\u516c\u7ea6", "\u516c\u7d04"),
                               ("siyue", "\u56db\u6708", "\u56db\u6708"),
                               ("miyue", "\u871c\u6708", "\u871c\u6708"),
                               ("miyao", "\u8ff7\u836f", "\u8ff7\u85e5")):
                self.assertEqual(sc if variant == "sc" else tc, rows[py][0][0])


if __name__ == "__main__":
    unittest.main()
