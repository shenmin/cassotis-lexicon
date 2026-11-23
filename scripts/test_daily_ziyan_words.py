"""Words of 2026-11-23: the user's 自研, 长训, 一单, 自究, 罪己, 没单, 零单, 两单, 三单, 四单, 五单, 六单,
七单, 八单, 九单, 十单, 二单 and 自戕, and their kinds: a numeral or a demonstrative before 单 (orders), verbs and
adjectives of orders before 单, 自 before a verb of the self and of what one does oneself, words of blaming oneself, and
a word of time or kind before 训. The user: "再帮我加一批词：自研、长(chang)训、一单、自究、罪己、没单、零单、两单、三单、四单、五单、
六单、七单、八单、九单、十单、二单、自戕、……". Words of the families' keys at an import weight are weighted anew. Weighted as
test_daily_wohen_words (occurrences where the word is no part of a longer dictionary word, nor before one that its last
character begins, nor after one that its first character ends); a word stays under every more frequent word of its
key."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from test_daily_whitespace_phrases import read_rows
from test_daily_cuo_xiu_sha_shui_phrases import block

HEADERS = {'common': "# Everyday words, 2026-11-23, the more frequent ones: the user's 自研, 长训, 一单, 自究, 罪己, 没单, 零单, 两单, 三单, 四单, 五单, 六单, 七单, 八单, 九单, 十单, 二单 and 自戕, and their kinds the lexicon lacked: a numeral or a demonstrative before 单 (几单, 每单, 万单), verbs and adjectives of orders before 单 (出单, 跟单, 签单, 抢单, 大单, 新单), 自 before a verb of the self and of what one does oneself (自纠, 自评, 自伤, 自产, 自提), words of blaming oneself (责己, 罪己诏) and a word of time or kind before 训 (实训, 参训, 内训, 冬训, 复训), weighted by the general text as the batches before; 三单, 签单, 自产 and 自伤 above a word of their key by everyday conversation, 自裁 above 资财 too; 七单 above 弃单, 自究 above 自疚 and 没单 above 昧旦 by hand, the user's words where the counts lie close or a literary word conversation never writes; 十单 between 实弹 and 市担.", 'less': '# Everyday words, 2026-11-23, the less frequent ones (好单, 散单, 千单, 整单, 改单, 漏单, 压单, 弃单, 加训, 夏训, 夜训, 停训, 自咎, 自训), by the same weights; words the general text seldom writes as words at 2 or below.'}
SIZES = {'common': 87, 'less': 69}
REQUESTED = ['自研', '长训', '一单', '自究', '罪己', '没单', '零单', '两单', '三单', '四单', '五单', '六单', '七单', '八单', '九单', '十单', '二单', '自戕']
HEADER_FORCED = "# Weighted anew on 2026-11-23: the words of the batch's keys at an import weight by the general text (资深, 资历, 飞弹, 定单, 零担, 放胆, 流弹, 扯蛋, 自贬, 滋肾, 子粒; 行迹 and 形迹 under 星级, which the traditional dictionary holds at 118), and 实弹 above 市担, which the general text writes 125 times as seldom."
FORCED = [('shidan', '实弹', '實彈', 900), ('chedan', '扯蛋', '扯蛋', 200), ('dingdan', '定单', '定單', 400), ('fangdan', '放胆', '放膽', 400), ('feidan', '飞弹', '飛彈', 600), ('lingdan', '零担', '零擔', 400), ('liudan', '流弹', '流彈', 200), ('xingji', '形迹', '形跡', 116), ('xingji', '行迹', '行跡', 117), ('zibian', '自贬', '自貶', 200), ('zili', '子粒', '子粒', 200), ('zili', '资历', '資歷', 219), ('zishen', '滋肾', '滋腎', 599), ('zishen', '资深', '資深', 600)]
ROWS = tuple(row[:4] for header in HEADERS.values() for row in block(header))


class DailyZiyanWordsTests(unittest.TestCase):
    def test_blocks(self):
        for group, header in HEADERS.items():
            rows = block(header)
            self.assertEqual(SIZES[group], len(rows), group)
            self.assertEqual({"exact_rank_no_contains"}, {row[4] for row in rows}, group)
        self.assertEqual(len(ROWS), len({(row[0], row[1]) for row in ROWS}))
        texts = {row[1] for row in ROWS} | {row[1] for row in FORCED}
        for word in REQUESTED:
            self.assertIn(word, texts, word)
        forced = block(HEADER_FORCED)
        self.assertEqual({"exact_rank"}, {row[4] for row in forced})
        self.assertEqual({row[:4] for row in FORCED}, {tuple(row[:4]) for row in forced})

    def test_kinds(self):
        for pinyin, sc, tc, _weight in ROWS + tuple(row[:4] for row in FORCED):
            self.assertIn(len(sc), (2, 3, 4), sc)
            self.assertEqual(len(sc), len(tc), sc)
            self.assertNotIn("'", pinyin)
        keys = {(row[0], row[1]) for row in ROWS + tuple(FORCED)}
        # Readings by the meaning: 长 of long (chang), 单 of orders (dan).
        for pinyin, word in (("changxun", "长训"), ("yidan", "一单"), ("liangdan", "两单"), ("shidan", "十单")):
            self.assertIn((pinyin, word), keys)

    def test_order(self):
        by_key = {}
        for (pinyin, text), fields in read_rows("dict_clean_sc.txt").items():
            by_key.setdefault(pinyin, {})[text] = int(fields[0])
        for pinyin, word, _tc, weight in ROWS + tuple(FORCED):
            self.assertEqual(weight, by_key[pinyin][word], word)
            others = [text for text, value in by_key[pinyin].items() if text != word and value == weight]
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
