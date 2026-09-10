"""Check audited merged readings and the household/article vocabulary delta."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_external_cedict as builder
from validate_regression_samples import load_merged_dict

ZA_SC = '\u624e'
ZA_TC = '\u7d2e'
MARKER = '# Household actions, article references and binding wire 2026-09-10.'


class MergedReadingTests(unittest.TestCase):
    def test_restore_sc_reading_without_rekeying_primary_or_traditional(self):
        sc = {('zha', ZA_SC): 402, ('za', '\u6742'): 570}
        tc = {('zha', ZA_SC): 404, ('za', ZA_TC): 279}
        original_tc = dict(tc)
        stats = builder._restore_audited_simplified_single_char_readings(sc, tc, 'test')
        self.assertEqual(279, sc[('za', ZA_SC)])
        self.assertEqual(402, sc[('zha', ZA_SC)])
        self.assertEqual(original_tc, tc)
        self.assertEqual(1, stats['test_simplified_readings_restored'])

    def test_existing_reading_is_preserved_and_refresh_is_idempotent(self):
        sc = {('zha', ZA_SC): 402, ('za', ZA_SC): 310}
        original = dict(sc)
        for _ in range(2):
            builder._restore_audited_simplified_single_char_readings(sc, {('za', ZA_TC): 279}, 'test')
        self.assertEqual(original, sc)

    def test_unverified_or_nonpositive_source_cannot_add_a_reading(self):
        for tc in ({}, {('zha', ZA_TC): 400}, {('za', ZA_TC): 0}):
            sc = {('zha', ZA_SC): 402}
            builder._restore_audited_simplified_single_char_readings(sc, tc, 'test')
            self.assertEqual({('zha', ZA_SC): 402}, sc)

    def test_phrase_only_build_does_not_gain_a_single_character(self):
        sc = {('zajin', '\u624e\u7d27'): 720}
        original = dict(sc)
        builder._restore_audited_simplified_single_char_readings(sc, {('za', ZA_TC): 279}, 'test')
        self.assertEqual(original, sc)

    def test_new_reading_cannot_inherit_excessive_variant_weight(self):
        sc = {('zha', ZA_SC): 402}
        builder._restore_audited_simplified_single_char_readings(sc, {('za', ZA_TC): 1000}, 'test')
        self.assertEqual(builder.SINGLE_CHAR_ADDED_READING_WEIGHT_CAP, sc[('za', ZA_SC)])

    def test_restored_reading_survives_export_without_renumbering_old_rows(self):
        sc = {('zha', ZA_SC): 402, ('za', '\u6742'): 570}
        builder._restore_audited_simplified_single_char_readings(sc, {('za', ZA_TC): 279}, 'test')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'dict.txt'
            original = f'zha\t{ZA_SC}\t402\nza\t\u6742\t570\n'
            path.write_text(original, encoding='utf-8')
            builder._write_dict(path, sc, unihan_map={ZA_SC: 'zha'},
                                unihan_readings_map={ZA_SC: {'zha'}, ZA_TC: {'zha', 'za'}})
            expected = original + f'za\t{ZA_SC}\t279\n'
            self.assertEqual(expected, path.read_text(encoding='utf-8'))
            builder._write_dict(path, sc)
            self.assertEqual(expected, path.read_text(encoding='utf-8'))

    def test_generated_readings_are_on_first_page_in_both_scripts(self):
        for variant, target in (('sc', ZA_SC), ('tc', ZA_TC)):
            rows = load_merged_dict([ROOT / f'data/generated/dict_clean_{variant}.txt',
                                    ROOT / f'data/generated/dict_unihan_{variant}.txt'])
            self.assertIn(target, [text for text, _weight in rows['za'][:4]])
            self.assertIn(ZA_SC, [text for text, _weight in rows['zha'][:9]])

    def test_curated_rows_round_trip_with_explicit_readings_and_weights(self):
        payload = (ROOT / 'manifests/curated_daily_supplement_phrases.tsv').read_text(encoding='utf-8').split(MARKER, 1)[1].split('\n\n', 1)[0]
        entries, _ = builder._parse_curated_daily_phrase_entries(payload.encode('utf-8'), 2)
        regular, exact = builder._partition_curated_daily_post_rank_exact_entries(entries)
        self.assertFalse(regular)
        self.assertEqual(11, len(exact))
        sc, tc = {}, {}
        builder._inject_curated_daily_post_rank_exact_entries(sc, tc, exact)
        for variant, expected in (('sc', sc), ('tc', tc)):
            rows = {}
            for line in (ROOT / f'data/generated/dict_clean_{variant}.txt').read_text(encoding='utf-8').splitlines():
                parts = line.split('\t')
                rows[(parts[0], parts[1])] = parts[2:]
            for key, weight in expected.items():
                self.assertEqual([str(weight), 'no_contains'], rows[key])
                self.assertGreater(weight, 0)
                self.assertLessEqual(weight, 640)
            target = '\u624e\u4e1d\u94a9' if variant == 'sc' else '\u7d2e\u7d72\u9264'
            self.assertIn(('zasigou', target), expected)
            self.assertNotIn(('zhasigou', target), rows)


if __name__ == '__main__':
    unittest.main()
