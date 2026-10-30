"""Daily additions with independent counts and explicit chang in 粗长."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_external_cedict as builder
from test_daily_whitespace_phrases import read_rows

ROWS = [('weifu', '微幅', '微幅', 399), ('jiban', '几版', '幾版', 80),
        ('bushengfanjiang', '不升反降', '不升反降', 200), ('busheng', '不升', '不升', 600),
        ('fanjiang', '反降', '反降', 200), ('meitui', '美腿', '美腿', 600),
        ('cuduan', '粗短', '粗短', 400), ('cuchang', '粗长', '粗長', 200),
        ('xiduan', '细短', '細短', 200)]


class DailyWeifuWordsTests(unittest.TestCase):
    def test_explicit_readings_and_weights(self):
        entries, _ = builder._parse_curated_daily_phrase_entries(
            (ROOT / 'manifests/curated_daily_supplement_phrases.tsv').read_bytes(), 2)
        wanted = {(r[0], r[1]) for r in ROWS}
        selected = [r for r in entries if (r[3], r[0]) in wanted]
        regular, exact = builder._partition_curated_daily_post_rank_exact_entries(selected)
        self.assertFalse(regular)
        self.assertEqual(len(ROWS), len(exact))
        maps = ({}, {})
        builder._inject_curated_daily_post_rank_exact_entries(*maps, exact)
        for index, mapping in enumerate(maps, 1):
            self.assertEqual({(r[0], r[index]): r[3] for r in ROWS}, mapping)

    def test_both_variants_and_frequency_evidence(self):
        for index, variant in enumerate(('sc', 'tc'), 1):
            base = read_rows(f'dict_clean_{variant}.txt')
            prior = read_rows(f'dict_completion_prior_{variant}.txt')
            frequency = {}
            for line in (ROOT / f'data/generated/dict_word_frequency_{variant}.txt').read_text(encoding='utf-8').splitlines():
                if line and not line.startswith('#'):
                    word, value = line.split('\t')
                    frequency[word] = int(value)
            for pinyin, sc, tc, weight in ROWS:
                word = sc if index == 1 else tc
                self.assertEqual([str(weight), 'no_contains'], base[(pinyin, word)])
                self.assertIn((pinyin, word), prior)
                self.assertGreater(frequency[word], 0)
            self.assertNotIn(('cuzhang', '粗长' if index == 1 else '粗長'), base)

    def test_common_homophones_not_displaced_by_weight(self):
        base = read_rows('dict_clean_sc.txt')
        for key, first, later in [('jiban', '基板', '几版'), ('jiban', '羁绊', '几版'),
                                  ('busheng', '不胜', '不升'), ('weifu', '未付', '微幅'),
                                  ('xiduan', '西端', '细短')]:
            self.assertGreater(int(base[(key, first)][0]), int(base[(key, later)][0]))


if __name__ == '__main__':
    unittest.main()
