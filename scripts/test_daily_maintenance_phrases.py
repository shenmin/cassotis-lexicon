"""Daily maintenance phrases and conservative shiti homophone ranks."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from validate_regression_samples import load_merged_dict

ROWS = (
    ("chale", "\u5dee\u4e86", "\u5dee\u4e86", 560),
    ("weixiudian", "\u7ef4\u4fee\u5e97", "\u7dad\u4fee\u5e97", 600),
    ("jiuyou", "\u65e7\u6709", "\u820a\u6709", 450),
    ("biyuan", "\u95ed\u6e90", "\u9589\u6e90", 560),
    ("nengya", "\u80fd\u5440", "\u80fd\u5440", 360),
    ("nengba", "\u80fd\u5427", "\u80fd\u5427", 420),
    ("nayibu", "\u54ea\u4e00\u6b65", "\u54ea\u4e00\u6b65", 520),
    ("neiyibu", "\u54ea\u4e00\u6b65", "\u54ea\u4e00\u6b65", 440),
    ("haowu", "\u597d\u7269", "\u597d\u7269", 520),
    ("xianniurou", "\u9c9c\u725b\u8089", "\u9bae\u725b\u8089", 560),
    ("hunzhe", "\u6df7\u7740", "\u6df7\u8457", 420),
)
WEIGHTS = (
    ("shiti", "\u5b9e\u4f53", "\u5be6\u9ad4", 1000),
    ("shiti", "\u8bd5\u9898", "\u8a66\u984c", 600),
    ("shiti", "\u5c38\u4f53", "\u5c4d\u9ad4", 300),
)


class DailyMaintenanceTests(unittest.TestCase):
    def test_explicit_ranks_survive_rebuild(self):
        entries, _ = builder._parse_curated_daily_phrase_entries(
            (ROOT / "manifests/curated_daily_supplement_phrases.tsv").read_bytes(), 2)
        wanted = {(row[0], row[1]) for row in ROWS + WEIGHTS}
        selected = [entry for entry in entries if (entry[3], entry[0]) in wanted]
        regular, exact = builder._partition_curated_daily_post_rank_exact_entries(selected)
        self.assertFalse(regular)
        self.assertEqual(len(wanted), len(exact))
        maps = ({}, {})
        builder._inject_curated_daily_post_rank_exact_entries(*maps, exact)
        builder._inject_curated_daily_post_rank_exact_entries(*maps, exact)
        for index, mapping in enumerate(maps, 1):
            self.assertEqual({(row[0], row[index]): row[3] for row in ROWS + WEIGHTS}, mapping)

    def test_generated_entries_are_exact_only_and_unique(self):
        for index, variant in enumerate(("sc", "tc"), 1):
            rows = {}
            for line in (ROOT / f"data/generated/dict_clean_{variant}.txt").read_text(
                    encoding="utf-8").splitlines():
                fields = line.split("\t")
                key = tuple(fields[:2])
                self.assertNotIn(key, rows)
                rows[key] = fields[2:]
            for row in ROWS:
                self.assertEqual([str(row[3]), "no_contains"], rows[(row[0], row[index])])
            for row in WEIGHTS:
                self.assertEqual(str(row[3]), rows[(row[0], row[index])][0])

    def test_shiti_order_preserves_corpse_as_a_regular_candidate(self):
        for variant, expected in (
                ("sc", ("\u5b9e\u4f53", "\u8bd5\u9898", "\u5c38\u4f53")),
                ("tc", ("\u5be6\u9ad4", "\u8a66\u984c", "\u5c4d\u9ad4"))):
            rows = load_merged_dict([ROOT / f"data/generated/dict_clean_{variant}.txt"])
            self.assertEqual(list(expected), [text for text, _ in rows["shiti"][:3]])
            self.assertGreater(rows["shiti"][2][1], 0)

    def test_added_terms_do_not_fabricate_corpus_support(self):
        for index, variant in enumerate(("sc", "tc"), 1):
            priors = {}
            for line in (ROOT / f"data/generated/dict_completion_prior_{variant}.txt").read_text(
                    encoding="utf-8").splitlines():
                fields = line.split("\t")
                priors[tuple(fields[:2])] = tuple(map(int, fields[2:]))
            for row in ROWS:
                self.assertEqual((80, 0, 0, 0, 0, 0, 0), priors[(row[0], row[index])])


if __name__ == "__main__":
    unittest.main()
