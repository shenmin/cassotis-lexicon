"""Keep both carry-verb readings usable without raising unrelated homophones."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_external_cedict as builder
from validate_regression_samples import load_merged_dict

MARKER = '# Carrying phrases and literary yi snippets, 2026-09-21.'
LIN = '\u62ce'


class DailyLinYiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = (ROOT / 'manifests/curated_daily_supplement_phrases.tsv').read_text(
            encoding='utf-8').split(MARKER, 1)[1].split('\n\n', 1)[0].encode('utf-8')
        entries, _ = builder._parse_curated_daily_phrase_entries(cls.payload, 2)
        cls.entries = entries
        cls.regular, cls.exact = builder._partition_curated_daily_post_rank_exact_entries(entries)
        cls.maps = ({}, {})
        builder._inject_curated_daily_post_rank_exact_entries(*cls.maps, cls.exact)

    def test_explicit_lexical_weights_and_readings_are_idempotent(self):
        self.assertFalse(self.regular)
        self.assertEqual(28, len(self.exact))
        repeated = tuple(dict(m) for m in self.maps)
        builder._inject_curated_daily_post_rank_exact_entries(*repeated, self.exact)
        self.assertEqual(self.maps, repeated)
        for mapping in self.maps:
            self.assertTrue(all(0 < weight <= 520 for weight in mapping.values()))
            self.assertEqual(14, sum(text.startswith('\u4ea6') for _, text in mapping))
            for tail in ('deqing', 'qing', 'dongxi', 'zhongwu', 'qilai', 'budong', 'zou'):
                left = [(text, weight) for (py, text), weight in mapping.items() if py == 'lin' + tail]
                right = [(text, weight) for (py, text), weight in mapping.items() if py == 'ling' + tail]
                self.assertEqual(1, len(left))
                self.assertEqual(left, right)
        overrides = builder._build_curated_daily_explicit_pinyin_override_map(self.entries)
        self.assertFalse(any(text.startswith(LIN) for text in overrides))

    def test_secondary_reading_preserves_primary_and_other_characters(self):
        overrides = builder._load_pinyin_overrides(ROOT / 'manifests/pinyin_overrides.tsv')
        self.assertEqual('ling', overrides[LIN])
        original = {('lin', LIN): 74, ('lin', '\u9cde'): 194,
                    ('ling', '\u9f84'): 317, ('ling', '\u9886'): 600}
        result, _ = builder._apply_word_pinyin_overrides(dict(original), {LIN: 'ling'}, 'test')
        builder._enforce_single_char_relative_order_overrides(result, 'test')
        self.assertEqual(210, result[('lin', LIN)])
        self.assertEqual(333, result[('ling', LIN)])
        self.assertEqual({k: v for k, v in original.items() if k[1] != LIN},
                         {k: v for k, v in result.items() if k[1] != LIN})
        repeated, _ = builder._apply_word_pinyin_overrides(dict(result), {LIN: 'ling'}, 'test')
        builder._enforce_single_char_relative_order_overrides(repeated, 'test')
        self.assertEqual(result, repeated)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'dict.txt'
            builder._write_dict(path, result, unihan_map={LIN: 'lin'},
                                unihan_readings_map={LIN: {'lin'}})
            self.assertIn(f'ling\t{LIN}\t333\n', path.read_text(encoding='utf-8'))

    def test_both_script_outputs_match_the_manifest(self):
        excluded = builder._parse_curated_contains_popularity_exclusions(self.payload)
        for variant, expected, no_contains in zip(('sc', 'tc'), self.maps, excluded):
            found = {}
            with (ROOT / f'data/generated/dict_clean_{variant}.txt').open(encoding='utf-8') as stream:
                for line in stream:
                    row = line.rstrip().split('\t')
                    key = tuple(row[:2])
                    if key in expected:
                        self.assertNotIn(key, found)
                        found[key] = row[2:]
            self.assertEqual({k: [str(v)] + (['no_contains'] if k[1] in no_contains else [])
                              for k, v in expected.items()}, found)

    def test_single_char_is_on_first_page_and_common_homophones_stay_ahead(self):
        for variant in ('sc', 'tc'):
            rows = load_merged_dict([ROOT / f'data/generated/dict_clean_{variant}.txt',
                                    ROOT / f'data/generated/dict_unihan_{variant}.txt'])
            for py in ('lin', 'ling'):
                self.assertIn(LIN, [text for text, _ in rows[py][:9]])
            for py, common, added in (
                ('yiran', '\u4f9d\u7136', '\u4ea6\u7136'),
                ('yishi', '\u610f\u8bc6' if variant == 'sc' else '\u610f\u8b58', '\u4ea6\u662f'),
                ('yiru', '\u4e00\u5982', '\u4ea6\u5982'),
                ('yixiang', '\u610f\u5411', '\u4ea6\u60f3'),
                ('yikuai', '\u4e00\u5757' if variant == 'sc' else '\u4e00\u584a', '\u4ea6\u5feb'),
            ):
                words = [text for text, _ in rows[py]]
                self.assertLess(words.index(common), words.index(added))

    def test_phrase_readings_share_only_their_own_lexical_prior(self):
        for variant, expected in zip(('sc', 'tc'), self.maps):
            rows = load_merged_dict([ROOT / f'data/generated/dict_clean_{variant}.txt'])
            prior = {}
            with (ROOT / f'data/generated/dict_completion_prior_{variant}.txt').open(encoding='utf-8') as stream:
                for line in stream:
                    row = line.rstrip().split('\t')
                    prior[tuple(row[:2])] = tuple(map(int, row[2:]))
            for (py, text), weight in expected.items():
                if py.startswith('ling'):
                    original_py = 'lin' + py[4:]
                    self.assertIn((text, weight), rows[original_py])
                    self.assertEqual(prior[(original_py, text)], prior[(py, text)])
                else:
                    self.assertEqual((80, 0, 0, 0, 0, 0, 0), prior[(py, text)])
            self.assertNotIn(LIN + ('\u7740' if variant == 'sc' else '\u8457'),
                             [text for text, _ in rows.get('lingzhe', [])])
            if variant == 'sc':
                self.assertEqual('\u9886\u7740', rows['lingzhe'][0][0])


if __name__ == '__main__':
    unittest.main()
