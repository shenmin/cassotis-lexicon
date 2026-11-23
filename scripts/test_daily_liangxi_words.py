"""Words of 2026-11-19: the user's 都以, 我再, 单颗, 单科, 靓号, 靓女, 好靓, 很靓, 非常靓, 太细, 非常细, 挺细, 有点细,
稍细 and 列了, and their kinds: a degree word before 细, 粗 and 靓 (and before 稀, 亮 and 凉, the other common readings of
those keys), 单 before a classifier, 都 before a preposition, a pronoun before 再, 列 before a complement, 靓 before a
noun. The user: "都（dou）以、我再、单颗、单科、靓（liang）号、靓（liang）女、好靓（liang）、很靓（liang）、非常靓（liang）、靓（liang）
仔（zai）、太细、非常细、挺细、有点细、稍细、列了、我再、……；另外，处理一个权重问题，wozai的权重，“窝在”应该小于“我在”、“我再”".
Words of the families' keys at an import weight are weighted anew, and 窝在 goes under 我在 and 我再. Weighted as
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

HEADERS = {'common': "# Everyday words, 2026-11-19, the more frequent ones: the user's 都以, 我再, 单颗, 单科, 靓号, 靓女, 好靓, 很靓, 非常靓, 太细, 非常细, 挺细, 有点细, 稍细 and 列了, and their kinds the lexicon lacked: a degree word before 细, 粗 and 靓 and before 稀, 亮 and 凉, the other common readings of those keys (较细, 越亮, 偏凉), 单 before a classifier (单笔, 单场, 单根), 都 before a preposition (都按, 都由, 都为), a pronoun before 再 (我们再, 他再), 列 before a complement (列在, 列好) and 靓 before a noun (靓汤, 靓照), weighted by the general text as the batches before; 我再, 太细, 越细 and 单片 above a word of their key by everyday conversation; 他再, 她再 and 它再 below 踏在 at 4 to 2, since higher they took 他在 and 她在 of long sentences; 单颗 above 弹壳 and 有点细 above 有点稀 by hand, the user's words where the counts lie close.", 'less': '# Everyday words, 2026-11-19, the less frequent ones (好细, 真细, 这么粗, 有点粗, 单袋, 单局, 都凭, 列清楚, 靓妹, 靓车, 咱再), by the same weights; 有点稀, 超亮, 最凉, 靓号码 and other words the general text seldom writes as words, at 2 or below.'}
SIZES = {'common': 108, 'less': 154}
REQUESTED = ['都以', '我再', '单颗', '单科', '靓号', '靓女', '好靓', '很靓', '非常靓', '太细', '非常细', '挺细', '有点细', '稍细', '列了']
HEADER_FORCED = "# Weighted anew on 2026-11-19: 窝在 under 我在 and 我再 (the user), and the words of the batch's keys at an import weight by the general text (但也, 两级, 两届, 量级, 蛋壳, 痘印, 很细, 凉凉, 过膝 by everyday conversation), 弹壳 under 单颗."
FORCED = [('wozai', '窝在', '窩在', 501), ('danbao', '蛋包', '蛋包', 200), ('dandao', '胆道', '膽道', 600), ('danji', '单极', '單極', 33), ('danke', '弹壳', '彈殼', 398), ('danke', '蛋壳', '蛋殼', 599), ('danlun', '单论', '單論', 400), ('danye', '但也', '但也', 600), ('douyin', '痘印', '痘印', 599), ('douyin', '逗引', '逗引', 200), ('douyou', '豆油', '豆油', 599), ('guoxi', '国玺', '國璽', 183), ('guoxi', '过膝', '過膝', 400), ('henxi', '很细', '很細', 600), ('jiaoxi', '教习', '教習', 128), ('jixi', '及膝', '及膝', 102), ('liangbao', '凉薄', '涼薄', 400), ('liangji', '两级', '兩級', 600), ('liangji', '良机', '良機', 598), ('liangji', '量级', '量級', 599), ('liangjie', '两届', '兩屆', 600), ('liangjie', '梁洁', '梁潔', 200), ('liangliang', '两两', '兩兩', 600), ('liangliang', '亮亮', '亮亮', 598), ('liangliang', '凉凉', '涼涼', 599), ('liangliang', '晾凉', '晾涼', 597), ('liangmei', '两枚', '兩枚', 600), ('liangpian', '两片', '兩片', 439), ('liangshan', '两扇', '兩扇', 457), ('liangyi', '两仪', '兩儀', 488), ('liangyi', '凉意', '涼意', 489), ('liangyi', '晾衣', '晾衣', 399), ('liangyi', '良医', '良醫', 400), ('liezhe', '咧着', '咧著', 400)]
ROWS = tuple(row[:4] for header in HEADERS.values() for row in block(header))


class DailyLiangxiWordsTests(unittest.TestCase):
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
        # Readings by the meaning: 靓 of good-looking (liang), 都 of all (dou), 了 of completion (le).
        for pinyin, word in (("lianghao", "靓号"), ("liangnv", "靓女"), ("haoliang", "好靓"), ("henliang", "很靓"),
                             ("feichangliang", "非常靓"), ("douyi", "都以"), ("liele", "列了")):
            self.assertIn((pinyin, word), keys)

    def test_wozai(self):
        # The user: 窝在 under 我在 and 我再, in both variants; still above 握在 and 卧在, which the general text and
        # everyday conversation write less often.
        for variant in ("sc", "tc"):
            rows = read_rows(f"dict_clean_{variant}.txt")
            weight = {text: int(fields[0]) for (pinyin, text), fields in rows.items() if pinyin == "wozai"}
            wo, zai, nest, hold = ("我在", "我再", "窝在", "握在") if variant == "sc" else ("我在", "我再", "窩在", "握在")
            self.assertGreater(weight[wo], weight[zai], variant)
            self.assertGreater(weight[zai], weight[nest], variant)
            self.assertGreater(weight[nest], weight[hold], variant)

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
