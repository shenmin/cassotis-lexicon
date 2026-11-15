"""Words of 2026-11-14: 核 as "check" before a verb (核验, 核校 read hejiao, 核发, 核批, 核减),
a numeral before 选 (二选, 三选, 二选一, 七选五, 多选), 小 before a noun, the small thing (小鱼, 小园,
小草, 小碗), and a verb before 在, where something is or ends up (沉在, 吃在, 玩在, 爱在, 偏在, 长在
read zhangzai, 记在, 刻在). The user: "再加一批词吧：核验、核校（jiao）、二选、三选、小鱼、小园、沉在、
吃在、玩在、爱在、偏在、……". Words of the families at an import weight (住在, 挂在, 活在 at 10, 小船,
小鼠) are weighted anew. Weighted as test_daily_zhefeng_words (occurrences where the word is no part
of a longer dictionary word, nor before one that its last character begins, nor after one that its
first character ends); a word stays under every more frequent word of its key."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from test_daily_whitespace_phrases import read_rows
from test_daily_cuo_xiu_sha_shui_phrases import block

HEADERS = {'common': '# Everyday words, 2026-11-14, the more frequent ones: 核 as "check" before a verb (the user\'s 核验 and 核校 read hejiao; 核发, 核减, 核保, 核拨, 核载), a numeral before 选 (the user\'s 二选 and 三选; 二选一, 三选一, 七选五, 多选), 小 before a noun (the user\'s 小鱼 and 小园; 小草, 小兔, 小猪, 小碗, 小窝) and a verb before 在 (the user\'s 沉在, 吃在, 玩在, 爱在 and 偏在; 生在, 长在 read zhangzai, 记在, 刻在, 泡在), weighted by the general text as the batches before.', 'less': '# Everyday words, 2026-11-14, the less frequent ones (核批, 核审, 核稿, 四选, 五选一, 双选, 小扇, 小凳, 小别, 小镜), by the same weights; 核扣, 核付, 核账, 多选一 and 六选三, which the general text seldom writes as words, at 2.'}
SIZES = {'common': 128, 'less': 30}
REQUESTED = ['核验', '核校', '二选', '三选', '小鱼', '小园', '沉在', '吃在', '玩在', '爱在', '偏在']
HEADER_FORCED = '# Weighted anew on 2026-11-14: import-weight words of the families and of their keys that the general text holds far more often than their weights say (住在, 挂在, 躲在, 跟在, 贴在, 小船, 小岛, 小鼠, 小费, 肖像, 旱灾, 盆栽; 小羊, which only the traditional dictionary had).'
FORCED = [('xiaoyang', '小羊', '小羊', 279), ('anzai', '按在', '按在', 600), ('baozai', '抱在', '抱在', 600), ('chanzai', '缠在', '纏在', 400), ('chuaizai', '揣在', '揣在', 200), ('couzai', '凑在', '湊在', 200), ('daozai', '倒在', '倒在', 600), ('dianzai', '垫在', '墊在', 400), ('diaozai', '掉在', '掉在', 600), ('dingzai', '钉在', '釘在', 599), ('dingzai', '顶在', '頂在', 400), ('dizai', '滴在', '滴在', 126), ('duozai', '躲在', '躲在', 600), ('duzai', '赌在', '賭在', 200), ('fuzai', '浮在', '浮在', 601), ('fuzai', '附在', '附在', 602), ('genzai', '跟在', '跟在', 600), ('guazai', '挂在', '掛在', 803), ('guizai', '跪在', '跪在', 600), ('hanzai', '焊在', '焊在', 200), ('huozai', '活在', '活在', 268), ('lianzai', '连在', '連在', 600), ('lizai', '立在', '立在', 600), ('maizai', '埋在', '埋在', 600), ('panzai', '盘在', '盤在', 400), ('paozai', '抛在', '拋在', 601), ('penzai', '喷在', '噴在', 600), ('piaozai', '漂在', '漂在', 400), ('pozai', '泼在', '潑在', 200), ('qizai', '骑在', '騎在', 600), ('quanzai', '蜷在', '蜷在', 200), ('raozai', '绕在', '繞在', 400), ('shengzai', '胜在', '勝在', 600), ('shouzai', '守在', '守在', 600), ('shuaizai', '摔在', '摔在', 400), ('taozai', '套在', '套在', 600), ('tiezai', '贴在', '貼在', 600), ('yinzai', '印在', '印在', 600), ('zazai', '砸在', '砸在', 600), ('zhuangzai', '撞在', '撞在', 280), ('zhuzai', '住在', '住在', 999), ('xuanzai', '悬在', '懸在', 279), ('kouzai', '扣在', '扣在', 600), ('xiaochuan', '小船', '小船', 439), ('xiaodao', '小岛', '小島', 600), ('xiaodao', '小刀', '小刀', 296), ('xiaoshu', '小树', '小樹', 602), ('xiaoshu', '小鼠', '小鼠', 100), ('xiaotan', '小摊', '小攤', 956), ('xiaojie', '小街', '小街', 584), ('xiaojing', '小径', '小徑', 601), ('xiaogu', '小鼓', '小鼓', 134), ('xiaohuo', '小火', '小火', 601), ('xiaohuo', '小伙', '小夥', 600), ('xiaobu', '小步', '小步', 600), ('xiaozhong', '小众', '小眾', 99), ('xiaoqian', '小钱', '小錢', 600), ('xiaofei', '小费', '小費', 600), ('xiaoxiang', '肖像', '肖像', 600), ('hanzai', '旱灾', '旱災', 601), ('penzai', '盆栽', '盆栽', 601), ('xiaohu', '销户', '銷戶', 279), ('xiaoshu', '消暑', '消暑', 601), ('xiaojing', '孝经', '孝經', 600), ('hejia', '阖家', '闔家', 533), ('xiaoqi', '消气', '消氣', 279), ('xiaoxiang', '小项', '小項', 235), ('heshen', '和珅', '和珅', 600), ('heshen', '河神', '河神', 400)]
ROWS = tuple(row[:4] for header in HEADERS.values() for row in block(header))


class DailyHeyanWordsTests(unittest.TestCase):
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
        keys = {(row[0], row[1]) for row in ROWS + tuple(FORCED)}
        # Readings by the meaning: 核校 checks (jiao, the user), 长在 grows, 粘在 sticks, 冲在, 倒在, 难在.
        for pinyin, word in (("hejiao", "核校"), ("zhangzai", "长在"), ("zhanzai", "粘在"), ("zhazai", "扎在"),
                             ("mozai", "抹在"), ("chongzai", "冲在"), ("daozai", "倒在"), ("nanzai", "难在"),
                             ("hejia", "核价"), ("hezai", "核载")):
            self.assertIn((pinyin, word), keys)
        self.assertNotIn(("hexiao", "核校"), keys)

    def test_order_on_shared_keys(self):
        # 核验 just above 合眼, 挂在 above 挂载 (the general text writes them more often); 住在 under 主宰,
        # 小鱼 under 小雨, 活在 under 火灾; 小鼠 far under 小数 (the user: 小数 first on xiaoshu, not by frequency
        # alone).
        for variant, index in (("sc", 0), ("tc", 1)):
            rows = read_rows(f"dict_clean_{variant}.txt")
            for pinyin, pair in (("heyan", (("核验", "核驗"), ("合眼", "合眼"))),
                                 ("guazai", (("挂在", "掛在"), ("挂载", "掛載"))),
                                 ("zhuzai", (("主宰", "主宰"), ("住在", "住在"))),
                                 ("xiaoyu", (("小雨", "小雨"), ("小鱼", "小魚"))),
                                 ("huozai", (("火灾", "火災"), ("活在", "活在"))),
                                 ("xiaoshu", (("小数", "小數"), ("小鼠", "小鼠")))):
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
