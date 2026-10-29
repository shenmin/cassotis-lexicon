"""Words of 2026-10-28: 才 (cai) and 只 (zhi, "only") before a verb or an
adjective of one character. The user: "再加一批：才开、才关、才醒、才睡、才至、……"
and "再加一批：只加、只挑、只点、只叫、……". The pairs jieba cuts as the adverb
and a word of one character in the general text and in chat sentences,
reviewed by hand (traditional forms, prepositions, pieces of longer words, 只
as a classifier and readings the key cannot tell left out); 只剩 and 只为,
imports at 0.01, weighted anew, and the words at an import's weight that
were more frequent than a word of the batch on its key (支架, 支点, 支教). Weighted as test_daily_suo_bijiao_phrases
(occurrences where the word is no part of a longer dictionary word, nor
before one that its last character begins, nor after one that its first
character ends). On 2026-10-29 踩脚 and 踩鞋, at 1000 from the daily action
phrases, took the tier of their own occurrences by those rules, and 才叫 and
才写, which had been put one below them, their own tiers."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from test_daily_whitespace_phrases import read_rows
from test_daily_cuo_xiu_sha_shui_phrases import block

HEADERS = {'common': "# Everyday words, 2026-10-28: 才 (cai) before a verb or an adjective of one character, the more frequent ones: 才开, 才关, 才醒, 才睡, 才至 (the user's examples), 才算, 才叫, 才知, 才想, 才够, 才懂, 才配; the pairs jieba cuts as the adverb 才 and a word of one character in the general text and in chat sentences that the dictionary lacked, reviewed by hand (traditional forms, prepositions, pieces of longer words such as 才恢 of 才恢复, readings the key cannot tell left out). Weighted as the blocks of 2026-10-20 (occurrences where the word is no part of a longer dictionary word, nor before one that its last character begins, nor after one that its first character ends); a word stays under every more frequent word of its key, an import's weight included (才关 under 菜馆, 才醒 under 才行, 才至 under 采制).", 'less': '# Everyday words, 2026-10-28: 才 (cai) before a verb of one character, the less frequent ones (才写, 才找, 才拿, 才停, 才考, 才活, 才带, 才穿, 才放, 才讲, 才像, 才问, 才跌, 才赚), by the same weights.', 'zhi_common': '# Everyday words, 2026-10-28: 只 (zhi, "only") before a verb or an adjective of one character, the more frequent ones: 只加, 只挑, 只点, 只叫 (the user\'s examples), 只占, 只靠, 只差, 只够, 只谈, 只等, 只让, 只讲, 只认; the pairs jieba cuts as the adverb 只 and a word of one character, reviewed by hand (只 as a classifier, 只狗 and 只猫, and pieces such as 只可 of 只可惜 left out), weighted by the same rules (只加 under 指甲 and 支架, 只点 under 指点, 支点 and 质点, 只叫 under 执教 and 支教).', 'zhi_less': '# Everyday words, 2026-10-28: 只 (zhi, "only") before a verb of one character, the less frequent ones (只盯, 只投, 只拍, 只住, 只填, 只扣, 只唱, 只杀, 只存, 只跌, 只拉, 只来), by the same weights.'}
SIZES = {'common': 23, 'less': 14, 'zhi_common': 52, 'zhi_less': 12}
REQUESTED = ['才开', '才关', '才醒', '才睡', '才至', '只加', '只挑', '只点', '只叫']
HEADER_FORCED = "# Words at an import's weight, 2026-10-28, weighted by the same rules as the 才 and 只 words: 只为 and 只剩, and the words at an import's weight on the keys of those words that are more frequent than one of them (支架, 趾甲, 制假, 支点, 质点, 支教, 纸巾, 织锦, 知己, 织机, 至极, 之道, 纸质, 彩绘, 采制; the user chose to weight them anew rather than to put the requested words above them); 直击, 踩上 and 踩稳 keep the low weights of their block."
FORCED = [('zhisheng', '只剩', '只剩', 279), ('zhiwei', '只为', '只為', 600), ('zhidao', '之道', '之道', 148), ('zhijia', '支架', '支架', 603), ('zhizhi', '纸质', '紙質', 600), ('zhitou', '枝头', '枝頭', 155), ('zhijiao', '支教', '支教', 600), ('zhiji', '知己', '知己', 382), ('zhijin', '纸巾', '紙巾', 601), ('caihui', '彩绘', '彩繪', 601), ('zhishou', '值守', '值守', 279), ('zhiyin', '知音', '知音', 601), ('zhidian', '支点', '支點', 183), ('zhiyuan', '致远', '致遠', 165), ('zhiai', '挚爱', '摯愛', 469), ('zhiqu', '志趣', '志趣', 531), ('zhifang', '置放', '置放', 400), ('zhidian', '质点', '質點', 182), ('zhizhao', '支招', '支招', 601), ('zhijia', '制假', '製假', 600), ('zhijin', '织锦', '織錦', 600), ('zhixuan', '直选', '直選', 279), ('zhiqian', '支前', '支前', 277), ('caizhi', '采制', '采制', 349), ('zhiji', '织机', '織機', 383), ('zhiji', '至极', '至極', 381), ('zhiqian', '纸钱', '紙錢', 278), ('zhijia', '趾甲', '趾甲', 601)]
ROWS = tuple(row[:4] for header in HEADERS.values() for row in block(header))
HEADER_CAIJIAO = ("# Reweighted 2026-10-29: 踩脚 and 踩鞋, at 1000 from the daily action phrases of "
                  "curated_daily_phrases.tsv, by the rules of the 才 words of 2026-10-28 (the tier of their "
                  "occurrences as words in the general text, 304 and 8); 才叫 and 才写 (3,190 and 143), which "
                  "those rules had put one below them at 999, take their own tiers in the 才 blocks (600 and 200).")
CAIJIAO = [('caijiao', '踩脚', '踩腳', 400), ('caixie', '踩鞋', '踩鞋', 80)]


class DailyCaiZhiWordsTests(unittest.TestCase):
    def test_blocks(self):
        for group, header in HEADERS.items():
            rows = block(header)
            self.assertEqual(SIZES[group], len(rows), group)
            self.assertEqual({"exact_rank_no_contains"}, {row[4] for row in rows}, group)
        self.assertEqual(len(ROWS), len({(row[0], row[1]) for row in ROWS}))
        texts = {row[1] for row in ROWS}
        for word in REQUESTED:
            self.assertIn(word, texts, word)
        forced = block(HEADER_FORCED)
        self.assertEqual(sorted(tuple(row) for row in FORCED), sorted(row[:4] for row in forced))
        self.assertEqual({"exact_rank"}, {row[4] for row in forced})

    def test_cai_words_above_cai_jiao_and_cai_xie(self):
        self.assertEqual(sorted(CAIJIAO), sorted(tuple(row[:4]) for row in block(HEADER_CAIJIAO)))
        self.assertEqual({"exact_rank"}, {row[4] for row in block(HEADER_CAIJIAO)})
        weights = {(row[0], row[1]): row[3] for row in ROWS}
        self.assertEqual(600, weights[("caijiao", "才叫")])
        self.assertEqual(200, weights[("caixie", "才写")])
        for index, variant in enumerate(("sc", "tc"), 1):
            rows = read_rows(f"dict_clean_{variant}.txt")
            for pinyin, word, other in (("caijiao", ("才叫", "才叫"), ("踩脚", "踩腳")),
                                        ("caixie", ("才写", "才寫"), ("踩鞋", "踩鞋"))):
                self.assertGreater(int(rows[(pinyin, word[index - 1])][0]),
                                   int(rows[(pinyin, other[index - 1])][0]), (variant, pinyin))

    def test_head_and_one_character(self):
        for pinyin, sc, tc, _weight in ROWS:
            self.assertEqual(2, len(sc), sc)
            self.assertIn(sc[0], "才只", sc)
            self.assertEqual(sc[0], tc[0], sc)
            self.assertTrue(pinyin.startswith({"才": "cai", "只": "zhi"}[sc[0]]), pinyin)
            self.assertNotIn("'", pinyin)

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
