"""Keep the literary reading and its completion indexes in agreement."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from validate_regression_samples import load_merged_dict

AUTUMN = "\u79cb\u6c34"
SWIM = "\u6cc5\u6c34"
QUOTES = (AUTUMN + "\u5171\u957f\u5929\u4e00\u8272",
          AUTUMN + "\u5171\u9577\u5929\u4e00\u8272")
READING = "qiushuigongchangtianyise"
OLD_READING = "qiushuigongzhangtianyise"


class AutumnWaterReadingTests(unittest.TestCase):
    def test_reading_override_replaces_wrong_reading_without_changing_weight(self):
        overrides = builder._load_pinyin_overrides(ROOT / "manifests/pinyin_overrides.tsv")
        for quote in QUOTES:
            self.assertEqual(READING, overrides[quote])
            mapping = {(OLD_READING, quote): 451, ("qiushui", AUTUMN): 600,
                       ("qiushui", SWIM): 433}
            for _ in range(2):
                mapping, _ = builder._apply_word_pinyin_overrides(mapping, overrides, "test")
            self.assertEqual({(READING, quote): 451, ("qiushui", AUTUMN): 600,
                              ("qiushui", SWIM): 433}, mapping)

    def test_weight_is_a_reproducible_exact_override(self):
        payload = (ROOT / "manifests/curated_daily_supplement_phrases.tsv").read_bytes()
        entries, _ = builder._parse_curated_daily_phrase_entries(payload, 2)
        _, exact = builder._partition_curated_daily_post_rank_exact_entries(entries)
        sc, tc = {}, {}
        for _ in range(2):
            builder._inject_curated_daily_post_rank_exact_entries(sc, tc, exact)
        self.assertEqual(600, sc[("qiushui", AUTUMN)])
        self.assertEqual(600, tc[("qiushui", AUTUMN)])

    def test_generated_dictionary_reading_and_rank(self):
        for variant, quote in zip(("sc", "tc"), QUOTES):
            rows = load_merged_dict([ROOT / f"data/generated/dict_clean_{variant}.txt"])
            self.assertEqual([(AUTUMN, 600), (SWIM, 433)], rows["qiushui"])
            self.assertIn((quote, 451), rows[READING])
            self.assertNotIn(quote, [text for text, _ in rows.get(OLD_READING, [])])

    def test_completion_indexes_do_not_retain_the_wrong_reading(self):
        for variant, quote in zip(("sc", "tc"), QUOTES):
            prior_rows, lookup_rows = [], []
            for kind, rows, text_col in (("prior", prior_rows, 1), ("lookup", lookup_rows, 2)):
                with (ROOT / f"data/generated/dict_completion_{kind}_{variant}.txt").open(
                        encoding="utf-8") as stream:
                    for line in stream:
                        row = line.rstrip().split("\t")
                        if len(row) > text_col and row[text_col] == quote:
                            rows.append(row)
            self.assertEqual(1, len(prior_rows))
            self.assertEqual(9, len(prior_rows[0]))
            self.assertEqual(READING, prior_rows[0][0])
            self.assertTrue(lookup_rows)
            self.assertTrue(all(len(row) == 13 for row in lookup_rows))
            self.assertTrue(all(row[1] == READING and READING.startswith(row[0])
                                for row in lookup_rows))
            self.assertIn("qiushuigongchang", {row[0] for row in lookup_rows})
            self.assertFalse(any("zhang" in row[0] for row in lookup_rows))


if __name__ == "__main__":
    unittest.main()
