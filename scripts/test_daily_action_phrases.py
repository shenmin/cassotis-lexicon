"""Keep manual action vocabulary reproducible without inventing LM evidence."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_external_cedict as builder
from validate_regression_samples import load_merged_dict

MARKER = '# Everyday directional actions 2026-09-10.'


class DailyActionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        payload = (ROOT / 'manifests/curated_daily_supplement_phrases.tsv').read_text(
            encoding='utf-8').split(MARKER, 1)[1].split('\n\n', 1)[0]
        entries, _ = builder._parse_curated_daily_phrase_entries(payload.encode('utf-8'), 2)
        cls.regular, cls.exact = builder._partition_curated_daily_post_rank_exact_entries(entries)
        cls.maps = ({}, {})
        builder._inject_curated_daily_post_rank_exact_entries(*cls.maps, cls.exact)

    def test_all_four_phrases_use_explicit_positive_ranks(self):
        self.assertFalse(self.regular)
        self.assertEqual(4, len(self.exact))
        for mapping in self.maps:
            self.assertEqual(4, len(mapping))
            self.assertTrue(all(0 < weight <= 660 for weight in mapping.values()))

    def test_generated_artifacts_match_production_parser(self):
        for variant, mapping in zip(('sc', 'tc'), self.maps):
            found = {}
            for line in (ROOT / f'data/generated/dict_clean_{variant}.txt').read_text(
                    encoding='utf-8').splitlines():
                parts = line.split('\t')
                key = tuple(parts[:2])
                if key in mapping:
                    self.assertNotIn(key, found)
                    found[key] = parts[2:]
            self.assertEqual({key: [str(w), 'no_contains'] for key, w in mapping.items()}, found)

    def test_seated_homophones_remain_first(self):
        for variant in ('sc', 'tc'):
            rows = load_merged_dict([ROOT / f'data/generated/dict_clean_{variant}.txt',
                                    ROOT / f'data/generated/dict_unihan_{variant}.txt'])
            self.assertEqual('\u5750\u4e0a', rows['zuoshang'][0][0])
            self.assertEqual('\u5750\u4e0b', rows['zuoxia'][0][0])

    def test_traditional_spelling_and_idempotent_injection(self):
        sc, tc = (dict(mapping) for mapping in self.maps)
        self.assertIn(('guashang', '\u639b\u4e0a'), tc)
        self.assertIn(('chengshang', '\u6490\u4e0a'), tc)
        builder._inject_curated_daily_post_rank_exact_entries(sc, tc, self.exact)
        self.assertEqual(self.maps, (sc, tc))


class DailyJiahaoTests(unittest.TestCase):
    def test_manifest_and_generated_rows_preserve_existing_homophone(self):
        marker = '# Everyday action completion 2026-09-12.'
        payload = (ROOT / 'manifests/curated_daily_supplement_phrases.tsv').read_text(
            encoding='utf-8').split(marker, 1)[1].split('\n\n', 1)[0]
        entries, _ = builder._parse_curated_daily_phrase_entries(payload.encode('utf-8'), 2)
        regular, exact = builder._partition_curated_daily_post_rank_exact_entries(entries)
        self.assertFalse(regular)
        self.assertEqual(1, len(exact))
        maps = ({}, {})
        builder._inject_curated_daily_post_rank_exact_entries(*maps, exact)
        word = '\u52a0\u597d'
        self.assertEqual(({('jiahao', word): 360}, {('jiahao', word): 360}), maps)
        builder._inject_curated_daily_post_rank_exact_entries(*maps, exact)
        for variant, plus in (('sc', '\u52a0\u53f7'), ('tc', '\u52a0\u865f')):
            with self.subTest(variant=variant):
                path = ROOT / f'data/generated/dict_clean_{variant}.txt'
                generated = path.read_text(encoding='utf-8').splitlines()
                self.assertEqual(1, generated.count(f'jiahao\t{word}\t360\tno_contains'))
                rows = load_merged_dict([path, ROOT / f'data/generated/dict_unihan_{variant}.txt'])
                self.assertEqual([(plus, 390), (word, 360)], rows['jiahao'])


class DailyAccidentalActionTests(unittest.TestCase):
    def test_reproducible_positive_exact_entries_without_synthetic_evidence(self):
        marker = '# Everyday accidental actions 2026-09-12.'
        payload = (ROOT / 'manifests/curated_daily_supplement_phrases.tsv').read_text(
            encoding='utf-8').split(marker, 1)[1].split('\n\n', 1)[0]
        entries, _ = builder._parse_curated_daily_phrase_entries(payload.encode('utf-8'), 2)
        regular, exact = builder._partition_curated_daily_post_rank_exact_entries(entries)
        self.assertFalse(regular)
        self.assertEqual(9, len(exact))
        maps = ({}, {})
        builder._inject_curated_daily_post_rank_exact_entries(*maps, exact)
        before = tuple(dict(mapping) for mapping in maps)
        builder._inject_curated_daily_post_rank_exact_entries(*maps, exact)
        self.assertEqual(before, maps)
        expected = [
            ('wuhuan', '\u6362', '\u63db', 240),
            ('wujiang', '\u5c06', '\u5c07', 480),
            ('wuba', '\u628a', '\u628a', 520),
            ('wuren', '\u8ba4', '\u8a8d', 600),
            ('wuzuo', '\u4f5c', '\u4f5c', 460),
            ('wuzuo', '\u505a', '\u505a', 260),
            ('wuru', '\u5165', '\u5165', 640),
            ('wuchi', '\u5403', '\u5403', 360),
            ('wuhe', '\u559d', '\u559d', 320),
        ]
        for index, variant in enumerate(('sc', 'tc')):
            expected_map = {(py, ('\u8bef' if index == 0 else '\u8aa4') + (sc if index == 0 else tc)): weight
                            for py, sc, tc, weight in expected}
            self.assertEqual(expected_map, maps[index])
            found = {}
            with (ROOT / f'data/generated/dict_clean_{variant}.txt').open(encoding='utf-8') as stream:
                for line in stream:
                    fields = line.rstrip('\r\n').split('\t')
                    key = tuple(fields[:2])
                    if key in expected_map:
                        self.assertNotIn(key, found)
                        found[key] = fields[2:]
            self.assertEqual({key: [str(w), 'no_contains'] for key, w in expected_map.items()}, found)


class DailyMistakenActionTests(unittest.TestCase):
    def test_cuo_entries_are_reproducible_and_keep_uncommon_usage_lower(self):
        marker = '# Everyday mistaken actions 2026-09-12.'
        payload = (ROOT / 'manifests/curated_daily_supplement_phrases.tsv').read_text(
            encoding='utf-8').split(marker, 1)[1].split('\n\n', 1)[0]
        entries, _ = builder._parse_curated_daily_phrase_entries(payload.encode('utf-8'), 2)
        regular, exact = builder._partition_curated_daily_post_rank_exact_entries(entries)
        self.assertFalse(regular)
        self.assertEqual(4, len(exact))
        maps = ({}, {})
        builder._inject_curated_daily_post_rank_exact_entries(*maps, exact)
        before = tuple(dict(mapping) for mapping in maps)
        builder._inject_curated_daily_post_rank_exact_entries(*maps, exact)
        self.assertEqual(before, maps)
        expected = [
            ('cuoba', '\u9519\u628a', '\u932f\u628a', 520),
            ('cuojiang', '\u9519\u5c06', '\u932f\u5c07', 460),
            ('cuoren', '\u9519\u8ba4', '\u932f\u8a8d', 560),
            ('cuoru', '\u9519\u5165', '\u932f\u5165', 320),
        ]
        for index, variant in enumerate(('sc', 'tc')):
            expected_map = {(py, sc if index == 0 else tc): weight
                            for py, sc, tc, weight in expected}
            self.assertEqual(expected_map, maps[index])
            found = {}
            with (ROOT / f'data/generated/dict_clean_{variant}.txt').open(encoding='utf-8') as stream:
                for line in stream:
                    fields = line.rstrip('\r\n').split('\t')
                    key = tuple(fields[:2])
                    if key in expected_map:
                        self.assertNotIn(key, found)
                        found[key] = fields[2:]
            self.assertEqual({key: [str(w), 'no_contains'] for key, w in expected_map.items()}, found)


if __name__ == '__main__':
    unittest.main()
