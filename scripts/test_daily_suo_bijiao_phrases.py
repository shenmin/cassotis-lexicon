"""Everyday words of 2026-10-20, second batch (the user's 所花、所批、所交、比较烦、
树状、出字、哐哐、咣咣、不耗、没数, and more of their kinds; then 谁都、啥叫、啥是): 所 +
a verb, 比较 + an adjective of one character and 烦 after a degree word, shapes X状,
typing words, sounds, 不耗 and 没数, 谁 before a word (read shui and shei) and 啥. Weighted as test_daily_bu_zai_qi_phrases (occurrences
where the word is no part of a longer dictionary word, and here nor before
one that its last character begins: 所花 not in 所花费); of new homophones a
requested word goes first unless the other is three times as frequent (所花
above 所画, 所交 above 所教); 所作 stays under 所做. Existing words at an
import weight on the keys of the batch are weighted by the same rules (所见
above the new 所建, 光光 above 咣咣, 水饺 above 谁叫); 所见, 行状, 嘤嘤嘤, 水饺 and 税官
were missing from the traditional dictionary and are added there."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from test_daily_whitespace_phrases import read_rows
from test_daily_cuo_xiu_sha_shui_phrases import block, keys

HEADER_COMMON = "# Everyday words, 2026-10-20 (second batch), the more frequent ones:"
HEADER_LESS = "# Everyday words, 2026-10-20 (second batch), the less frequent ones"
HEADER_FORCED = "# Existing words at an import weight (1 to 84) on the keys of the second batch"
REQUESTED = "所花 所批 所交 比较烦 树状 出字 哐哐 咣咣 不耗 没数 谁都 啥叫 啥是".split()
# (pinyin, word, other): word above other on the key
ABOVE = [("suohua", "所花", "所画"), ("suojiao", "所交", "所教"), ("suojian", "所见", "所建"),
         ("shuzhuang", "树状", "树桩"), ("guangguang", "光光", "咣咣"), ("suoshou", "所受", "所收"),
         ("mazi", "麻子", "码字"), ("shuijiao", "水饺", "谁叫"),
         ("shuidou", "谁都", "水痘"), ("shashi", "啥是", "啥事")]
BELOW = [("suozuo", "所作", "所做"), ("shuzhuang", "树状", "梳妆"), ("guangguang", "咣咣", "逛逛"),
         ("kuangkuang", "哐哐", "框框"), ("chuzi", "出字", "出自"), ("buhao", "不耗", "不好"),
         ("meishu", "没数", "美术"), ("guanzhuang", "灌装", "罐装"), ("guanzhuang", "管状", "灌装")]
FORCED = {
    ("suozhi", "所指"): 600,
    ("xuzhuang", "絮状"): 600,
    ("xianzhuang", "线状"): 600,
    ("shuzhuangtu", "树状图"): 400,
    ("dada", "哒哒"): 401,
    ("sousou", "嗖嗖"): 401,
    ("honghong", "轰轰"): 400,
    ("gugu", "咕咕"): 214,
    ("gudu", "咕嘟"): 200,
    ("pipa", "噼啪"): 307,
    ("gezhi", "咯吱"): 200,
    ("baji", "吧唧"): 330,
    ("pada", "啪嗒"): 703,
    ("hulu", "呼噜"): 600,
    ("aoao", "嗷嗷"): 600,
    ("wawa", "哇哇"): 600,
    ("wuwu", "呜呜"): 600,
    ("miemie", "咩咩"): 400,
    ("gege", "咯咯"): 2,
    ("yingyingying", "嘤嘤嘤"): 200,
    ("hengheng", "哼哼"): 600,
    ("buxiang", "不响"): 199,
    ("buwen", "不稳"): 600,
    ("xinlimeishu", "心里没数"): 80,
    ("shashihou", "啥时候"): 600,
    ("weisha", "为啥"): 600,
    ("guangguang", "光光"): 559,
    ("shuzhuang", "树桩"): 600,
    ("suojian", "所见"): 601,
    ("suoshou", "所受"): 601,
    ("suohao", "锁好"): 401,
    ("suozai", "缩在"): 279,
    ("xuanzi", "选自"): 999,
    ("shasha", "傻傻"): 443,
    ("honghong", "红红"): 600,
    ("sisi", "丝丝"): 559,
    ("pengpeng", "碰碰"): 279,
    ("pengpeng", "怦怦"): 278,
    ("dingding", "定定"): 401,
    ("yingying", "硬硬"): 80,
    ("xingzhuang", "性状"): 538,
    ("guanzhuang", "灌装"): 479,
    ("gudu", "古都"): 600,
    ("didi", "地底"): 559,
    ("mazi", "麻子"): 601,
    ("mazi", "码子"): 200,
    ("buhao", "补好"): 401,
    ("chuzi", "厨子"): 600,
    ("chuzi", "处子"): 400,
    ("pipa", "劈啪"): 200,
    ("sousou", "飕飕"): 400,
    ("buji", "簿记"): 278,
    ("buji", "簿籍"): 80,
    ("buji", "不吉"): 279,
    ("lizhuang", "力壮"): 200,
    ("wuwu", "唔唔"): 200,
    ("wuwu", "无物"): 558,
    ("wuwu", "戊午"): 559,
    ("xingzhuang", "行状"): 400,
    ("gongzhuang", "供状"): 80,
    ("yingying", "荧荧"): 200,
    ("dingding", "定鼎"): 400,
    ("baji", "靶机"): 200,
    ("shashi", "砂石"): 783,
    ("shashi", "沙石"): 782,
    ("shuibi", "水笔"): 600,
    ("shuiguan", "税官"): 561,
    ("shuijiao", "水饺"): 600,
    ("shuiqu", "水渠"): 279,
    ("shuixiang", "水乡"): 601,
    ("shuiyao", "水妖"): 200,
    ("shuizai", "水灾"): 600,
    ("sharen", "砂仁"): 600,
    ("weisha", "纬纱"): 400,
    ("dingding", "钉钉"): 415,
    ("shuzhuang", "梳妆"): 930,
}
# Reweighted words the traditional dictionary lacked: added with the contains flag.
TC_ADDED = {
    ("yingyingying", "嚶嚶嚶"): 200,
    ("suojian", "所見"): 601,
    ("xingzhuang", "行狀"): 400,
    ("shuiguan", "稅官"): 561,
    ("shuijiao", "水餃"): 600,
}
ROWS = tuple(row[:4] for row in block(HEADER_COMMON) + block(HEADER_LESS))


class DailySuoBijiaoTests(unittest.TestCase):
    def test_blocks(self):
        common, less = block(HEADER_COMMON), block(HEADER_LESS)
        self.assertGreater(len(common), 130)
        self.assertGreater(len(less), 50)
        self.assertEqual({"exact_rank_no_contains"}, {row[4] for row in common + less})
        self.assertEqual(len(ROWS), len({(row[0], row[1]) for row in ROWS}))
        texts = {row[1] for row in ROWS}
        for word in REQUESTED:
            self.assertIn(word, texts, word)
        self.assertIn(("suoqian", "所签", "所簽", 400), ROWS)
        # 谁 read shui and shei.
        for word in ("谁都", "谁也", "谁能"):
            readings = {row[0] for row in ROWS if row[1] == word}
            self.assertEqual({"shei", "shui"}, {p for p in ("shei", "shui") if any(p in r for r in readings)}, word)
        self.assertTrue(all("著" not in row[2] and "爲" not in row[2] for row in ROWS))

    def test_order(self):
        rows = keys("sc")
        for pinyin, word, other in ABOVE:
            self.assertGreater(rows[pinyin][word], rows[pinyin][other], word)
        for pinyin, word, other in BELOW:
            self.assertLess(rows[pinyin][word], rows[pinyin][other], word)
        # No weight of the batch ties with another word of its key.
        by_key = {}
        for (pinyin, text), fields in read_rows("dict_clean_sc.txt").items():
            by_key.setdefault(pinyin, {})[text] = int(fields[0])
        for pinyin, word, _tc, weight in ROWS + tuple((p, w, "", v) for (p, w), v in FORCED.items()):
            others = [text for text, value in by_key[pinyin].items() if text != word and value == weight]
            self.assertFalse(others, (pinyin, word))

    def test_reweighted_words(self):
        forced = block(HEADER_FORCED)
        self.assertEqual({"exact_rank"}, {row[4] for row in forced})
        self.assertEqual(FORCED, {(row[0], row[1]): row[3] for row in forced})
        text = (ROOT / "manifests/curated_daily_supplement_phrases.tsv").read_text(encoding="utf-8")
        for (_pinyin, word), _weight in FORCED.items():
            self.assertFalse([line for line in text.splitlines()
                              if line.split("\t")[0] == word and line.split("\t")[2:3] == ["0.01"]], word)
        clean = read_rows("dict_clean_sc.txt")
        for (pinyin, word), weight in FORCED.items():
            self.assertEqual(str(weight), clean[(pinyin, word)][0], word)
        tc_rows = read_rows("dict_clean_tc.txt")
        for key, weight in TC_ADDED.items():
            self.assertEqual([str(weight)], tc_rows[key], key)
        # The traditional weights aligned with the simplified ones.
        self.assertEqual("415", tc_rows[("dingding", "釘釘")][0])
        self.assertEqual("930", tc_rows[("shuzhuang", "梳妝")][0])

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
