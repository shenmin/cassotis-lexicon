"""Words of 2026-11-06: 将, 会 and 就 before a preposition, a copula or an auxiliary
(将在, 将于, 将是, 会在, 就于), the same after other adverbs (已在, 曾是, 仍将) and the short phrases they make.
The user: "帮我添加一批：将在、将于、会在、会于、就于、将是、……". Weighted as test_daily_hui_dong_words
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

HEADERS = {'common': "# Everyday words, 2026-11-06, the more frequent ones: 将在, 将于, 将是, 会在, 会于 and 就于 (the user's examples), 将, 会 and 就 before a preposition, a copula, an adverb or a verb (将被, 将对, 会使, 就更), 将 before a pronoun (将其, 将此), adverbs and conjunctions before 在, 于, 是, 将 and 会 (已在, 并于, 曾是, 还将, 则会), and the short phrases they make (将会在, 已经在, 将成为), weighted by the general text as the batches before, and the words such a word would take off its page or put below itself (不会再, 能与, 并与).", 'less': '# Everyday words, 2026-11-06, the less frequent ones (将呈, 会愈, 就落, 仅于, 又会在), by the same weights.'}
SIZES = {'common': 477, 'less': 45}
REQUESTED = ['将在', '将于', '会在', '会于', '就于', '将是']
HEADER_FORCED = '# Weighted anew on 2026-11-06: import-weight words of the family, which the general text holds far more often than their weights say (也在, 并在, 就连, 将至, 倒是, 恰是).'
FORCED = [('jiangzhi', '将至', '將至', 277), ('jiulian', '就连', '就連', 600), ('yezai', '也在', '也在', 600), ('bingzai', '并在', '並在', 600), ('daoshi', '倒是', '倒是', 341), ('qiashi', '恰是', '恰是', 600)]
ROWS = tuple(row[:4] for header in HEADERS.values() for row in block(header))


class DailyJiangWordsTests(unittest.TestCase):
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
        for pinyin, word in (("jiangzai", "将在"), ("jiangyu", "将于"), ("huizai", "会在"), ("huiyu", "会于"), ("jiuyu", "就于"), ("jiangshi", "将是")):
            self.assertIn((pinyin, word), keys)

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
