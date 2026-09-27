"""Audited additive na/nei/nuo readings and everyday phrase regressions."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_external_cedict as builder
from validate_regression_samples import load_merged_dict

NA = '\u90a3'
ROWS = (
    ('laiyitang', '\u6765\u4e00\u8d9f', '\u4f86\u4e00\u8d9f', 520),
    ('haizao', '\u8fd8\u65e9', '\u9084\u65e9', 620),
    ('nahaizao', '\u90a3\u8fd8\u65e9', '\u90a3\u9084\u65e9', 420),
    ('zouyitang', '\u8d70\u4e00\u8d9f', '\u8d70\u4e00\u8d9f', 520),
    ('dahu', '\u6253\u547c', '\u6253\u547c', 420),
    ('najian', '\u90a3\u95f4', '\u90a3\u9593', 0),
    ('haiyoude', '\u8fd8\u6709\u5f97', '\u9084\u6709\u5f97', 320),
    ('haiyoudewan', '\u8fd8\u6709\u5f97\u73a9', '\u9084\u6709\u5f97\u73a9', 360),
    ('nuoqin', '\u90a3\u7434', '\u90a3\u7434', 120),
)


class DailyNaReadingTests(unittest.TestCase):
    def test_explicit_zero_rank_is_not_promoted_on_rebuild(self):
        for mode in ('exact_rank', 'exact_rank_no_contains', 'exact_zero'):
            payload = f'\u90a3\u95f4\t\u90a3\u9593\t0.000\tnajian\t{mode}\n'
            entries, _ = builder._parse_curated_daily_phrase_entries(payload.encode('utf-8'), 2)
            regular, exact = builder._partition_curated_daily_post_rank_exact_entries(entries)
            self.assertFalse(regular)
            maps = ({('najian', '\u90a3\u95f4'): 80}, {('najian', '\u90a3\u9593'): 80})
            builder._inject_curated_daily_post_rank_exact_entries(*maps, exact)
            self.assertEqual({('najian', '\u90a3\u95f4'): 0}, maps[0])
            self.assertEqual({('najian', '\u90a3\u9593'): 0}, maps[1])

    def test_manifest_exact_ranks_are_explicit_and_reproducible(self):
        entries, _ = builder._parse_curated_daily_phrase_entries(
            (ROOT / 'manifests/curated_daily_supplement_phrases.tsv').read_bytes(), 2)
        wanted = {(row[0], row[1]) for row in ROWS}
        entries = [entry for entry in entries if (entry[3], entry[0]) in wanted]
        regular, exact = builder._partition_curated_daily_post_rank_exact_entries(entries)
        self.assertFalse(regular)
        self.assertEqual(len(ROWS), len(exact))
        maps = ({}, {})
        builder._inject_curated_daily_post_rank_exact_entries(*maps, exact)
        builder._inject_curated_daily_post_rank_exact_entries(*maps, exact)
        for index, mapping in enumerate(maps, 1):
            self.assertEqual({(row[0], row[index]): row[3] for row in ROWS}, mapping)

    def test_multiple_added_readings_preserve_primary_and_existing_aliases(self):
        original = {('na', NA): 950, ('nei', '\u5185'): 567,
                    ('nuo', '\u7cef'): 223, ('nage', NA + '\u4e2a'): 1000,
                    ('naxie', NA + '\u4e9b'): 1000}
        result = dict(original)
        builder._restore_audited_additive_pinyin_readings(result, 'test')
        self.assertEqual(60, result[('nei', NA)])
        self.assertEqual(180, result[('nuo', NA)])
        for key, weight in original.items():
            self.assertEqual(weight, result[key])
        self.assertEqual(1000, result[('neige', NA + '\u4e2a')])
        once = dict(result)
        builder._restore_audited_additive_pinyin_readings(result, 'test')
        self.assertEqual(once, result)
        result[('nei', NA)] = 200
        builder._restore_audited_additive_pinyin_readings(result, 'test')
        self.assertEqual(200, result[('nei', NA)])

    def test_no_blanket_name_place_or_phrase_expansion(self):
        original = {('naqu', NA + '\u66f2'): 120, ('naqiner', NA + '\u7434\u513f'): 10,
                    ('nahaizao', NA + '\u8fd8\u65e9'): 420, ('nage', '\u7eb3\u683c'): 40}
        mapping = dict(original)
        builder._restore_audited_additive_pinyin_readings(mapping, 'test')
        self.assertEqual(original, mapping)
        empty = {}
        builder._restore_audited_additive_pinyin_readings(empty, 'test')
        self.assertFalse(empty)

    def test_output_preserves_audited_word_keys_and_primary_flags(self):
        mapping = {('na', NA): 950, ('nage', NA + '\u4e2a'): 1000}
        builder._restore_audited_additive_pinyin_readings(mapping, 'test')
        keys = {(added, text) for text, _, added, _ in builder.AUDITED_ADDITIVE_PINYIN_READINGS}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'dict.txt'
            builder._write_dict(path, mapping, preserve_pinyin_keys=keys,
                                contains_popularity_excluded_keys=keys,
                                unihan_map={NA: 'na'}, unihan_readings_map={NA: {'na'}})
            written = path.read_text(encoding='utf-8')
            for pinyin in ('na', 'nei', 'nuo'):
                self.assertIn(f'{pinyin}\t{NA}\t', written)
            self.assertIn(f'neige\t{NA}\u4e2a\t1000\tno_contains\n', written)
            self.assertIn(f'nage\t{NA}\u4e2a\t1000\n', written)
            self.assertIn(f'na\t{NA}\t950\n', written)

    def test_generated_readings_visible_without_displacing_primary_homophones(self):
        for variant in ('sc', 'tc'):
            rows = load_merged_dict([ROOT / f'data/generated/dict_unihan_{variant}.txt'])
            self.assertIn((NA, 950 if variant == 'sc' else 913), rows['na'])
            self.assertIn((NA, 60), rows['nei'][:9])
            self.assertIn((NA, 180), rows['nuo'][:9])
            self.assertNotEqual(NA, rows['nei'][0][0])
            self.assertNotEqual(NA, rows['nuo'][0][0])

    def test_generated_phrases_flags_and_completion_priors(self):
        for index, variant in enumerate(('sc', 'tc'), 1):
            clean = ROOT / f'data/generated/dict_clean_{variant}.txt'
            mapping = {}
            for line in clean.read_text(encoding='utf-8').splitlines():
                fields = line.split('\t')
                key = tuple(fields[:2])
                self.assertNotIn(key, mapping)
                mapping[key] = fields[2:]
            for row in ROWS:
                self.assertEqual([str(row[3]), 'no_contains'], mapping[(row[0], row[index])])
            for text, source, added, _ in builder.AUDITED_ADDITIVE_PINYIN_READINGS:
                if len(text) > 1 and (source, text) in mapping:
                    self.assertEqual(mapping[(source, text)][0], mapping[(added, text)][0])
                    self.assertEqual(['no_contains'], mapping[(added, text)][1:])
            self.assertEqual('1000', mapping[('haizao', '\u6d77\u85fb')][0])
            prior = {}
            for line in (ROOT / f'data/generated/dict_completion_prior_{variant}.txt').read_text(
                    encoding='utf-8').splitlines():
                fields = line.split('\t')
                prior[tuple(fields[:2])] = tuple(map(int, fields[2:]))
            for row in ROWS:
                self.assertEqual((80, 0, 0, 0, 0, 0, 0), prior[(row[0], row[index])])


if __name__ == '__main__':
    unittest.main()
