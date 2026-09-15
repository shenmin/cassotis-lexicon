"""Regression coverage for explicit nasal-final + ge vocabulary."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from validate_regression_samples import load_merged_dict

MARKER = "# Everyday an/ang + ge phrases, 2026-09-15."
WORDS = (
    ("xiangge", "\u60f3\u4e2a", "\u60f3\u500b", 640),
    ("changge", "\u5531\u4e2a", "\u5531\u500b", 520),
    ("changge", "\u5c1d\u4e2a", "\u5617\u500b", 360),
    ("jiangge", "\u8bb2\u4e2a", "\u8b1b\u500b", 640),
    ("xiange", "\u732e\u4e2a", "\u737b\u500b", 360),
    ("qiange", "\u7275\u4e2a", "\u727d\u500b", 320),
    ("bange", "\u529e\u4e2a", "\u8fa6\u500b", 620),
    ("pange", "\u76d8\u4e2a", "\u76e4\u500b", 420),
    ("pange", "\u76fc\u4e2a", "\u76fc\u500b", 260),
    ("pange", "\u6500\u4e2a", "\u6500\u500b", 180),
    ("bange", "\u62cc\u4e2a", "\u62cc\u500b", 320),
    ("fange", "\u53cd\u4e2a", "\u53cd\u500b", 260),
    ("fange", "\u7ffb\u4e2a", "\u7ffb\u500b", 580),
    ("dange", "\u62c5\u4e2a", "\u64d4\u500b", 320),
    ("tange", "\u63a2\u6208", "\u63a2\u6208", 580),
    ("tange", "\u8c08\u4e2a", "\u8ac7\u500b", 520),
    ("tange", "\u53f9\u4e2a", "\u5606\u500b", 280),
    ("tange", "\u8d2a\u4e2a", "\u8caa\u500b", 240),
    ("tange", "\u5f39\u4e2a", "\u5f48\u500b", 480),
    ("nange", "\u96be\u4e2a", "\u96e3\u500b", 120),
    ("nange", "\u96be\u54e5", "\u96e3\u54e5", 180),
    ("lange", "\u62e6\u4e2a", "\u6514\u500b", 320),
    ("lange", "\u63fd\u4e2a", "\u652c\u500b", 280),
    ("gange", "\u5e72\u54e5", "\u4e7e\u54e5", 180),
    ("kange", "\u770b\u4e2a", "\u770b\u500b", 640),
    ("kange", "\u780d\u4e2a", "\u780d\u500b", 300),
    ("kange", "\u4f83\u4e2a", "\u4f83\u500b", 260),
    ("hange", "\u558a\u4e2a", "\u558a\u500b", 480),
    ("hange", "\u542b\u4e2a", "\u542b\u500b", 280),
    ("hange", "\u710a\u4e2a", "\u710a\u500b", 220),
    ("jiange", "\u5efa\u4e2a", "\u5efa\u500b", 640),
    ("jiange", "\u51cf\u4e2a", "\u6e1b\u500b", 420),
    ("qiange", "\u6b20\u4e2a", "\u6b20\u500b", 380),
    ("xiange", "\u5acc\u4e2a", "\u5acc\u500b", 180),
    ("yange", "\u54bd\u4e2a", "\u56a5\u500b", 220),
    ("yange", "\u9a8c\u4e2a", "\u9a57\u500b", 380),
    ("wange", "\u5b8c\u4e2a", "\u5b8c\u500b", 180),
)


class DailyNasalGeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        payload = (ROOT / "manifests/curated_daily_supplement_phrases.tsv").read_text(
            encoding="utf-8").split(MARKER, 1)[1].split("\n\n", 1)[0]
        entries, _ = builder._parse_curated_daily_phrase_entries(payload.encode("utf-8"), 2)
        cls.regular, cls.exact = builder._partition_curated_daily_post_rank_exact_entries(entries)
        cls.maps = ({}, {})
        builder._inject_curated_daily_post_rank_exact_entries(*cls.maps, cls.exact)

    def test_explicit_positive_weights_survive_rebuild(self):
        self.assertFalse(self.regular)
        self.assertEqual(37, len(self.exact))
        for index in (0, 1):
            expected = {(py, (sc, tc)[index]): weight for py, sc, tc, weight in WORDS}
            self.assertEqual(expected, self.maps[index])
        builder._inject_curated_daily_post_rank_exact_entries(*self.maps, self.exact)
        self.assertEqual(37, len(self.maps[0]))
        self.assertEqual(37, len(self.maps[1]))

    def test_generated_entries_and_completion_priors(self):
        for index, variant in enumerate(("sc", "tc")):
            mapping = self.maps[index]
            found = {}
            with (ROOT / f"data/generated/dict_clean_{variant}.txt").open(encoding="utf-8") as stream:
                for line in stream:
                    row = line.rstrip().split("\t")
                    key = tuple(row[:2])
                    if key in mapping:
                        self.assertNotIn(key, found)
                        found[key] = row[2:]
            self.assertEqual({key: [str(weight), "no_contains"] for key, weight in mapping.items()}, found)
            with (ROOT / f"data/generated/dict_completion_prior_{variant}.txt").open(encoding="utf-8") as stream:
                priors = {}
                for line in stream:
                    row = line.rstrip().split("\t")
                    key = tuple(row[:2])
                    if key in mapping:
                        self.assertNotIn(key, priors)
                        priors[key] = row[2:]
            self.assertEqual({key: ["80", "0", "0", "0", "0", "0", "0"]
                              for key in mapping}, priors)

    def test_requested_words_visible_and_common_homophones_preserved(self):
        leaders = {
            "changge": ("\u5531\u6b4c", "\u5531\u6b4c"),
            "bange": ("\u534a\u4e2a", "\u534a\u500b"),
            "dange": ("\u803d\u6401", "\u803d\u64f1"),
            "jiange": ("\u95f4\u9694", "\u9593\u9694"),
            "yange": ("\u4e25\u683c", "\u56b4\u683c"),
            "gange": ("\u5e72\u4e2a", "\u5e79\u500b"),
            "wange": ("\u73a9\u4e2a", "\u8f13\u6b4c"),
        }
        for index, variant in enumerate(("sc", "tc")):
            rows = load_merged_dict([ROOT / f"data/generated/dict_clean_{variant}.txt",
                                    ROOT / f"data/generated/dict_unihan_{variant}.txt"])
            for py, sc, tc, _ in WORDS:
                self.assertIn((sc, tc)[index], [word for word, _ in rows[py][:9]])
            for py, words in leaders.items():
                self.assertEqual(words[index], rows[py][0][0], (variant, py))
            self.assertEqual(760, rows["gange"][0][1])

    def test_polyphonic_readings_and_traditional_forms(self):
        self.assertIn(("tange", "\u5f39\u4e2a"), self.maps[0])
        self.assertNotIn(("dange", "\u5f39\u4e2a"), self.maps[0])
        self.assertIn(("yange", "\u56a5\u500b"), self.maps[1])
        self.assertIn(("gange", "\u4e7e\u54e5"), self.maps[1])
        self.assertNotIn(("gange", "\u5e79\u54e5"), self.maps[1])


if __name__ == "__main__":
    unittest.main()
