"""靓 reads liang in 靓丽, 靓仔 and 靓汤 as well as jing (2026-11-19).

The single characters had 靓 under jing only, so it could not be typed as
liang, its modern reading (靓 occurs in the general text 15,551 times, 靓丽
alone 6,470), and the specialist admissions read 老火靓汤 laohuojingtang."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_external_cedict as builder

GEN = ROOT / 'data/generated'
CHARS = {'sc': '靓', 'tc': '靚'}


def rows(path, columns):
    for line in path.read_text(encoding='utf-8').splitlines():
        if line and not line.startswith('#'):
            yield line.split('\t')[:columns]


def syllables_of(text, reading):
    """The reading's syllables one to a character, or None."""
    syllables = []
    for part in reading.split("'"):
        parsed = builder._runtime_parse_compact_pinyin(part)
        if not parsed or ''.join(parsed) != part:
            return None
        syllables.extend(parsed)
    return syllables if len(syllables) == len(text) else None


class LiangReadingTests(unittest.TestCase):
    def test_overrides_give_the_single_character_liang_in_both_variants(self):
        for variant, char in CHARS.items():
            overrides = builder._load_pinyin_overrides(ROOT / f'manifests/pinyin_overrides.{variant}.tsv')
            self.assertEqual('liang', overrides[char])
        result, _ = builder._apply_word_pinyin_overrides({('jing', '靓'): 253}, {'靓': 'liang'}, 'test')
        self.assertEqual({('jing', '靓'): 253, ('liang', '靓'): 253}, result)

    def test_single_character_reads_both_by_use(self):
        neighbours = {'sc': ('晾', '凉'), 'tc': ('晾', '涼')}
        for variant, char in CHARS.items():
            weights = {(py, text): int(weight)
                       for py, text, weight in rows(GEN / f'dict_unihan_{variant}.txt', 3)}
            self.assertIn(('jing', char), weights)
            # Under liang by its use in the general text and in typed messages:
            # below 凉, above 晾.
            below, above = neighbours[variant]
            self.assertLess(weights[('liang', below)], weights[('liang', char)])
            self.assertLess(weights[('liang', char)], weights[('liang', above)])

    def test_words_read_liang(self):
        for variant, char in CHARS.items():
            for name in ('dict_clean', 'dict_completion_prior'):
                for reading, text in rows(GEN / f'{name}_{variant}.txt', 2):
                    if char not in text:
                        continue
                    syllables = syllables_of(text, reading)
                    self.assertIsNotNone(syllables, (name, text, reading))
                    readings = {syllables[i] for i, ch in enumerate(text) if ch == char}
                    self.assertEqual({'liang'}, readings, (name, variant, text, reading))

    def test_admission_reads_liang(self):
        for fields in rows(ROOT / 'manifests/vertical/thuocl_specialist_admissions.tsv', 4):
            if len(fields) >= 4 and fields[0] == '老火靓汤':
                self.assertEqual('laohuoliangtang', fields[3])
                break
        else:
            self.fail('老火靓汤 not admitted')


if __name__ == '__main__':
    unittest.main()
