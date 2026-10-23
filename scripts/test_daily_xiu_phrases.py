"""Everyday words of 2026-10-23 (the user's 先修, 别修, 早修, 晚修, 早休, 晚休 and
灵修, and more of their kinds): 修 "repair" after an adverb or a modal and with
its result, self-study at school, spiritual practice, and 休 "rest". Weighted
as test_daily_suo_bijiao_phrases (occurrences where the word is no part of a
longer dictionary word, nor before one that its last character begins, nor
after one that its first character ends); a requested word leads a place name
it is more frequent than (晚修 above 万秀) and stays under a commoner word of
its key (灵修 under 领袖, 晚休 under 万秀). Existing words of the same kinds at
an import weight are weighted by the same rules (修满, 修业, 修士, 修课, 闭关修炼,
休业, 休庭, 半退休); 在修 stays a zai fragment at 1 and 双修 at its import
weight (at 183 it went above 双休), and the traditional dictionary gets 雙休."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from test_daily_whitespace_phrases import read_rows
from test_daily_cuo_xiu_sha_shui_phrases import block, keys

HEADER_COMMON = "# Everyday words, 2026-10-23 (修 and 休), the more frequent ones:"
HEADER_LESS = "# Everyday words, 2026-10-23 (修 and 休), the less frequent ones"
HEADER_FORCED = "# Existing words of the kinds of the batch of 2026-10-23 (修 and 休) at an import weight"
REQUESTED = "先修 别修 早修 晚修 早休 晚休 灵修".split()
# (pinyin, word, other): word above other on the key
ABOVE = [("wanxiu", "晚修", "万秀"), ("tongxiu", "同修", "铜锈"), ("kuxiu", "苦修", "枯朽"),
         ("zaoxiu", "早修", "早休"), ("xiuwan", "修完", "休完"), ("xiaoxiu", "小修", "小休"),
         ("xiuye", "修业", "休业")]
BELOW = [("lingxiu", "灵修", "领袖"), ("wanxiu", "晚休", "万秀"), ("shuangxiu", "双修", "双休"),
         ("gongxiu", "共修", "公休"), ("yuexiu", "月休", "越秀"), ("xiuke", "修课", "休克"),
         ("xiushi", "修士", "修饰"), ("meixiu", "没休", "没修"), ("yixiu", "已休", "已修"),
         ("jingxiu", "精修", "竞秀"), ("jingxiu", "静修", "精修"), ("buxiu", "补修", "补休"),
         ("baoxiu", "包修", "保修"), ("jianxiu", "兼修", "检修"), ("jianxiu", "剑修", "兼修"),
         ("zhengxiu", "正修", "整修"), ("haixiu", "还修", "害羞"), ("xiuxiu", "修修", "咻咻")]
FORCED = {
    ("xiuman", "修满"): 600,
    ("xiuke", "修课"): 279,
    ("xiuye", "修业"): 600,
    ("xiushi", "修士"): 600,
    ("biguanxiulian", "闭关修炼"): 200,
    ("xiuye", "休业"): 200,
    ("xiuting", "休庭"): 200,
    ("bantuixiu", "半退休"): 200,
    ("shuangxiu", "双休"): 184,
}
# Reweighted words the traditional dictionary lacked: added with the contains flag.
TC_ADDED = {
    ("shuangxiu", "雙休"): 184,
}
ROWS = tuple(row[:4] for row in block(HEADER_COMMON) + block(HEADER_LESS))


class DailyXiuTests(unittest.TestCase):
    def test_blocks(self):
        common, less = block(HEADER_COMMON), block(HEADER_LESS)
        self.assertEqual(42, len(common))
        self.assertEqual(23, len(less))
        self.assertEqual({"exact_rank_no_contains"}, {row[4] for row in common + less})
        self.assertEqual(len(ROWS), len({(row[0], row[1]) for row in ROWS}))
        texts = {row[1] for row in ROWS}
        for word in REQUESTED:
            self.assertIn(word, texts, word)
        self.assertIn(("lingxiu", "灵修", "靈修"), {row[:3] for row in ROWS})
        self.assertIn(("daxiaozhou", "大小周", "大小週"), {row[:3] for row in ROWS})
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
