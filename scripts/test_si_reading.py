"""伺 reads si in 伺服, 伺机, 窥伺 and 侦伺, ci only in 伺候 (2026-11-02).

The single characters had 伺 under ci only, so the specialist admissions
read 伺服电机 cifudianji, words without a reading of their own took ci
(伺机而动, the verse line 睢盱侦伺能鞠躬), and so did the word transitions
and completions built from them (伺服|电机 under cifudianji)."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_external_cedict as builder

GEN = ROOT / 'data/generated'
CHAR = '伺'
HOU = '候'


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


def wrong_readings(text, reading):
    syllables = syllables_of(text, reading)
    if syllables is None:
        return None
    return [i for i, ch in enumerate(text)
            if ch == CHAR and text[i + 1:i + 2] != HOU and syllables[i] != 'si']


class SiReadingTests(unittest.TestCase):
    def test_overrides_give_the_single_character_si_in_both_variants(self):
        for variant in ('sc', 'tc'):
            overrides = builder._load_pinyin_overrides(ROOT / f'manifests/pinyin_overrides.{variant}.tsv')
            self.assertEqual('si', overrides[CHAR])
        result, _ = builder._apply_word_pinyin_overrides({('ci', CHAR): 193}, {CHAR: 'si'}, 'test')
        self.assertEqual({('ci', CHAR): 193, ('si', CHAR): 193}, result)

    def test_single_character_reads_both_by_use(self):
        for variant in ('sc', 'tc'):
            weights = {(py, text): int(weight)
                       for py, text, weight in rows(GEN / f'dict_unihan_{variant}.txt', 3)}
            self.assertIn(('ci', CHAR), weights)
            # Under si by its use in the general text: below 泗, above 嘶.
            self.assertLess(weights[('si', '嘶')], weights[('si', CHAR)])
            self.assertLess(weights[('si', CHAR)], weights[('si', '泗')])

    def test_generated_rows_read_si_outside_cihou(self):
        tables = (
            ('dict_clean', 2, 1, 0),
            ('dict_completion_prior', 2, 1, 0),
            ('dict_completion_lookup', 3, 2, 1),
            ('dict_query_path_prior', 2, 1, 0),
            ('dict_lm_transition', 2, 1, 0),
            ('dict_transition_completion', 4, 2, 1),
        )
        for name, columns, text_column, reading_column in tables:
            aligned = 0
            for variant in ('sc', 'tc'):
                for fields in rows(GEN / f'{name}_{variant}.txt', columns):
                    text = fields[text_column].replace('|', '')
                    if CHAR not in text:
                        continue
                    wrong = wrong_readings(text, fields[reading_column])
                    if wrong is None:
                        continue
                    aligned += 1
                    self.assertEqual([], wrong, (name, variant, fields))
            self.assertGreater(aligned, 0, name)
        for variant in ('sc', 'tc'):
            for anchor, reading, text, _path in rows(GEN / f'dict_long_completion_{variant}.txt', 4):
                if CHAR in text:
                    body = text.lstrip('，。')
                    self.assertEqual([], wrong_readings(body, reading), (anchor, text))

    def test_cihou_keeps_ci(self):
        for variant in ('sc', 'tc'):
            keys = {(py, text) for py, text in rows(GEN / f'dict_clean_{variant}.txt', 2)}
            self.assertIn(('cihou', CHAR + HOU), keys)
            self.assertNotIn(('sihou', CHAR + HOU), keys)

    def test_manifests_read_si(self):
        for path, columns in (('manifests/vertical/thuocl_specialist_admissions.tsv', (0, 3)),
                              ('manifests/curated_daily_supplement_phrases.tsv', (0, 3))):
            for fields in rows(ROOT / path, 4):
                if len(fields) < 4:
                    continue
                text, reading = fields[columns[0]], fields[columns[1]]
                if CHAR in text and reading:
                    self.assertEqual([], wrong_readings(text, reading), (path, text))
        for fields in rows(ROOT / 'manifests/classical_poetry_next_lines.tsv', 6):
            if CHAR in fields[3]:
                self.assertEqual([], wrong_readings(fields[3], fields[5]), fields[3])


if __name__ == '__main__':
    unittest.main()
