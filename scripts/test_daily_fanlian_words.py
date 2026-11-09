"""Words of 2026-11-09: one character before 翻 for the direction or way of a turn (上翻,
下翻, 前翻, 后翻, 内翻) or a result (笑翻, 吵翻, 撞翻), and before 链 for a kind of link or chain
(软链, 硬链, 短链, 公链, 碳链). The user: "那有空时再帮我添加：上翻、下翻、软链、硬链、左翻、右翻、
前翻、后翻、……". Weighted as test_daily_zhefeng_words
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

HEADERS = {'common': "# Everyday words, 2026-11-09, the more frequent ones: one character before 翻 or 链 (the user's examples 上翻, 下翻, 左翻, 右翻, 前翻, 后翻, 软链 and 硬链; then 内翻, 滚翻, 深翻, 嗨翻, 翻翻), for the direction or way of a turn and for a kind of link or chain (短链, 内链, 公链, 主链, 跨链, 上链, 断链, 长链, 支链, 碳链, 重链, 补链, 强链), weighted by the general text as the batches before.", 'less': '# Everyday words, 2026-11-09, the less frequent ones (回翻, 笑翻, 吵翻, 撞翻, 精翻, 重翻, 友链, 死链, 盗链, 珠链, 犬链, 建链), by the same weights.'}
SIZES = {'common': 29, 'less': 61}
REQUESTED = ['上翻', '下翻', '软链', '硬链', '左翻', '右翻', '前翻', '后翻']
HEADER_FORCED = '# Weighted anew on 2026-11-09: import-weight words of the family, which the general text holds far more often than their weights say (金链, 表链, 狗链, 银链), and 眼帘, at an import\'s 1 under 演练 though the general text holds it 2,855 times (the user: "眼帘 改吧").'
FORCED = [('biaolian', '表链', '錶鏈', 200), ('goulian', '狗链', '狗鏈', 200), ('yinlian', '银链', '銀鏈', 200), ('jinlian', '金链', '金鍊', 400), ('yanlian', '眼帘', '眼簾', 600)]
ROWS = tuple(row[:4] for header in HEADERS.values() for row in block(header))


class DailyFanlianWordsTests(unittest.TestCase):
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
        for pinyin, word in (("shangfan", "上翻"), ("houfan", "后翻"), ("ruanlian", "软链"), ("yinglian", "硬链")):
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
