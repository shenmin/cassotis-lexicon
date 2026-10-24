"""Everyday words of 2026-10-24 (the user's buyaodai, which gave 不要呆, and
nanizuoba, which gave 那你坐吧 after a context): 不要 and 别 before a verb or an
adverb of one character (不要带, 不要再, 别走, 别忘) and set phrases of 别
(别担心, 别忘了), and 那你做吧. Weighted as test_daily_suo_bijiao_phrases
(occurrences where the word is no part of a longer dictionary word, nor
before one that its last character begins, nor after one that its first
character ends); homophones of one key keep the order of their frequency
(不要在 above 不要再, 别再 above 别在). Existing words of the same kinds at an
import weight (不要钱, 别理) are weighted by the same rules; the
traditional dictionary gets 別理."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from test_daily_whitespace_phrases import read_rows
from test_daily_cuo_xiu_sha_shui_phrases import block, keys

HEADER_COMMON = "# Everyday words, 2026-10-24 (不要 and 别 before a verb, 那你做吧), the more frequent ones:"
HEADER_LESS = "# Everyday words, 2026-10-24 (不要 and 别 before a verb, 那你做吧), the less frequent ones"
HEADER_FORCED = "# Existing words of the kinds of 不要带 and 那你做吧 (2026-10-24) at an import weight"
REQUESTED = "不要带 那你做吧".split()
# (pinyin, word, other): word above other on the key
ABOVE = [("buyaozai", "不要再", "不要在"), ("biezai", "别再", "别在"), ("bieting", "别听", "别停")]
BELOW = [("bieli", "别理", "别离"), ("biejiao", "别叫", "蹩脚")]
FORCED = {
    ("buyaoqian", "不要钱"): 600,
    ("bieli", "别理"): 200,
}
# Reweighted words the traditional dictionary lacked: added with the contains flag.
TC_ADDED = {
    ("bieli", "別理"): 200,
}
ROWS = tuple(row[:4] for row in block(HEADER_COMMON) + block(HEADER_LESS))


class DailyBuyaoBieTests(unittest.TestCase):
    def test_blocks(self):
        common, less = block(HEADER_COMMON), block(HEADER_LESS)
        self.assertEqual(80, len(common))
        self.assertEqual(46, len(less))
        self.assertEqual({"exact_rank_no_contains"}, {row[4] for row in common + less})
        self.assertEqual(len(ROWS), len({(row[0], row[1]) for row in ROWS}))
        texts = {row[1] for row in ROWS}
        for word in REQUESTED:
            self.assertIn(word, texts, word)
        self.assertIn(("buyaodai", "不要带", "不要帶"), {row[:3] for row in ROWS})
        # Taiwan's forms: 著 is 着 there (扛著), 爲 is no form of it.
        self.assertTrue(all("爲" not in row[2] for row in ROWS))

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
