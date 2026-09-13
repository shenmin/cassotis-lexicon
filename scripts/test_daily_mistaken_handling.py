"""Regression coverage for calibrated daily handling/action phrases."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from validate_regression_samples import load_merged_dict

MARKER = "# Everyday mistaken handling 2026-09-13."
EXPECTED = [
    ('chaban', '\u63d2\u677f', '\u63d2\u677f', 700),
    ('wufang', '\u8bef\u653e', '\u8aa4\u653e', 220),
    ('cuofang', '\u9519\u653e', '\u932f\u653e', 480),
    ('wuna', '\u8bef\u62ff', '\u8aa4\u62ff', 460),
    ('cuona', '\u9519\u62ff', '\u932f\u62ff', 540),
    ('cuona', '\u9519\u54ea', '\u932f\u54ea', 220),
    ('wuqu', '\u8bef\u53d6', '\u8aa4\u53d6', 340),
    ('cuoqu', '\u9519\u53d6', '\u932f\u53d6', 400),
    ('wutian', '\u8bef\u586b', '\u8aa4\u586b', 400),
    ('cuotian', '\u9519\u586b', '\u932f\u586b', 500),
    ('cuoxie', '\u9519\u5199', '\u932f\u5beb', 560),
    ('wupeng', '\u8bef\u78b0', '\u8aa4\u78b0', 440),
    ('cuopeng', '\u9519\u78b0', '\u932f\u78b0', 180),
    ('wuzhuang', '\u8bef\u88c5', '\u8aa4\u88dd', 320),
    ('cuozhuang', '\u9519\u88c5', '\u932f\u88dd', 420),
    ('wuxiang', '\u8bef\u60f3', '\u8aa4\u60f3', 140),
    ('cuoxiang', '\u9519\u60f3', '\u932f\u60f3', 160),
    ('wuhui', '\u8bef\u56de', '\u8aa4\u56de', 220),
    ('cuohui', '\u9519\u56de', '\u932f\u56de', 360),
    ('wufa', '\u8bef\u53d1', '\u8aa4\u767c', 1),
    ('cuofa', '\u9519\u53d1', '\u932f\u767c', 600),
    ('wukai', '\u8bef\u5f00', '\u8aa4\u958b', 360),
    ('wuguan', '\u8bef\u5173', '\u8aa4\u95dc', 320),
    ('cuoguan', '\u9519\u5173', '\u932f\u95dc', 360),
    ('wuda', '\u8bef\u6253', '\u8aa4\u6253', 380),
    ('cuoda', '\u9519\u6253', '\u932f\u6253', 460),
    ('wuxi', '\u8bef\u6d17', '\u8aa4\u6d17', 180),
    ('wuxi', '\u8bef\u5438', '\u8aa4\u5438', 260),
    ('cuoxi', '\u9519\u6d17', '\u932f\u6d17', 280),
]


class DailyMistakenHandlingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        payload = (ROOT / "manifests/curated_daily_supplement_phrases.tsv").read_text(
            encoding="utf-8").split(MARKER, 1)[1].split("\n\n", 1)[0]
        entries, _ = builder._parse_curated_daily_phrase_entries(payload.encode("utf-8"), 2)
        cls.regular, cls.exact = builder._partition_curated_daily_post_rank_exact_entries(entries)
        cls.maps = ({}, {})
        builder._inject_curated_daily_post_rank_exact_entries(*cls.maps, cls.exact)
        cls.merged = {
            variant: load_merged_dict([ROOT / f"data/generated/dict_clean_{variant}.txt",
                                      ROOT / f"data/generated/dict_unihan_{variant}.txt"])
            for variant in ("sc", "tc")
        }

    def test_explicit_positive_ranks_and_traditional_spellings(self):
        self.assertFalse(self.regular)
        self.assertEqual(29, len(self.exact))
        for index in (0, 1):
            self.assertEqual({(py, sc if index == 0 else tc): weight
                              for py, sc, tc, weight in EXPECTED}, self.maps[index])
            self.assertTrue(all(0 < value <= 700 for value in self.maps[index].values()))
            self.assertEqual(['wufa'], [py for (py, _), value in self.maps[index].items() if value == 1])

    def test_injection_is_idempotent(self):
        before = tuple(dict(mapping) for mapping in self.maps)
        builder._inject_curated_daily_post_rank_exact_entries(*self.maps, self.exact)
        self.assertEqual(before, self.maps)

    def test_generated_rows_match_builder_without_substring_popularity(self):
        for variant, mapping in zip(("sc", "tc"), self.maps):
            found = {}
            with (ROOT / f"data/generated/dict_clean_{variant}.txt").open(encoding="utf-8") as stream:
                for line in stream:
                    fields = line.rstrip("\r\n").split("\t")
                    key = tuple(fields[:2])
                    if key in mapping:
                        self.assertNotIn(key, found)
                        found[key] = fields[2:]
            self.assertEqual({key: [str(weight), "no_contains"] for key, weight in mapping.items()}, found)

    def test_common_homophones_stay_ahead(self):
        protected = [
            ("chaban", '\u67e5\u529e', '\u67e5\u8fa6', "chaban", '\u63d2\u677f', '\u63d2\u677f'),
            ("wufa", '\u65e0\u6cd5', '\u7121\u6cd5', "wufa", '\u8bef\u53d1', '\u8aa4\u767c'),
            ("wuhui", '\u8bef\u4f1a', '\u8aa4\u6703', "wuhui", '\u8bef\u56de', '\u8aa4\u56de'),
            ("wufang", '\u65e0\u59a8', '\u7121\u59a8', "wufang", '\u8bef\u653e', '\u8aa4\u653e'),
            ("wuqu", '\u8bef\u533a', '\u8aa4\u5340', "wuqu", '\u8bef\u53d6', '\u8aa4\u53d6'),
            ("wutian", '\u4e94\u5929', '\u4e94\u5929', "wutian", '\u8bef\u586b', '\u8aa4\u586b'),
            ("wuzhuang", '\u6b66\u88c5', '\u6b66\u88dd', "wuzhuang", '\u8bef\u88c5', '\u8aa4\u88dd'),
            ("wuguan", '\u65e0\u5173', '\u7121\u95dc', "wuguan", '\u8bef\u5173', '\u8aa4\u95dc'),
            ("wuda", '\u6b66\u6253', '\u6b66\u6253', "wuda", '\u8bef\u6253', '\u8aa4\u6253'),
            ("wuxi", '\u65e0\u606f', '\u7121\u606f', "wuxi", '\u8bef\u5438', '\u8aa4\u5438'),
            ("cuoxi", '\u6413\u6d17', '\u6413\u6d17', "cuoxi", '\u9519\u6d17', '\u932f\u6d17'),
        ]
        for index, variant in enumerate(("sc", "tc")):
            rows = self.merged[variant]
            for py, sc, tc, other_py, other_sc, other_tc in protected:
                left, right = (sc, other_sc) if index == 0 else (tc, other_tc)
                with self.subTest(variant=variant, preferred=left, phrase=right):
                    self.assertGreater(dict(rows[py])[left], dict(rows[other_py])[right])

    def test_rare_fragments_are_lower_and_all_entries_remain_visible(self):
        for index, variant in enumerate(("sc", "tc")):
            rows = self.merged[variant]
            cuona = dict(rows["cuona"])
            preferred, rare = ('\u9519\u62ff', '\u9519\u54ea') if index == 0 else ('\u932f\u62ff', '\u932f\u54ea')
            self.assertGreater(cuona[preferred], cuona[rare])
            for py, sc, tc, weight in EXPECTED:
                text = sc if index == 0 else tc
                self.assertIn((text, weight), rows[py][:9])

    def test_inability_keeps_a_clear_margin_over_accidental_sending(self):
        for variant, common, added in (('sc', '\u65e0\u6cd5', '\u8bef\u53d1'),
                                       ('tc', '\u7121\u6cd5', '\u8aa4\u767c')):
            weights = dict(self.merged[variant]['wufa'])
            self.assertGreaterEqual(weights[common], 2 * weights[added])


if __name__ == "__main__":
    unittest.main()
