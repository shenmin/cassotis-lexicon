"""Words of 2026-11-08: 失 and 无 with one character, for a loss (失温, 失水, 失热) and for
being without something (无事, 无钱, 无眠, 无雨, 无病). The user: "再帮我加一批日常：失温、失热、失水、
无事、无贼、无天、无命、无钱、无税、无眠、无字、无雨、无韵、无光、无油、无父、无母、无子、无女、
无酒、无籽、无生、无死、无病、……". Weighted as test_daily_zhefeng_words
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

HEADERS = {'common': "# Everyday words, 2026-11-08, the more frequent ones: 失 and 无 with one character (the user's examples 失温, 失热, 失水, 无事, 无钱, 无眠, 无雨, 无病 and the rest of their list; then 无休, 无止, 无好, 无坏 and 无差, read cha), for a loss (失分, 失能, 失聪, 失序) and for being without something (无忧, 无证, 无痕, 无创, 无涯, 无憾; the other halves of 无好 and 无坏: 无对, 无错, 无善, 无多), weighted by the general text as the batches before.", 'less': '# Everyday words, 2026-11-08, the less frequent ones (失怙, 失婚, 失盗, 无霜, 无薪, 无磷, 无优, 无劣, 无高, 无低), by the same weights.'}
SIZES = {'common': 115, 'less': 27}
REQUESTED = ['失温', '失热', '失水', '无事', '无贼', '无天', '无命', '无钱', '无税', '无眠', '无字', '无雨', '无韵', '无光', '无油', '无父', '无母', '无子', '无女', '无酒', '无籽', '无生', '无死', '无病', '无休', '无止', '无好', '无坏', '无差']
HEADER_FORCED = '# Weighted anew on 2026-11-08: import-weight words of the family, which the general text holds far more often than their weights say (失地, 失约, 失策, 无价, 无明, 无题, 无业, 无状, 无算).'
FORCED = [('shidi', '失地', '失地', 50), ('shiyue', '失约', '失約', 481), ('shice', '失策', '失策', 107), ('wujia', '无价', '無價', 600), ('wuming', '无明', '無明', 600), ('wuti', '无题', '無題', 600), ('wuye', '无业', '無業', 555), ('wuzhuang', '无状', '無狀', 200), ('wusuan', '无算', '無算', 200)]
ROWS = tuple(row[:4] for header in HEADERS.values() for row in block(header))


class DailyShiwuWordsTests(unittest.TestCase):
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
        for pinyin, word in (("shiwen", "失温"), ("wushi", "无事"), ("wuqian", "无钱")):
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
