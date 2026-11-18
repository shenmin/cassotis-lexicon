"""Words of 2026-11-18: the user's 都已, 事后关怀, 我很, 他很, 她很, 来搞, 来弄, 去弄, 别搞, 还搞, 还弄, 好乱,
更顶, 平级, 还送, 来送, 去送, 别送 and 一批词, and their kinds: a pronoun or an adverb before 很, a word of where or
whether before 搞, 弄, 送 and other verbs of everyday speech, 都 and its kind before 已, care and its kinds, a degree
word before an adjective of one character, ranks and batches. The user: "再加一批词：都（dou）已、事后关怀、我很、他很、
她很、来搞、来弄、去弄、别搞、还（hai）搞、还（hai）弄、好乱、更顶、平级、还（hai）送、来送、去送、别送、一批词、……". Words of
the families at an import weight are weighted anew. Weighted as test_daily_chaka_words (occurrences where
the word is no part of a longer dictionary word, nor before one that its last character begins, nor after one that its
first character ends); a word stays under every more frequent word of its key."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from test_daily_whitespace_phrases import read_rows
from test_daily_cuo_xiu_sha_shui_phrases import block

HEADERS = {'common': "# Everyday words, 2026-11-18, the more frequent ones: the user's 都已, 事后关怀, 我很, 他很, 她很, 来搞, 来弄, 去弄, 别搞, 还搞, 还弄, 好乱, 更顶, 平级, 还送, 来送, 去送, 别送 and 一批词, and their kinds the lexicon lacked: a pronoun or an adverb before 很 (觉得很, 真的很, 不是很), a word of where or whether before 搞, 弄, 送 and other verbs of everyday speech (自己搞, 没弄, 去办, 还拿), 都 and its kind before 已 (均已, 都曾), care (人文关怀), a degree word before an adjective of one character (好慢, 太乱, 更狠), ranks (军级, 乡级) and batches (一批人, 本批), weighted by the general text as the batches before; 来搞 above 来稿 by everyday conversation; 这么高, 那么高, 一批次 and 省一级, phrases the page showed on their keys before the batch's words came; 好水 at 2 under 好睡, 平调 at 200 under 凭吊.", 'less': '# Everyday words, 2026-11-18, the less frequent ones (您很, 别弄, 先送, 来整, 好困, 好饿, 好帅, 好疼, 跨级, 一批货, 收词), by the same weights; 好酷, 好苦, 好短, 好忙, 好痒 and 好瘦 above a word of their key that everyday conversation hardly writes; 那么浓 and 事后不久, phrases the page showed on their keys before; 更怪 at 40 under 更乖; 好吵, 好胖, 没送, 事后烟, 售后关怀, 这批词 and other words the general text seldom writes as words, at 2.'}
SIZES = {'common': 128, 'less': 186}
REQUESTED = ['都已', '事后关怀', '我很', '他很', '她很', '来搞', '来弄', '去弄', '别搞', '还搞', '还弄', '好乱', '更顶', '平级', '还送', '来送', '去送', '别送', '一批词']
HEADER_FORCED = '# Weighted anew on 2026-11-18: 好长 and 更惨 at an import weight, and 好养 above 好氧 by everyday conversation.'
FORCED = [('haochang', '好长', '好長', 600), ('gengcan', '更惨', '更慘', 600), ('haoyang', '好养', '好養', 135)]
ROWS = tuple(row[:4] for header in HEADERS.values() for row in block(header))


class DailyWohenWordsTests(unittest.TestCase):
    def test_blocks(self):
        for group, header in HEADERS.items():
            rows = block(header)
            self.assertEqual(SIZES[group], len(rows), group)
            self.assertEqual({"exact_rank_no_contains"}, {row[4] for row in rows}, group)
        self.assertEqual(len(ROWS), len({(row[0], row[1]) for row in ROWS}))
        texts = {row[1] for row in ROWS} | {row[1] for row in FORCED}
        for word in REQUESTED:
            self.assertIn(word, texts, word)

    def test_kinds(self):
        for pinyin, sc, tc, _weight in ROWS + tuple(row[:4] for row in FORCED):
            self.assertIn(len(sc), (2, 3, 4, 5, 6), sc)
            self.assertEqual(len(sc), len(tc), sc)
            self.assertNotIn("'", pinyin)
        keys = {(row[0], row[1]) for row in ROWS + tuple(FORCED)}
        # Readings by the meaning: 都 of all (dou), 还 of still (hai), 弄 of handling (nong).
        for pinyin, word in (("douyi", "都已"), ("haigao", "还搞"), ("hainong", "还弄"), ("haisong", "还送"),
                             ("lainong", "来弄")):
            self.assertIn((pinyin, word), keys)

    def test_order_on_shared_keys(self):
        # The everyday words of a key stay above the batch's: none listed.
        for variant, index in (("sc", 0), ("tc", 1)):
            rows = read_rows(f"dict_clean_{variant}.txt")
            for pinyin, pair in ():
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
