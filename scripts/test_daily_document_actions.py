"""Keep document/action entries explicit, reproducible, and selectable."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from validate_regression_samples import load_merged_dict

MARKER = "# Document and keyboard/touch actions, 2026-09-16."
WORDS = (
    ("xinwengao", "\u65b0\u6587\u7a3f", "\u65b0\u6587\u7a3f", 420),
    ("changan", "\u957f\u6309", "\u9577\u6309", 680),
    ("lianan", "\u8fde\u6309", "\u9023\u6309", 500),
)


class DailyDocumentActionTests(unittest.TestCase):
    def test_curated_weights_survive_rebuild(self):
        payload = (ROOT / "manifests/curated_daily_supplement_phrases.tsv").read_text(
            encoding="utf-8").split(MARKER, 1)[1].split("\n\n", 1)[0]
        entries, _ = builder._parse_curated_daily_phrase_entries(payload.encode("utf-8"), 2)
        regular, exact = builder._partition_curated_daily_post_rank_exact_entries(entries)
        self.assertFalse(regular)
        self.assertEqual(3, len(exact))
        maps = ({}, {})
        builder._inject_curated_daily_post_rank_exact_entries(*maps, exact)
        for i in range(2):
            self.assertEqual({(row[0], row[i + 1]): row[3] for row in WORDS}, maps[i])
        self.assertEqual(["chang", "an"], builder._runtime_parse_compact_pinyin("changan"))

    def test_generated_rows_and_priors(self):
        for i, variant in enumerate(("sc", "tc")):
            expected = {(row[0], row[i + 1]): row[3] for row in WORDS}
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

    def test_homophone_order(self):
        for i, variant in enumerate(("sc", "tc")):
            rows = load_merged_dict([ROOT / f"data/generated/dict_clean_{variant}.txt"])
            for row, limit in zip(WORDS, (2, 2, 1)):
                self.assertIn((row[i + 1], row[3]), rows[row[0]][:limit])
            self.assertEqual(("\u65b0\u95fb\u7a3f", "\u65b0\u805e\u7a3f")[i], rows["xinwengao"][0][0])
            self.assertEqual(("\u957f\u5b89", "\u9577\u5b89")[i], rows["changan"][0][0])


if __name__ == "__main__":
    unittest.main()
