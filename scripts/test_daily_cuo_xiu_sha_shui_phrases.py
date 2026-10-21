"""Everyday phrases of 2026-10-18 (the user's 定死、按月、按年、读错、返修、原厂、送修、
报修、按小时、念错、读对、念对、出啥、弄啥、吹啥、怕啥、咋呼啥、叫啥、喊啥、打啥、打谁、骂啥、
骂谁、贴啥、挂啥、喊杀、喊打, and more of their kinds): 按 + a unit, X错 / X对,
repair, fixed for good, X啥, X谁, 喊 + a cry. Weights by occurrences in the
general text and the chat sentences, in two blocks: the more frequent ones
(400 and up) and the less frequent ones. A row stays below the first word of
its key unless three times as frequent, and below any word of its key at
weight 100 or more that is more frequent (a requested word: one and a half
times); 圆场 is set lower so that the short promotion keeps the requested 原厂
first."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from test_daily_whitespace_phrases import read_rows

MANIFEST = ROOT / "manifests/curated_daily_supplement_phrases.tsv"
HEADER_COMMON = "# Everyday phrases, 2026-10-18, the more frequent ones:"
HEADER_LESS = "# Everyday phrases, 2026-10-18, the less frequent ones"
HEADER_FORCED = "# Existing words set lower, 2026-10-18:"
REQUESTED = ("定死 按月 按年 读错 返修 原厂 送修 报修 按小时 念错 读对 念对 出啥 弄啥 吹啥 怕啥 "
             "咋呼啥 叫啥 喊啥 打啥 打谁 骂啥 骂谁 贴啥 挂啥 喊杀 喊打").split()
# Requested words below a more frequent first word of their key.
BELOW = {"报修": "保修", "返修": "翻修", "打啥": "大厦", "骂啥": "麻纱", "挂啥": "刮痧",
         "打谁": "打水", "贴啥": "铁砂", "喊啥": "汉莎", "喊杀": "汉莎"}
# Rows below a more frequent word of their key that is not the first.
UNDER = {"按季": "胺基", "叫谁": "缴税", "焊死": "汉斯"}
LEADS = {"定死": "钉死", "叫啥": "较傻", "按月": "安岳", "原厂": "圆场"}
FORCED = (("yuanchang", "圆场", "圓場", 50),)


def block(header):
    """(pinyin, simplified, traditional, weight, mode) rows under a header."""
    rows = []
    inside = False
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        if line.startswith(header):
            inside = True
            continue
        if inside:
            if not line or line.startswith("#"):
                break
            sc, tc, usage, pinyin, mode = line.split("\t")
            rows.append((pinyin, sc, tc, int(round(float(usage) * 1000)), mode))
    return rows


ROWS = tuple(row[:4] for row in block(HEADER_COMMON) + block(HEADER_LESS))


def keys(variant):
    generated = read_rows(f"dict_clean_{variant}.txt")
    generated.update(read_rows(f"dict_unihan_{variant}.txt"))
    result = {}
    for (pinyin, text), fields in generated.items():
        result.setdefault(pinyin.replace("'", ""), {})[text] = int(fields[0])
    return result


class DailyCuoXiuShaShuiTests(unittest.TestCase):
    def test_blocks(self):
        common, less = block(HEADER_COMMON), block(HEADER_LESS)
        self.assertGreater(len(common), 60)
        self.assertGreater(len(less), 40)
        # Only words in use (the user: 不存在的词不要凑): no phrase with a particle
        # or an object, no 按 + a noun that is mostly a longer word; 按秒 is rare
        # and took 掐分赶秒 in a long benchmark sentence.
        texts = {row[1] for row in common + less}
        for word in ("修好了", "拿去修", "能干啥", "按人", "按份", "按字", "按条", "愁啥", "输对", "按秒"):
            self.assertNotIn(word, texts)
        self.assertEqual({"exact_rank_no_contains"}, {row[4] for row in common + less})
        self.assertTrue(all(row[3] >= 400 for row in common))
        self.assertTrue(all(row[3] < 400 for row in less))
        self.assertEqual(len(ROWS), len({(row[0], row[1]) for row in ROWS}))
        # 谁 is shui in these rows (the shei rows of the same words came on
        # 2026-10-20: test_daily_x_shui_phrases); 念 stays 念 in traditional.
        self.assertFalse(any(row[0].endswith("shei") for row in ROWS))
        self.assertFalse(any("唸" in row[2] for row in ROWS))

    def test_requested_words(self):
        texts = {row[1] for row in ROWS}
        rows = keys("sc")
        for word in REQUESTED:
            if word == "钉死":
                continue
            self.assertIn(word, texts, word)
        for word, first in LEADS.items():
            pinyin = next(row[0] for row in ROWS if row[1] == word)
            self.assertGreater(rows[pinyin][word], rows[pinyin][first], word)
        for word, first in list(BELOW.items()) + list(UNDER.items()):
            pinyin = next(row[0] for row in ROWS if row[1] == word)
            self.assertLess(rows[pinyin][word], rows[pinyin][first], word)

    def test_explicit_ranks_survive_rebuild(self):
        entries, _ = builder._parse_curated_daily_phrase_entries(MANIFEST.read_bytes(), 2)
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

    def test_forced_weight_keeps_its_row(self):
        self.assertEqual(FORCED, tuple((row[0], row[1], row[2], row[3]) for row in block(HEADER_FORCED)))
        self.assertEqual({"exact_rank"}, {row[4] for row in block(HEADER_FORCED)})
        for index, variant in enumerate(("sc", "tc"), 1):
            rows = read_rows(f"dict_clean_{variant}.txt")
            for row in FORCED:
                self.assertEqual(str(row[3]), rows[(row[0], row[index])][0])


if __name__ == "__main__":
    unittest.main()
