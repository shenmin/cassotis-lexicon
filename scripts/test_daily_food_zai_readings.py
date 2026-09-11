"""Check food vocabulary, secondary readings and corrected completion keys."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_external_cedict as builder
from validate_regression_samples import load_merged_dict

MARKER = '# Everyday food, clothing and proofreading 2026-09-11.'
ZAI = '\u4ed4'


class DailyFoodReadingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        payload = (ROOT / 'manifests/curated_daily_supplement_phrases.tsv').read_text(
            encoding='utf-8').split(MARKER, 1)[1].split('\n\n', 1)[0]
        cls.entries, _ = builder._parse_curated_daily_phrase_entries(payload.encode('utf-8'), 2)
        cls.regular, cls.exact = builder._partition_curated_daily_post_rank_exact_entries(cls.entries)
        cls.maps = ({}, {})
        builder._inject_curated_daily_post_rank_exact_entries(*cls.maps, cls.exact)

    def test_all_phrases_have_explicit_positive_daily_ranks(self):
        self.assertFalse(self.regular)
        self.assertEqual(15, len(self.exact))
        for mapping in self.maps:
            self.assertEqual(15, len(mapping))
            self.assertTrue(all(0 < value <= 700 for value in mapping.values()))

    def test_generated_rows_match_manifest_without_inventing_lm_evidence(self):
        for variant, expected in zip(('sc', 'tc'), self.maps):
            actual = {}
            for line in (ROOT / f'data/generated/dict_clean_{variant}.txt').read_text(
                    encoding='utf-8').splitlines():
                parts = line.split('\t')
                key = tuple(parts[:2])
                if key in expected:
                    self.assertNotIn(key, actual)
                    actual[key] = parts[2:]
            self.assertEqual({key: [str(w), 'no_contains'] for key, w in expected.items()}, actual)

    def test_secondary_reading_does_not_replace_or_raise_primary(self):
        overrides = builder._load_pinyin_overrides(ROOT / 'manifests/pinyin_overrides.tsv')
        self.assertEqual('zai', overrides[ZAI])
        original = {('zi', ZAI): 414, ('zai', '\u5728'): 853}
        result, _ = builder._apply_word_pinyin_overrides(original, overrides, 'test')
        self.assertEqual({**original, ('zai', ZAI): 280}, result)
        repeated, _ = builder._apply_word_pinyin_overrides(result, overrides, 'test')
        self.assertEqual(result, repeated)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'dict.txt'
            builder._write_dict(path, result, unihan_map={ZAI: 'zi'},
                                unihan_readings_map={ZAI: {'zi'}})
            self.assertIn(f'zai\t{ZAI}\t280\n', path.read_text(encoding='utf-8'))

    def test_both_scripts_keep_zai_on_first_page_and_common_homophones_ahead(self):
        for variant, canyon in (('sc', '\u5ce1\u8c37'), ('tc', '\u5cfd\u8c37')):
            rows = load_merged_dict([ROOT / f'data/generated/dict_clean_{variant}.txt',
                                    ROOT / f'data/generated/dict_unihan_{variant}.txt'])
            self.assertIn((ZAI, 280), rows['zai'][:9])
            self.assertIn((ZAI, 414), rows['zi'])
            self.assertEqual('\u5728', rows['zai'][0][0])
            self.assertEqual('\u518d', rows['zai'][1][0])
            self.assertEqual(canyon, rows['xiagu'][0][0])
            self.assertEqual(['\u4e00\u9762', '\u4ee5\u514d'],
                             [text for text, _ in rows['yimian'][:2]])

    def test_explicit_compound_readings_and_spoken_aliases(self):
        overrides = builder._build_curated_daily_explicit_pinyin_override_map(self.entries)
        for text in ('\u9732\u80a9', '\u9732\u817f'):
            self.assertNotIn(text, overrides)
        for text in ('\u5ba1\u6821', '\u5be9\u6821'):
            self.assertEqual('shenjiao', overrides[text])
        for variant, rice in (('sc', '\u7172\u4ed4\u996d'), ('tc', '\u7172\u4ed4\u98ef')):
            rows = load_merged_dict([ROOT / f'data/generated/dict_clean_{variant}.txt'])
            self.assertIn((rice, 700), rows['baozaifan'])
            self.assertNotIn(rice, [text for text, _ in rows.get('baozifan', [])])
            remapped, _ = builder._apply_explicit_term_pinyin_overrides(
                {('baozifan', rice): 10}, overrides, 'test')
            self.assertEqual({('baozaifan', rice): 10}, remapped)

    def test_corrected_completion_does_not_reintroduce_old_reading(self):
        for variant, rice in (('sc', '\u7172\u4ed4\u996d'), ('tc', '\u7172\u4ed4\u98ef')):
            prior = [line.split('\t') for line in
                     (ROOT / f'data/generated/dict_completion_prior_{variant}.txt').read_text(
                         encoding='utf-8').splitlines() if f'\t{rice}\t' in line]
            lookup = [line.split('\t') for line in
                      (ROOT / f'data/generated/dict_completion_lookup_{variant}.txt').read_text(
                          encoding='utf-8').splitlines() if f'\t{rice}\t' in line]
            self.assertEqual(['baozaifan'], [row[0] for row in prior])
            self.assertEqual([['baozai', 'baozaifan', rice]], [row[:3] for row in lookup])
            self.assertEqual('700', lookup[0][3])


if __name__ == '__main__':
    unittest.main()
