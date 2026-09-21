"""An explicit phrase must not raise the weights of its homophone fragments."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from validate_regression_samples import load_merged_dict

MARKER = "# Explicit requested phrase, 2026-09-21; no fragment popularity reinforcement."
PINYIN = "dingzaipiguhoumian"
WORDS = ("\u76ef\u5728\u5c41\u80a1\u540e\u9762",
         "\u76ef\u5728\u5c41\u80a1\u5f8c\u9762")


class DailyDingPhraseTests(unittest.TestCase):
    def test_rebuild_adds_only_the_explicit_phrase(self):
        payload = (ROOT / "manifests/curated_daily_supplement_phrases.tsv").read_text(
            encoding="utf-8").split(MARKER, 1)[1].split("\n\n", 1)[0].encode("utf-8")
        entries, _ = builder._parse_curated_daily_phrase_entries(payload, 2)
        regular, exact = builder._partition_curated_daily_post_rank_exact_entries(entries)
        self.assertFalse(regular)
        self.assertEqual(1, len(exact))
        self.assertEqual(["ding", "zai", "pi", "gu", "hou", "mian"],
                         builder._runtime_parse_compact_pinyin(PINYIN))
        maps = ({}, {})
        for _ in range(2):
            builder._inject_curated_daily_post_rank_exact_entries(*maps, exact)
        for mapping, word in zip(maps, WORDS):
            self.assertEqual({(PINYIN, word): 180}, mapping)
        self.assertEqual(({WORDS[0]}, {WORDS[1]}),
                         builder._parse_curated_contains_popularity_exclusions(payload))

    def test_generated_entry_and_no_invented_corpus_evidence(self):
        for variant, word in zip(("sc", "tc"), WORDS):
            for kind, suffix in (("clean", ["180", "no_contains"]),
                                 ("completion_prior", ["80", "0", "0", "0", "0", "0", "0"])):
                matches = []
                with (ROOT / f"data/generated/dict_{kind}_{variant}.txt").open(
                        encoding="utf-8") as stream:
                    for line in stream:
                        row = line.rstrip().split("\t")
                        if row[:2] == [PINYIN, word]:
                            matches.append(row[2:])
                self.assertEqual([suffix], matches)
            rows = load_merged_dict([ROOT / f"data/generated/dict_clean_{variant}.txt"])
            self.assertEqual([(word, 180)], rows[PINYIN])
            expected = {("\u9489\u5728", 10), ("\u9876\u5728", 10)} if variant == "sc" else {
                ("\u91d8\u5728", 10), ("\u9802\u5728", 10)}
            self.assertEqual(expected, set(rows["dingzai"]))

    def test_completion_index_uses_the_same_phrase_and_weight(self):
        for variant, word in zip(("sc", "tc"), WORDS):
            matches = []
            with (ROOT / f"data/generated/dict_completion_lookup_{variant}.txt").open(
                    encoding="utf-8") as stream:
                for line in stream:
                    row = line.rstrip().split("\t")
                    if row[1:3] == [PINYIN, word]:
                        matches.append(row)
            self.assertEqual({"dingzai", "dingzaipi", "dingzaipigu", "dingzaipiguhou"},
                             {row[0] for row in matches})
            self.assertEqual(4, len(matches))
            for row in matches:
                self.assertEqual(["180", "80", "0", "0", "0", "0", "0", "0", "0"], row[3:12])


if __name__ == "__main__":
    unittest.main()
