"""Words of 2026-10-29: X刷, 发X, 以X, X着 and X的. The user: "添加日常库：
多刷、少刷、又刷、有刷、已刷、没刷、来刷、我刷、你刷、她刷、他刷、守着、发钱、发饷、发粮、
发米、发油、想的、以你、以我、以他、以她、……". More of each kind from the pairs of
the general text the dictionary lacked, reviewed by hand (pieces of longer
words, nouns before 的 and readings the key cannot tell left out); a verb
before 着 or 的 only where the key held another word (收着, 香的). Weighted
as test_daily_suo_bijiao_phrases
(occurrences where the word is no part of a longer dictionary word, nor
before one that its last character begins, nor after one that its first
character ends)."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from test_daily_whitespace_phrases import read_rows
from test_daily_cuo_xiu_sha_shui_phrases import block

HEADERS = {'common': '# Everyday words, 2026-10-29, the more frequent ones: 刷 after a word of one character (多刷, 少刷, 又刷, 有刷, 已刷, 没刷, 来刷, 我刷, 你刷, 她刷, 他刷: the user\'s examples, after "duoshua" had read duo shu a; 一刷, 二刷, 三刷, 被刷), 发 before what is handed out (发钱, 发饷, 发粮, 发米, 发油; 发工资, 发红包, 发奖金), 以 before a pronoun (以你, 以我, 以他, 以她; 以它, 以我们), and a verb of one character before 着 or 的 where the key held another word (守着 above 收着, 想的 under 香的; 住着, 爱的, 带的; low on their key: X的 where X得 is a word of the key, such as 藏的 and 跑的, since the general text writes 的 for 得 and counts X得 as X的, and words that took benchmark cases from a word of their key, such as 画着 and 讲着); the pairs of the general text that the dictionary lacked, reviewed by hand (pieces of longer words such as 持着 of 坚持着, nouns before 的, readings the key cannot tell left out). Weighted as the blocks of 2026-10-20 (occurrences where the word is no part of a longer dictionary word, nor before one that its last character begins, nor after one that its first character ends); a word stays under every more frequent word of its key, an import\'s weight included.', 'less': '# Everyday words, 2026-10-29, the less frequent ones (卡刷, 线刷, 油刷, 发糖, 发券, 发福利, 以你们, 以您, 选着, 改着, 磨着, 挨的, 躺的, 赶的), by the same weights.'}
SIZES = {'common': 133, 'less': 64}
REQUESTED = ['多刷', '少刷', '又刷', '有刷', '已刷', '没刷', '来刷', '我刷', '你刷', '她刷', '他刷', '守着', '发钱', '发饷', '发粮', '发米', '发油', '想的', '以你', '以我', '以他', '以她']
HEADER_FORCED = ''
FORCED = []
ROWS = tuple(row[:4] for header in HEADERS.values() for row in block(header))


class DailyShuaFaYiWordsTests(unittest.TestCase):
    def test_blocks(self):
        for group, header in HEADERS.items():
            rows = block(header)
            self.assertEqual(SIZES[group], len(rows), group)
            self.assertEqual({"exact_rank_no_contains"}, {row[4] for row in rows}, group)
        self.assertEqual(len(ROWS), len({(row[0], row[1]) for row in ROWS}))
        texts = {row[1] for row in ROWS}
        for word in REQUESTED:
            self.assertIn(word, texts, word)
        self.assertFalse(FORCED)
        self.assertEqual("", HEADER_FORCED)

    def test_kinds(self):
        for pinyin, sc, tc, _weight in ROWS:
            self.assertIn(len(sc), (2, 3), sc)
            self.assertNotIn("'", pinyin)
            if sc[-1] in "刷着的":
                self.assertEqual({"刷": "刷", "着": "著", "的": "的"}[sc[-1]], tc[-1], sc)
                self.assertTrue(pinyin.endswith({"刷": "shua", "着": "zhe", "的": "de"}[sc[-1]]), pinyin)
            else:
                self.assertIn(sc[0], "发以", sc)
                self.assertEqual({"发": "發", "以": "以"}[sc[0]], tc[0], sc)
                self.assertTrue(pinyin.startswith({"发": "fa", "以": "yi"}[sc[0]]), pinyin)

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
