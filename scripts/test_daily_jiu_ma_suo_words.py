"""Words of 2026-11-01: 就X, X吗, 所X, X过, X中, 借X, 有X / 无X, 反X and a
few more. The user: "再添加一批词（包括拓展一些）：就放、就弄、就还（huan）、就丢、就甩、
就睡、就起、就醒、就恨、就爱、就带、就戴、就穿、就脱、就奔、就跑、就走、就趴、就飞、……、
弄吗、丢吗、甩吗、睡吗、起吗、爱吗、恨吗、带吗、穿吗、戴吗、脱吗、飞吗、发吗、……、所限、
所恨、所弄、所丢、会中、没中、有中、有车、借来、借去、有房、无贷、有贷、多词、反升、进过、
恨过、戴过、弄过、小蜜、小秘、……". More of each kind from the pairs of the
general text the dictionary lacked, reviewed by hand (pieces of longer words
and readings the key cannot tell left out; 就还 is jiu huan, as the user
wrote). Weighted as test_daily_suo_bijiao_phrases (occurrences where the word
is no part of a longer dictionary word, nor before one that its last
character begins, nor after one that its first character ends)."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from test_daily_whitespace_phrases import read_rows
from test_daily_cuo_xiu_sha_shui_phrases import block

HEADERS = {'common': "# Everyday words, 2026-11-01, the more frequent ones: 就 before a verb of one character (就放, 就弄, 就还, 就丢, 就甩, 就睡, 就起, 就醒, 就恨, 就爱, 就带, 就戴, 就穿, 就脱, 就奔, 就跑, 就走, 就趴, 就飞: the user's examples, 就还 read jiu huan; 就找, 就哭, 就停, 就住), a verb or adjective of one character before 吗 (弄吗, 丢吗, 甩吗, 睡吗, 起吗, 爱吗, 恨吗, 带吗, 穿吗, 戴吗, 脱吗, 飞吗, 发吗; 说吗, 忙吗, 贵吗), 所 before a verb (所限, 所恨, 所弄, 所丢; 所迫, 所言, 所购), a verb before 过 (进过, 恨过, 戴过, 弄过; 救过, 离过, 生过), 中 read zhong as hit or won (会中, 没中, 有中; 能中), 借 before a direction, a result or what is lent (借来, 借去; 借到, 借车), 有, 无 and 没 before a house, a car or a debt (有车, 有房, 无贷, 有贷; 无房, 没车, 有房贷), 反 before a rise or fall (反升; 反跌, 反诈), 多词, 小蜜 and 小秘 (多字); 上过, 高过 and 就多, which the dictionary had only as pairs of single characters (上|过 and the like) that a word of the batch went above; low on their key, words that took benchmark cases from a word of their key, such as 痛吗, 炸过, 所著, 无房 and 就多; the pairs of the general text that the dictionary lacked, reviewed by hand (pieces of longer words such as 就可 of 就可以 and 所措 of 不知所措, readings the key cannot tell left out). Weighted as the blocks of 2026-10-29 (occurrences where the word is no part of a longer dictionary word, nor before one that its last character begins, nor after one that its first character ends); a word stays under every more frequent word of its key, an import's weight included.", 'less': '# Everyday words, 2026-11-01, the less frequent ones (就醉, 就饿, 就躺, 冷吗, 饱吗, 签吗, 所骗, 所诱, 吻过, 醉过, 才中, 借走, 有债, 反涨, 少字), by the same weights.'}
SIZES = {'common': 229, 'less': 229}
REQUESTED = ['就放', '就弄', '就还', '就丢', '就甩', '就睡', '就起', '就醒', '就恨', '就爱', '就带', '就戴', '就穿', '就脱', '就奔', '就跑', '就走', '就趴', '就飞', '弄吗', '丢吗', '甩吗', '睡吗', '起吗', '爱吗', '恨吗', '带吗', '穿吗', '戴吗', '脱吗', '飞吗', '发吗', '所限', '所恨', '所弄', '所丢', '会中', '没中', '有中', '有车', '借来', '借去', '有房', '无贷', '有贷', '多词', '反升', '进过', '恨过', '戴过', '弄过', '小蜜', '小秘']
HEADER_FORCED = "# Everyday words of 2026-11-01 the lexicon held at an import's weight, weighted as the blocks above (所爱, 抢过, 擦过, 尝过, 逃过, 借书, 借贷); and 接力, one above 竭力 again: with 借力 on the key the short choice no longer put it first."
FORCED = [('suoai', '所爱', '所愛', 600), ('qiangguo', '抢过', '搶過', 132), ('caguo', '擦过', '擦過', 400), ('changguo', '尝过', '嘗過', 600), ('taoguo', '逃过', '逃過', 600), ('jieshu', '借书', '借書', 600), ('jiedai', '借贷', '借貸', 600), ('jieli', '接力', '接力', 894)]
ROWS = tuple(row[:4] for header in HEADERS.values() for row in block(header))


class DailyJiuMaSuoWordsTests(unittest.TestCase):
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
        last = {"吗": ("嗎", "ma"), "过": ("過", "guo"), "中": ("中", "zhong")}
        first = {"就": ("就", "jiu"), "所": ("所", "suo"), "借": ("借", "jie"), "反": ("反", "fan"),
                 "有": ("有", "you"), "无": ("無", "wu"), "没": ("沒", "mei"), "多": ("多", "duo"),
                 "少": ("少", "shao"), "小": ("小", "xiao"),
                 # 接力, weighted above 竭力 again (the batch's 借力 had turned it below).
                 "接": ("接", "jie")}
        for pinyin, sc, tc, _weight in ROWS + tuple(row[:4] for row in FORCED):
            self.assertIn(len(sc), (2, 3), sc)
            self.assertNotIn("'", pinyin)
            if sc[-1] in last:
                self.assertEqual(last[sc[-1]][0], tc[-1], sc)
                self.assertTrue(pinyin.endswith(last[sc[-1]][1]), pinyin)
            else:
                self.assertIn(sc[0], first, sc)
                self.assertEqual(first[sc[0]][0], tc[0], sc)
                self.assertTrue(pinyin.startswith(first[sc[0]][1]), pinyin)
        self.assertIn(("jiuhuan", "就还"), {(row[0], row[1]) for row in ROWS + tuple(FORCED)})

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
