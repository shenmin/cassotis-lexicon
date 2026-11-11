"""Words of 2026-11-11: 多 as "how" before an adjective (多长, 多短, 多难, 多高, 多帅, 多丑,
多重 read duozhong), 多渗人 beside 多瘆人, 瘆人, 题外 and 插线. The user: "日常库再帮我添加：题外、多长
（chang）、插线、多短、……；按照低频、高频、合适权重就行". 多长 and 多短 go above 多场 and 多端, which
everyday conversation writes far less often (LCCC). Weighted as test_daily_zhefeng_words
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

HEADERS = {'common': '# Everyday words, 2026-11-11, the more frequent ones: 多 as "how" before an adjective (the user\'s 多长 read duochang, 多短, 多怕, 多黑, 多难, 多穷, 多有, 多富, 多坏, 多渗人, 多轻, 多重 read duozhong, 多亮, 多暗, 多白, 多高, 多低, 多矮, 多帅 and 多丑; 多强, 多深, 多美, 多快, 多忙, 多贵, 多晚) and the user\'s 题外 and 插线, weighted by the general text as the batches before; 多长 and 多短 above 多场 and 多端, which everyday conversation writes far less often.', 'less': '# Everyday words, 2026-11-11, the less frequent ones (多慢, 多疼, 多冷, 多胖, 多瘦, 多饿, 多乖, 多瘆人 beside 多渗人, and 瘆人, of which 渗人 is the common miswriting), by the same weights.'}
SIZES = {'common': 45, 'less': 74}
REQUESTED = ['题外', '多长', '插线', '多短', '多怕', '多黑', '多难', '多穷', '多有', '多富', '多坏', '多渗人', '多轻', '多重', '多亮', '多暗', '多白', '多高', '多低', '多矮', '多帅', '多丑']
HEADER_FORCED = '# Weighted anew on 2026-11-11: import-weight words of the 多X keys that the general text holds far more often than their weights say (多远, 多好, 多块, 多段, 多图, 舵手, 渗人).'
FORCED = [('duoyuan', '多远', '多遠', 600), ('duohao', '多好', '多好', 600), ('duoduan', '多段', '多段', 318), ('duokuai', '多块', '多塊', 601), ('duotu', '多图', '多圖', 400), ('duoshou', '舵手', '舵手', 279), ('shenren', '渗人', '滲人', 200), ('duoxiang', '多箱', '多箱', 200), ('duoguai', '多怪', '多怪', 200), ('duoxian', '剁馅', '剁餡', 82)]
ROWS = tuple(row[:4] for header in HEADERS.values() for row in block(header))


class DailyDuoWordsTests(unittest.TestCase):
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
        # The user's readings: 多长 (chang), 多重 (zhong).
        for pinyin, word in (("duochang", "多长"), ("duozhong", "多重"), ("duoshenren", "多渗人"), ("tiwai", "题外"),
                             ("chaxian", "插线")):
            self.assertIn((pinyin, word), keys)

    def test_order_on_shared_keys(self):
        # 多长 above 多场 and 多短 above 多端 (conversation), 多渗人 (requested) above 多瘆人, 多重 under 多种.
        for variant, index in (("sc", 0), ("tc", 1)):
            rows = read_rows(f"dict_clean_{variant}.txt")
            for pinyin, pair in (("duochang", (("多长", "多長"), ("多场", "多場"))),
                                 ("duoduan", (("多短", "多短"), ("多端", "多端"))),
                                 ("duoshenren", (("多渗人", "多滲人"), ("多瘆人", "多瘮人"))),
                                 ("duozhong", (("多种", "多種"), ("多重", "多重")))):
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
