"""Everyday words of 2026-10-22 (the user's 春丽、只对、还对 read hai、偏对、我擦、机王、
已打、已答、分库, and more of their kinds): an adverb before 对, characters of
fighting games, exclamations of chat, X王 of a champion, 已 and 未 before a
verb of messages and errands, and words of split databases. Weighted as
test_daily_suo_bijiao_phrases (occurrences where the word is no part of a
longer dictionary word, nor before one that its last character begins); a
requested word stays under a word of its key more than one and a half times
as frequent (只对 under 支队, 春丽 under 纯利). Existing words at an import
weight on the keys of the batch are weighted by the same rules (才对, 拳王,
街霸), so that a new word does not go above a commoner one whose weight says
nothing (既往 above 机王, 医大 above 已打), and 卧草 and the
place name 蔡堆, far above their frequency, go under 卧槽 and 才对; 臥草, 醫大
and 維達 were missing from the traditional dictionary and are added there."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from test_daily_whitespace_phrases import read_rows
from test_daily_cuo_xiu_sha_shui_phrases import block, keys

HEADER_COMMON = "# Everyday words, 2026-10-22, the more frequent ones:"
HEADER_LESS = "# Everyday words, 2026-10-22, the less frequent ones"
HEADER_FORCED = "# Existing words on the keys of the batch of 2026-10-22:"
REQUESTED = "春丽 只对 还对 偏对 我擦 机王 已打 已答 分库".split()
# (pinyin, word, other): word above other on the key
ABOVE = [("caidui", "才对", "蔡堆"), ("wocao", "卧槽", "卧草"),
         ("weiqian", "未签", "尾欠"), ("weipi", "未批", "胃痞"), ("yida", "已打", "已答"),
         ("jiwang", "既往", "机王"),
         ("weida", "维达", "未打")]
BELOW = [("zhidui", "只对", "支队"), ("chunli", "春丽", "纯利"), ("jiwang", "机王", "既往"),
         ("yida", "已答", "一大"), ("weishou", "未收", "为首")]
FORCED = {
    ("jieba", "街霸"): 279,
    ("caidui", "才对"): 600,
    ("quanwang", "拳王"): 600,
    ("fenkufenbiao", "分库分表"): 200,
    ("fenqubiao", "分区表"): 400,
    ("duxiefenli", "读写分离"): 200,
    ("zhucongfuzhi", "主从复制"): 200,
    ("jiwang", "既往"): 600,
    ("yida", "医大"): 402,
    ("yiban", "一瓣"): 279,
    ("weida", "维达"): 400,
    ("wocao", "卧草"): 50,
    ("caidui", "蔡堆"): 50,
}
# Reweighted words the traditional dictionary lacked: added with the contains flag.
TC_ADDED = {
    ("yida", "醫大"): 402,
    ("weida", "維達"): 400,
    ("wocao", "臥草"): 50,
}
ROWS = tuple(row[:4] for row in block(HEADER_COMMON) + block(HEADER_LESS))


class DailyChunliYidaTests(unittest.TestCase):
    def test_blocks(self):
        common, less = block(HEADER_COMMON), block(HEADER_LESS)
        self.assertEqual(48, len(common))
        self.assertEqual(43, len(less))
        self.assertEqual({"exact_rank_no_contains"}, {row[4] for row in common + less})
        self.assertEqual(len(ROWS), len({(row[0], row[1]) for row in ROWS}))
        texts = {row[1] for row in ROWS}
        for word in REQUESTED:
            self.assertIn(word, texts, word)
        self.assertIn(("haidui", "还对", "還對"), {row[:3] for row in ROWS})
        self.assertIn(("woca", "我擦", "我擦"), {row[:3] for row in ROWS})
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
