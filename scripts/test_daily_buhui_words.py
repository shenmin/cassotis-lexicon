"""Words of 2026-11-09: 不 before a verb of 回 (不回来, 不回去, 不回家, 不回头, 不回复, 不回答),
补回去 beside 补回来, the phrases 不会X those keys showed before (不会去, 不会想), and one character
before 间 for a room (大间, 通间, 小间, 明间, 单间). The user: "还得加：不回来、不回去、补回去、
（不回X>补回X）": on a key that has both, 不回X goes above 补回X; then "再加：大间、通间、小间、……".
Weighted as test_daily_zhefeng_words
(occurrences where the word is no part of a longer dictionary word, nor
before one that its last character begins, nor after one that its first
character ends); a word stays under every more frequent word of its key."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from test_daily_whitespace_phrases import read_rows
from test_daily_cuo_xiu_sha_shui_phrases import block

HEADERS = {'common': "# Everyday words, 2026-11-09, the more frequent ones: 不 before a verb of 回 (the user's 不回来 and 不回去; 不回家, 不回头, 不回答, 不回复, 不回避, 不回应), 补回去 beside 补回来 (the user: 不回X above 补回X), the phrases 不会X of those keys that the short-phrase stage put together before (不会去, 不会想, 不会像, 不会了, 不会比), and one character before 间 for a room (the user's 大间, 通间 and 小间; 明间, 次间), weighted by the general text as the batches before.", 'less': '# Everyday words, 2026-11-09, the less frequent ones (不回国, 不回收, 不回弹, 不会犯, 不会留, 梢间, 半间, 东间, 西间), by the same weights.'}
SIZES = {'common': 23, 'less': 67}
REQUESTED = ['不回来', '不回去', '补回去', '大间', '通间', '小间']
HEADER_FORCED = '# Weighted anew on 2026-11-09: import-weight words of the X间 family, which the general text holds far more often than their weights say (单间, 包间).'
FORCED = [('danjian', '单间', '單間', 600), ('baojian', '包间', '包間', 368)]
ROWS = tuple(row[:4] for header in HEADERS.values() for row in block(header))


class DailyBuhuiWordsTests(unittest.TestCase):
    def test_blocks(self):
        for group, header in HEADERS.items():
            rows = block(header)
            self.assertEqual(SIZES[group], len(rows), group)
            self.assertEqual({"exact_rank_no_contains"}, {row[4] for row in rows}, group)
        self.assertEqual(len(ROWS), len({(row[0], row[1]) for row in ROWS}))
        texts = {row[1] for row in ROWS}
        for word in REQUESTED:
            self.assertIn(word, texts, word)

    def test_kinds(self):
        for pinyin, sc, tc, _weight in ROWS + tuple(row[:4] for row in FORCED):
            self.assertIn(len(sc), (2, 3, 4, 5), sc)
            self.assertEqual(len(sc), len(tc), sc)
            self.assertNotIn("'", pinyin)
        keys = {(row[0], row[1]) for row in ROWS}
        for pinyin, word in (("buhuilai", "不回来"), ("buhuiqu", "不回去"), ("buhuiqu", "补回去")):
            self.assertIn((pinyin, word), keys)

    def test_buhui_above_mending(self):
        # The user: "（不回X>补回X）".
        for variant, index in (("sc", 0), ("tc", 1)):
            rows = read_rows(f"dict_clean_{variant}.txt")
            for pinyin, pair in (("buhuilai", (("不回来", "不回來"), ("补回来", "補回來"))),
                                 ("buhuiqu", (("不回去", "不回去"), ("补回去", "補回去")))):
                (high, low) = (word[index] for word in pair)
                self.assertGreater(int(rows[(pinyin, high)][0]), int(rows[(pinyin, low)][0]), (variant, pinyin))

    def test_order(self):
        by_key = {}
        for (pinyin, text), fields in read_rows("dict_clean_sc.txt").items():
            by_key.setdefault(pinyin, {})[text] = int(fields[0])
        for pinyin, word, _tc, weight in ROWS + tuple(FORCED):
            self.assertEqual(weight, by_key[pinyin][word], word)
            others = [text for text, value in by_key[pinyin].items() if text != word and value == weight]
            # Under a word at 1 (an import's weight) the batch's words go to 0,
            # where they cannot be ordered (只招 and 只找 under 支招).
            if weight > 0:
                self.assertFalse(others, (pinyin, word))

    def test_explicit_ranks_survive_rebuild(self):
        entries, _ = builder._parse_curated_daily_phrase_entries(
            (ROOT / "manifests/curated_daily_supplement_phrases.tsv").read_bytes(), 2)
        wanted = {(row[0], row[1]) for row in ROWS}
        selected = [entry for entry in entries if (entry[3], entry[0]) in wanted]
        regular, exact = builder._partition_curated_daily_post_rank_exact_entries(selected)
        self.assertFalse(regular)
        self.assertEqual(len(ROWS), len(exact))
        maps = ({}, {})
        builder._inject_curated_daily_post_rank_exact_entries(*maps, exact)
        for index, mapping in enumerate(maps, 1):
            self.assertEqual({(row[0], row[index]): row[3] for row in ROWS}, mapping)

    def test_generated_entries_and_prior(self):
        for index, variant in enumerate(("sc", "tc"), 1):
            rows = read_rows(f"dict_clean_{variant}.txt")
            prior = read_rows(f"dict_completion_prior_{variant}.txt")
            for row in ROWS:
                self.assertEqual([str(row[3]), "no_contains"], rows[(row[0], row[index])])
                self.assertEqual(["80", "0", "0", "0", "0", "0", "0"], prior[(row[0], row[index])])
            for row in FORCED:
                self.assertEqual(str(row[3]), rows[(row[0], row[index])][0])


if __name__ == "__main__":
    unittest.main()
