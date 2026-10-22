"""Everyday words of 2026-10-22, the second batch (the user's 第一站 to 第十站, 两站,
四站 to 十站, 高危, 高延时, 低延时 and 续期, and more of their kinds): stops of a
ride or a journey, levels of a risk, latency and renewals. Weighted as
test_daily_suo_bijiao_phrases (occurrences where the word is no part of a
longer dictionary word, nor before one that its last character begins); a
requested word stays under a word of its key more than one and a half times
as frequent (八站 under 霸占, 十站 under 实战, 高危 under 高位). Existing words at
an import weight on the keys of the batch are weighted by the same rules (三站,
到站, 低风险), so that a new word does not go above a commoner one whose weight
says nothing (基站 above 几站, 中尉 above 中危, 誓言 above 时延); 中衛 was missing
from the traditional dictionary and is added there."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from test_daily_whitespace_phrases import read_rows
from test_daily_cuo_xiu_sha_shui_phrases import block, keys

HEADER_COMMON = "# Everyday words, 2026-10-22 (stations, risk levels, latency, renewals), the more frequent ones:"
HEADER_LESS = "# Everyday words, 2026-10-22 (stations, risk levels, latency, renewals), the less frequent ones"
HEADER_FORCED = "# Existing words on the keys of the batch of 2026-10-22 (stations, risk levels, latency, renewals):"
REQUESTED = ("第一站 第二站 第三站 第四站 第五站 第六站 第七站 第八站 第九站 第十站 两站 四站 五站 六站 七站 "
             "八站 九站 十站 高危 高延时 低延时 续期").split()
# (pinyin, word, other): word above other on the key
ABOVE = [("jizhan", "基站", "几站"), ("zhongwei", "中尉", "中危"), ("diwei", "地委", "低危"),
         ("shiyan", "誓言", "时延"), ("liangzhan", "两站", "粮站"),
         ("wuzhan", "五站", "坞站"), ("baozhan", "报站", "饱绽"),
         ("gaowei", "高危", "高维"), ("gaowei", "高危", "高位")]
BELOW = [("bazhan", "八站", "霸占"), ("shizhan", "十站", "实战"), ("sizhan", "四站", "死战"),
         ("diwei", "低危", "地位"), ("jizhan", "几站", "激战")]
FORCED = {
    ("sanzhan", "三站"): 400,
    ("daozhan", "到站"): 600,
    ("chuzhan", "出站"): 739,
    ("baozhan", "报站"): 400,
    ("difengxian", "低风险"): 600,
    ("jizhan", "基站"): 999,
    ("jizhan", "机战"): 200,
    ("zhongwei", "中尉"): 601,
    ("zhongwei", "众位"): 401,
    ("zhongwei", "中卫"): 600,
    ("diwei", "地委"): 601,
    ("diwei", "帝位"): 600,
    ("shiyan", "誓言"): 493,
}
# Reweighted words the traditional dictionary lacked: added with the contains flag.
TC_ADDED = {
    ("zhongwei", "中衛"): 600,
}
ROWS = tuple(row[:4] for row in block(HEADER_COMMON) + block(HEADER_LESS))


class DailyZhanGaoweiTests(unittest.TestCase):
    def test_blocks(self):
        common, less = block(HEADER_COMMON), block(HEADER_LESS)
        self.assertEqual(45, len(common))
        self.assertEqual(16, len(less))
        self.assertEqual({"exact_rank_no_contains"}, {row[4] for row in common + less})
        self.assertEqual(len(ROWS), len({(row[0], row[1]) for row in ROWS}))
        texts = {row[1] for row in ROWS}
        for word in REQUESTED:
            self.assertIn(word, texts, word)
        self.assertIn(("liangzhan", "两站", "兩站"), {row[:3] for row in ROWS})
        self.assertIn(("xuqi", "续期", "續期"), {row[:3] for row in ROWS})
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
