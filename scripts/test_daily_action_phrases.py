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


if __name__ == '__main__':
    unittest.main()
