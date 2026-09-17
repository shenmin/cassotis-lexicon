"""Keep productive ke phrases selectable without inventing corpus evidence."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from validate_regression_samples import load_merged_dict

MARKER = "# Productive ke + action/property phrases, 2026-09-17."


class DailyKePhraseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        payload = (ROOT / "manifests/curated_daily_supplement_phrases.tsv").read_text(
            encoding="utf-8").split(MARKER, 1)[1].split("\n\n", 1)[0]
        cls.rows = [line.split("\t") for line in payload.splitlines()
                    if line and not line.startswith("#")]
        cls.entries, _ = builder._parse_curated_daily_phrase_entries(payload.encode("utf-8"), 2)
        cls.regular, cls.exact = builder._partition_curated_daily_post_rank_exact_entries(cls.entries)
        cls.maps = ({}, {})
        builder._inject_curated_daily_post_rank_exact_entries(*cls.maps, cls.exact)

    def test_all_requested_phrases_have_reproducible_positive_ranks(self):
        self.assertFalse(self.regular)
        self.assertEqual(39, len(self.exact))
        for index in (0, 1):
            expected = {(r[3], r[index]): round(float(r[2]) * 1000) for r in self.rows}
            self.assertEqual(39, len(expected))
            self.assertEqual(expected, self.maps[index])
            self.assertTrue(all(80 <= weight <= 680 for weight in expected.values()))
        self.assertTrue(all(r[4] == "exact_rank_no_contains" for r in self.rows))
        builder._inject_curated_daily_post_rank_exact_entries(*self.maps, self.exact)
        self.assertEqual(39, len(self.maps[0]))

    def test_two_complete_syllables_and_script_forms(self):
        for py, text in self.maps[0]:
            self.assertEqual(2, len(text))
            self.assertEqual("\u53ef", text[0])
            syllables = builder._runtime_parse_compact_pinyin(py)
            self.assertEqual(2, len(syllables))
            self.assertEqual("ke", syllables[0])
        for py, text in (("kexie", "\u53ef\u5beb"), ("kedu", "\u53ef\u8b80"),
                         ("ketuo", "\u53ef\u812b"), ("kechang", "\u53ef\u5617"),
                         ("kezhuang", "\u53ef\u88dd"), ("kezu", "\u53ef\u7d44")):
            self.assertIn((py, text), self.maps[1])

    def test_generated_rows_and_no_synthetic_popularity(self):
        for index, variant in enumerate(("sc", "tc")):
            expected = self.maps[index]
            for filename, values in (
                (f"dict_clean_{variant}.txt", {k: [str(v), "no_contains"] for k, v in expected.items()}),
                (f"dict_completion_prior_{variant}.txt", {k: ["80", "0", "0", "0", "0", "0", "0"] for k in expected}),
            ):
                found = {}
                with (ROOT / "data/generated" / filename).open(encoding="utf-8") as stream:
                    for line in stream:
                        row = line.rstrip().split("\t")
                        key = tuple(row[:2])
                        if key in expected:
                            self.assertNotIn(key, found)
                            found[key] = row[2:]
                self.assertEqual(values, found)

    def test_visibility_and_common_homophones(self):
        for index, variant in enumerate(("sc", "tc")):
            rows = load_merged_dict([ROOT / f"data/generated/dict_clean_{variant}.txt",
                                    ROOT / f"data/generated/dict_unihan_{variant}.txt"])
            for py, word in self.maps[index]:
                self.assertIn(word, [text for text, _ in rows[py][:9]])
            for py, sc, tc in (("keai", "\u53ef\u7231", "\u53ef\u611b"),
                               ("keguan", "\u5ba2\u89c2", "\u5ba2\u89c0"),
                               ("kecheng", "\u8bfe\u7a0b", "\u8ab2\u7a0b"),
                               ("kejian", "\u53ef\u89c1", "\u53ef\u898b"),
                               ("keshui", "\u778c\u7761", "\u778c\u7761")):
                self.assertEqual((sc, tc)[index], rows[py][0][0])
            self.assertEqual(("\u53ef\u5199", "\u53ef\u5beb")[index], rows["kexie"][0][0])
            self.assertEqual(("\u53ef\u8bfb", "\u53ef\u8b80")[index], rows["kedu"][0][0])


if __name__ == "__main__":
    unittest.main()
