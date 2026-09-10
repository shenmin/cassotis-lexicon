"""Check the meal/shopping supplement against the production manifest parser."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_external_cedict as builder
from validate_regression_samples import load_merged_dict

MARKER = '# Everyday meals, shopping and conversational fragments 2026-09-10.'


class DailyFoodTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        payload = (ROOT / 'manifests/curated_daily_supplement_phrases.tsv').read_text(
            encoding='utf-8').split(MARKER, 1)[1].split('\n\n', 1)[0]
        cls.entries, _ = builder._parse_curated_daily_phrase_entries(payload.encode('utf-8'), 2)
        cls.regular, cls.exact = builder._partition_curated_daily_post_rank_exact_entries(cls.entries)
        cls.maps = ({}, {})
        builder._inject_curated_daily_post_rank_exact_entries(*cls.maps, cls.exact)

    def test_all_requested_phrases_use_explicit_exact_ranks(self):
        self.assertFalse(self.regular)
        self.assertEqual(16, len(self.exact))
        for mapping in self.maps:
            self.assertEqual(16, len(mapping))
            self.assertTrue(all(0 < w <= 760 for w in mapping.values()))

    def test_generated_rows_match_manifest_without_substring_evidence(self):
        for variant, mapping in zip(('sc', 'tc'), self.maps):
            rows = {}
            for line in (ROOT / f'data/generated/dict_clean_{variant}.txt').read_text(
                    encoding='utf-8').splitlines():
                parts = line.split('\t')
                key = tuple(parts[:2])
                if key in mapping:
                    self.assertNotIn(key, rows)
                    rows[key] = parts[2:]
            self.assertEqual({key: [str(w), 'no_contains'] for key, w in mapping.items()}, rows)

    def test_food_and_address_forms_are_correct_in_traditional(self):
        tc = self.maps[1]
        for key in (('maimian', '\u8cb7\u9eb5'), ('tangtuan', '\u6e6f\u7cf0'),
                    ('tangyuan', '\u6e6f\u5713'), ('aye', '\u963f\u723a')):
            self.assertIn(key, tc)
        self.assertNotIn(('maimian', '\u8cb7\u9762'), tc)

    def test_unambiguous_everyday_words_and_lower_frequency_homophones(self):
        for variant, chars in (('sc', ('\u70b9\u4e00\u4e0b', '\u70b9\u70b9', '\u58f0\u8c03')),
                               ('tc', ('\u9ede\u4e00\u4e0b', '\u9ede\u9ede', '\u8072\u8abf'))):
            rows = load_merged_dict([ROOT / f'data/generated/dict_clean_{variant}.txt',
                                    ROOT / f'data/generated/dict_unihan_{variant}.txt'])
            for query, expected in zip(('dianyixia', 'diandian', 'shengdiao'), chars):
                self.assertEqual(expected, rows[query][0][0])
            expected = '\u6c64\u5706' if variant == 'sc' else '\u6e6f\u5713'
            self.assertEqual(expected, rows['tangyuan'][0][0])

    def test_reapplying_curated_ranks_is_idempotent(self):
        sc, tc = (dict(mapping) for mapping in self.maps)
        builder._inject_curated_daily_post_rank_exact_entries(sc, tc, self.exact)
        self.assertEqual(self.maps, (sc, tc))


if __name__ == '__main__':
    unittest.main()
