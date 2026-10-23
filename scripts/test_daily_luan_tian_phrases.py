"""Everyday words of 2026-10-22, the third batch (the user's 竞争集, 填好, 天好, 填完,
乱拼, 乱改, 乱凑, 乱做, 乱作, 乱弄, 乱交, 乱唱, 乱舔, 乱加, 乱扣, 乱开, 乱灌, 乱关, 乱管, 乱喊 and
乱下, 后端 above 后段, 都该, 都学, 都开, 都关, 都跑, 都好, 都坏, 都杀, 都傻, 都笨, 都棒, 都帮,
都跪, 都舔 and 都打, and more of their kinds): sets of cases, filling in, the
weather, doing a thing any which way, and 都 (dou) before a verb or an
adjective. Weighted as test_daily_suo_bijiao_phrases
(occurrences where the word is no part of a longer dictionary word, nor
before one that its last character begins, nor after one that its first
character ends); a requested word leads a place name or an archaic word it
is more frequent than (填完 above 田湾, 乱加 above 銮驾) and stays under a
commoner word of its key (乱交 under 乱叫). Existing words at an import weight
on the keys of the batch are weighted by the same rules (验证集, 测试集, 乱摸,
瞎扯; 瞎编 stays at 1, and the traditional dictionary gets it at 1), and 后端 goes above 后段 (the user's word); 乱骂 stays under 乱麻 (an import weight, but the commoner word),
乱倒 just under 乱道 (above it the clause 方寸不乱道 lost its draft), and
乱想 is held at 2 (at its weight it went above 乱象 without a context)."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from test_daily_whitespace_phrases import read_rows
from test_daily_cuo_xiu_sha_shui_phrases import block, keys

HEADER_COMMON = "# Everyday words, 2026-10-22, the third batch (sets of cases, filling in, the weather, doing a thing any which way), the more frequent ones:"
HEADER_LESS = "# Everyday words, 2026-10-22, the third batch (sets of cases, filling in, the weather, doing a thing any which way), the less frequent ones"
HEADER_FORCED = "# Existing words on the keys of the batch of 2026-10-22, the third (sets of cases, filling in, doing a thing any which way):"
REQUESTED = ("竞争集 填好 天好 填完 乱拼 乱改 乱凑 乱做 乱作 乱弄 乱交 乱唱 乱舔 乱加 乱扣 乱开 乱灌 乱关 "
             "乱管 乱喊 乱下 都该 都学 都开 都关 都跑 都好 都坏 都杀 都傻 都笨 都棒 都帮 都跪 都舔 都打").split()
# (pinyin, word, other): word above other on the key
ABOVE = [("houduan", "后端", "后段"), ("douhao", "都好", "逗号"), ("dougai", "都改", "都该"),
         ("doushi", "斗士", "都试"), ("tianhao", "填好", "天好"), ("tianwan", "填完", "田湾"), ("luanjia", "乱加", "銮驾"),
         ("luanma", "乱麻", "乱骂"), ("luanmo", "乱摸", "卵模")]
BELOW = [("luanjiao", "乱交", "乱叫"), ("luanxiang", "乱想", "乱象"), ("tianping", "填平", "天平"),
         ("luanchuan", "乱传", "栾川"), ("tianyixia", "填一下", "舔一下"), ("ceshiji", "测试集", "测试机"),
         ("luanma", "乱骂", "乱码"), ("kaifaji", "开发集", "开发机"), ("dousha", "都杀", "豆沙"),
         ("dousha", "都傻", "豆沙"), ("douxiao", "都笑", "逗笑"), ("doushi", "都试", "都是"),
         ("luandao", "乱倒", "乱道")]
FORCED = {
    ("yanzhengji", "验证集"): 400,
    ("ceshiji", "测试集"): 600,
    ("luanmo", "乱摸"): 200,
    ("luanfa", "乱发"): 400,
    ("luanche", "乱扯"): 200,
    ("luanzhao", "乱找"): 80,
    ("houduan", "后端"): 956,
    ("doushi", "斗士"): 279,
    ("doushi", "斗室"): 278,
    ("xiabian", "瞎编"): 1,
    ("xiache", "瞎扯"): 400,
    ("xiazheteng", "瞎折腾"): 400,
}
# Reweighted words the traditional dictionary lacked: added with the contains flag.
TC_ADDED = {
    ("xiabian", "瞎編"): 1,
}
ROWS = tuple(row[:4] for row in block(HEADER_COMMON) + block(HEADER_LESS))


class DailyLuanTianTests(unittest.TestCase):
    def test_blocks(self):
        common, less = block(HEADER_COMMON), block(HEADER_LESS)
        self.assertEqual(126, len(common))
        self.assertEqual(58, len(less))
        self.assertEqual({"exact_rank_no_contains"}, {row[4] for row in common + less})
        self.assertEqual(len(ROWS), len({(row[0], row[1]) for row in ROWS}))
        texts = {row[1] for row in ROWS}
        for word in REQUESTED:
            self.assertIn(word, texts, word)
        self.assertIn(("luanpin", "乱拼", "亂拼"), {row[:3] for row in ROWS})
        self.assertIn(("jingzhengji", "竞争集", "競爭集"), {row[:3] for row in ROWS})
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
