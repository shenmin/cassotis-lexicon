"""Validate everyday UI phrases, readings and conservative homophone ranks."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_external_cedict as builder
from validate_regression_samples import load_merged_dict

MARKER = '# Everyday actions, UI terms and forms of address, 2026-09-22.'


class DailyUiPhraseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        payload = (ROOT / 'manifests/curated_daily_supplement_phrases.tsv').read_text(
            encoding='utf-8').split(MARKER, 1)[1].split('\n\n', 1)[0].encode('utf-8')
        entries, _ = builder._parse_curated_daily_phrase_entries(payload, 2)
        cls.regular, cls.exact = builder._partition_curated_daily_post_rank_exact_entries(entries)
        cls.maps = ({}, {})
        builder._inject_curated_daily_post_rank_exact_entries(*cls.maps, cls.exact)
        cls.exclusions = builder._parse_curated_contains_popularity_exclusions(payload)

    def test_explicit_weights_are_positive_bounded_and_idempotent(self):
        self.assertFalse(self.regular)
        self.assertEqual(61, len(self.exact))
        repeated = tuple(dict(mapping) for mapping in self.maps)
        builder._inject_curated_daily_post_rank_exact_entries(*repeated, self.exact)
        self.assertEqual(self.maps, repeated)
        for mapping, exclusions in zip(self.maps, self.exclusions):
            self.assertEqual(61, len(mapping))
            self.assertTrue(all(0 < weight <= 800 for weight in mapping.values()))
            self.assertEqual({'fade', 'chuxianshi'},
                             {py for (py, _), weight in mapping.items() if weight == 1})
            self.assertEqual({word for _, word in mapping}, exclusions)

    def test_contextual_readings_and_correct_cabinet_spelling(self):
        for variant, mapping in zip(('sc', 'tc'), self.maps):
            expected = {
                '\u5f53\u524d\u884c' if variant == 'sc' else '\u7576\u524d\u884c': 'dangqianhang',
                '\u5f97\u9760\u6211': 'deikaowo',
                '\u8fd8\u5f97' if variant == 'sc' else '\u9084\u5f97': 'haidei',
                '\u4e94\u6597\u6a71' if variant == 'sc' else '\u4e94\u6597\u6ae5': 'wudouchu',
            }
            for word, py in expected.items():
                self.assertEqual([py], [key for key, text in mapping if text == word])
            self.assertFalse(any(text == '\u4e94\u6597\u53a8' for _, text in mapping))
            saving = {py for py, word in mapping if word.startswith('\u7701')}
            self.assertEqual({'shengdian', 'shengshui', 'shengqi', 'shengneng', 'shengren', 'shengsheng'}, saving)

    def test_generated_dictionary_rows_match_manifest_exactly(self):
        for variant, expected in zip(('sc', 'tc'), self.maps):
            found = {}
            with (ROOT / f'data/generated/dict_clean_{variant}.txt').open(encoding='utf-8') as stream:
                for line in stream:
                    row = line.rstrip().split('\t')
                    key = tuple(row[:2])
                    if key in expected:
                        self.assertNotIn(key, found)
                        found[key] = row[2:]
            self.assertEqual({key: [str(weight), 'no_contains'] for key, weight in expected.items()}, found)

    def test_familiar_homophones_are_not_displaced_by_names(self):
        for variant in ('sc', 'tc'):
            rows = load_merged_dict([ROOT / f'data/generated/dict_clean_{variant}.txt'])
            pairs = (
                ('wangjie', '\u738b\u6770' if variant == 'sc' else '\u738b\u5091', '\u738b\u59d0'),
                ('wangjie', '\u5f80\u5c4a' if variant == 'sc' else '\u5f80\u5c46', '\u738b\u59d0'),
                ('lijie', '\u7406\u89e3', '\u674e\u59d0'),
                ('lijie', '\u793c\u8282' if variant == 'sc' else '\u79ae\u7bc0', '\u674e\u59d0'),
                ('wujie', '\u65e0\u89e3' if variant == 'sc' else '\u7121\u89e3', '\u5434\u59d0' if variant == 'sc' else '\u5433\u59d0'),
                ('zhengjie', '\u6574\u6d01' if variant == 'sc' else '\u6574\u6f54', '\u90d1\u59d0' if variant == 'sc' else '\u912d\u59d0'),
                ('zhizhi', '\u5236\u6b62', '\u6cbb\u6cbb'),
                ('shengqi', '\u751f\u6c14' if variant == 'sc' else '\u751f\u6c23',
                 '\u7701\u6c14' if variant == 'sc' else '\u7701\u6c23'),
                ('shengren', '\u80dc\u4efb' if variant == 'sc' else '\u52dd\u4efb', '\u7701\u4eba'),
            )
            for py, common, added in pairs:
                words = [word for word, _ in rows[py]]
                self.assertLess(words.index(common), words.index(added), (variant, py, common, added))

    def test_partial_particle_phrases_do_not_dominate_complete_expressions(self):
        for variant, mapping in zip(('sc', 'tc'), self.maps):
            self.assertTrue(all(weight <= 120 for (py, _), weight in mapping.items() if py == 'shude'))
            rows = load_merged_dict([ROOT / f'data/generated/dict_clean_{variant}.txt'])
            common = '\u51fa\u73b0\u5f02\u5e38' if variant == 'sc' else '\u51fa\u73fe\u7570\u5e38'
            added = '\u51fa\u73b0\u65f6' if variant == 'sc' else '\u51fa\u73fe\u6642'
            common_weight = dict(rows['chuxianyichang'])[common]
            self.assertGreater(common_weight, mapping[('chuxianshi', added)])

    def test_no_fabricated_completion_popularity(self):
        for variant, expected in zip(('sc', 'tc'), self.maps):
            prior = {}
            with (ROOT / f'data/generated/dict_completion_prior_{variant}.txt').open(encoding='utf-8') as stream:
                for line in stream:
                    row = line.rstrip().split('\t')
                    if tuple(row[:2]) in expected:
                        self.assertNotIn(tuple(row[:2]), prior)
                        prior[tuple(row[:2])] = tuple(map(int, row[2:]))
            self.assertEqual({key: (80, 0, 0, 0, 0, 0, 0) for key in expected}, prior)

    def test_new_words_are_available_to_completion_lookup(self):
        for variant, expected in zip(('sc', 'tc'), self.maps):
            targets = {key for key in expected if key[0] in (
                'wudouchu', 'dangqianhang', 'xiangxiajiantou', 'xuanzhongxiang', 'fasongguo')}
            found = set()
            with (ROOT / f'data/generated/dict_completion_lookup_{variant}.txt').open(
                    encoding='utf-8') as stream:
                for line in stream:
                    row = line.rstrip().split('\t')
                    key = tuple(row[1:3])
                    if key in targets:
                        self.assertTrue(key[0].startswith(row[0]))
                        self.assertLess(len(row[0]), len(key[0]))
                        self.assertEqual(expected[key], int(row[3]))
                        found.add(key)
            self.assertEqual(targets, found)


if __name__ == '__main__':
    unittest.main()
