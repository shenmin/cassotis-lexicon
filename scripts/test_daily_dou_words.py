"""Words of 2026-10-27: 都 read dou before a verb or an adjective of one
character. The user, after the batch of words on keys without a word: "还要添加：
都（dou）叫、……". The dictionary had 176 such words and not 都叫; the pairs
jieba cuts as the adverb 都 and a word of one character in the general text
and in chat sentences, reviewed by hand (pieces of longer words, prepositions
and readings the key cannot tell left out). Weighted as
test_daily_suo_bijiao_phrases (occurrences where the word is no part of a
longer dictionary word, nor before one that its last character begins, nor
after one that its first character ends)."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from test_daily_whitespace_phrases import read_rows
from test_daily_cuo_xiu_sha_shui_phrases import block, keys

HEADERS = {'common': "# Everyday words, 2026-10-27, the third batch: 都 (dou) before a verb or an adjective of one character, the more frequent ones: 都叫 (the user's example), 都找, 都怪, 都别, 都挺, 都还, 都算, 都涨, 都赚, 都喊; the pairs jieba cuts as the adverb 都 and a word of one character in the general text and in chat sentences that the dictionary lacked, reviewed by hand (pieces of longer words such as 都需 of 都需要, prepositions, readings the key cannot tell left out). Weighted as the blocks of 2026-10-20 (occurrences where the word is no part of a longer dictionary word, nor before one that its last character begins, nor after one that its first character ends); 都叫 stays under 豆角 (not one and a half times as frequent) and 都花 under 豆花 (not three times); 都归 and 都填 go above 都跪 and 都舔 of 2026-10-22, eight and ten times as frequent (their samples one rank lower).", 'less': '# Everyday words, 2026-10-27, the third batch, the less frequent ones of the same kind (都抱, 都劝, 都掉, 都赔, 都红, 都痛, 都骂, 都扔, 都亮, 都热, 都挤, 都松, 都黑, 都冷), by the same weights.'}
SIZES = {'common': 74, 'less': 14}
REQUESTED = ['都叫']
ROWS = tuple(row[:4] for header in HEADERS.values() for row in block(header))


class DailyDouWordsTests(unittest.TestCase):
    def test_blocks(self):
        for group, header in HEADERS.items():
            rows = block(header)
            self.assertEqual(SIZES[group], len(rows), group)
            self.assertEqual({"exact_rank_no_contains"}, {row[4] for row in rows}, group)
        self.assertEqual(len(ROWS), len({(row[0], row[1]) for row in ROWS}))
        texts = {row[1] for row in ROWS}
        for word in REQUESTED:
            self.assertIn(word, texts, word)
        self.assertIn(("doujiao", "都叫", "都叫"), {row[:3] for row in ROWS})

    def test_dou_and_one_character(self):
        for pinyin, sc, tc, _weight in ROWS:
            self.assertEqual(2, len(sc), sc)
            self.assertTrue(sc.startswith("都") and tc.startswith("都"), sc)
            self.assertTrue(pinyin.startswith("dou") and "'" not in pinyin, pinyin)

    def test_order(self):
        rows = keys("sc")
        self.assertEqual(600, rows["doujiao"]["都叫"])
        by_key = {}
        for (pinyin, text), fields in read_rows("dict_clean_sc.txt").items():
            by_key.setdefault(pinyin, {})[text] = int(fields[0])
        for pinyin, word, _tc, weight in ROWS:
            others = [text for text, value in by_key[pinyin].items() if text != word and value == weight]
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


if __name__ == "__main__":
    unittest.main()
