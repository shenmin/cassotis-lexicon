"""Validate curated verb + le readings, visibility and isolated lexical weights."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from validate_regression_samples import load_merged_dict

MARKER = "# Everyday verb + le phrases and a software-work phrase, 2026-09-16."


class DailyVerbLeTests(unittest.TestCase):
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

    def test_explicit_positive_weights_survive_rebuild(self):
        self.assertFalse(self.regular)
        self.assertEqual(55, len(self.exact))
        for variant in (0, 1):
            expected = {(row[3], row[variant]): round(float(row[2]) * 1000) for row in self.rows}
            self.assertEqual(expected, self.maps[variant])
            self.assertTrue(all(0 < weight <= 700 for weight in expected.values()))
        self.assertTrue(all(row[4] == "exact_rank_no_contains" for row in self.rows))
        builder._inject_curated_daily_post_rank_exact_entries(*self.maps, self.exact)
        self.assertEqual(55, len(self.maps[0]))

    def test_generated_weights_and_priors(self):
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
            priors = {}
            with (ROOT / f"data/generated/dict_completion_prior_{variant}.txt").open(encoding="utf-8") as stream:
                for line in stream:
                    row = line.rstrip().split("\t")
                    key = tuple(row[:2])
                    if key in mapping:
                        self.assertNotIn(key, priors)
                        priors[key] = row[2:]
            self.assertEqual({key: ["80", "0", "0", "0", "0", "0", "0"] for key in mapping}, priors)

    def test_requested_words_are_present_once(self):
        for py, text in (
            ("lianle", "\u8fde\u4e86"), ("tongle", "\u901a\u4e86"),
            ("shanle", "\u95ea\u4e86"), ("huale", "\u5212\u4e86"),
            ("huale", "\u6ed1\u4e86"), ("aile", "\u7231\u4e86"),
            ("shuile", "\u6c34\u4e86"), ("feile", "\u98de\u4e86"),
            ("diaole", "\u6389\u4e86"), ("zuobanben", "\u505a\u7248\u672c"),
            ("jingyong", "\u7ecf\u7528"), ("bujingyong", "\u4e0d\u7ecf\u7528"),
            ("jingzao", "\u7ecf\u9020"), ("bujingzao", "\u4e0d\u7ecf\u9020"),
            ("bujing", "\u4e0d\u7ecf"),
            ("wodao", "\u6211\u5012"), ("wodaoshi", "\u6211\u5012\u662f"),
            ("zhewodaoshi", "\u8fd9\u6211\u5012\u662f"),
        ):
            self.assertEqual(1, sum(row[0] == text and row[3] == py for row in self.rows))
            self.assertIn((py, text), self.maps[0])

    def test_le_readings_and_traditional_forms(self):
        for py, text in self.maps[0]:
            if text.endswith("\u4e86"):
                self.assertEqual(2, len(text))
                self.assertEqual("\u4e86", text[-1])
                self.assertEqual("le", builder._runtime_parse_compact_pinyin(py)[-1])
        self.assertIn(("zuobanben", "\u505a\u7248\u672c"), self.maps[0])
        self.assertIn(("huale", "\u5283\u4e86"), self.maps[1])
        self.assertIn(("cangle", "\u85cf\u4e86"), self.maps[0])
        self.assertNotIn(("zangle", "\u85cf\u4e86"), self.maps[0])
        self.assertIn(("chuanle", "\u50b3\u4e86"), self.maps[1])
        self.assertIn(("zhewodaoshi", "\u9019\u6211\u5012\u662f"), self.maps[1])

    def test_durability_phrases(self):
        for py, text, weight in (
            ("jingyong", "\u7d93\u7528", 360),
            ("bujingyong", "\u4e0d\u7d93\u7528", 420),
            ("jingzao", "\u7d93\u9020", 260),
            ("bujingzao", "\u4e0d\u7d93\u9020", 360),
            ("bujing", "\u4e0d\u7d93", 180),
            ("jingdezhu", "\u7d93\u5f97\u4f4f", 500),
        ):
            self.assertEqual(weight, self.maps[1][(py, text)])

    def test_visibility_and_established_homophones(self):
        for index, variant in enumerate(("sc", "tc")):
            rows = load_merged_dict([ROOT / f"data/generated/dict_clean_{variant}.txt",
                                    ROOT / f"data/generated/dict_unihan_{variant}.txt"])
            for py, word in self.maps[index]:
                self.assertIn(word, [text for text, _ in rows[py][:9]])
            self.assertEqual("\u7761\u4e86", rows["shuile"][0][0])
            self.assertEqual(("\u5220\u4e86", "\u522a\u4e86")[index], rows["shanle"][0][0])
            self.assertEqual("\u82b1\u4e86", rows["huale"][0][0])
            self.assertEqual(("\u4e0d\u60ca", "\u4e0d\u9a5a")[index], rows["bujing"][0][0])
            self.assertEqual(("\u95ee\u4e86", "\u554f\u4e86")[index], rows["wenle"][0][0])
            self.assertIn("\u543b\u4e86", [text for text, _ in rows["wenle"][:9]])
            self.assertIn(("\u8585\u4e86", 280), rows["haole"])
            self.assertIn("\u8585\u4e86", [text for text, _ in rows["haole"][:9]])
            self.assertIn((("\u5367\u5012", "\u81e5\u5012")[index], 428), rows["wodao"])


if __name__ == "__main__":
    unittest.main()
