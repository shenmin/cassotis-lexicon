"""Readings that were missing (2026-10-18): the standard reading beside a
colloquial one (泄露 xielou, 标识符 biaozhifu, 明了 mingliao), another meaning
(一行 yixing, 朝阳 zhaoyang, 落下 laxia, 褪去 tunqu, 得有点 deyoudian, 就得 jiude,
穿着 chuanzhuo as attire), the colloquial nei of 哪个 / 哪些 / 哪些方面, and 标识
as biaoshi; the common erhua words typed with the syllable er (zheer, naer,
huier), which were stored only as zher / nar, at the lowest weight (not
没空儿 or 点儿: in 没空而 and 有点耳鸣 the er is no erhua); and readings that were
errors: 适可而止 shikeyerzhi, 小时了 xiaoshiliao, 仔仔细细 zaizixixi. A new row
stays below every other word of its key unless it is the standard reading."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from test_daily_whitespace_phrases import read_rows

MANIFEST = ROOT / "manifests/curated_daily_supplement_phrases.tsv"
OVERRIDES = ROOT / "manifests/pinyin_overrides.tsv"
HEADER_READINGS = "# Readings that were missing, 2026-10-18:"
HEADER_ERHUA = "# Erhua words typed with the syllable er"
READINGS = (
    ("xielou", "泄露", "泄露", 1000),
    ("yixing", "一行", "一行", 999),
    ("neige", "哪个", "哪個", 580),
    ("neixie", "哪些", "哪些", 834),
    ("laxia", "落下", "落下", 834),
    ("biaozhifu", "标识符", "標識符", 666),
    ("biaoshi", "标识", "標識", 600),
    ("zhaoyang", "朝阳", "朝陽", 999),
    ("tunqu", "褪去", "褪去", 202),
    ("deyoudian", "得有点", "得有點", 800),
    ("mingliao", "明了", "明了", 696),
    ("jiude", "就得", "就得", 699),
    ("neixiefangmian", "哪些方面", "哪些方面", 280),
    ("chuanzhuo", "穿着", "穿着", 700),
)
# (wrong reading, right reading, sc, tc)
REKEYED = (("shikeyerzhi", "shikeerzhi", "适可而止", "適可而止"),
           ("xiaoshiliao", "xiaoshile", "小时了", "小時了"),
           ("zaizixixi", "zizixixi", "仔仔细细", "仔仔細細"))
# Standard readings that may lead their key.
STANDARD = {("xielou", "泄露"), ("biaozhifu", "标识符")}


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


ROWS = tuple(row[:4] for row in block(HEADER_READINGS) + block(HEADER_ERHUA))


class DailyReadingsErhuaTests(unittest.TestCase):
    def test_reading_rows(self):
        rows = block(HEADER_READINGS)
        self.assertEqual(READINGS, tuple(row[:4] for row in rows))
        self.assertEqual({"exact_rank_no_contains"}, {row[4] for row in rows})

    def test_only_common_erhua_words_have_the_er_spelling(self):
        # 这儿, 那儿, 哪儿, 一会儿, 玩意儿, 一块儿 and their compounds; not 没空儿,
        # 点儿 or 有点儿: in 没空而 and 有点耳鸣 the er is no erhua (the user).
        families = ("这儿", "那儿", "哪儿", "会儿", "玩意儿", "一块儿")
        rows = block(HEADER_ERHUA)
        self.assertEqual(20, len(rows))
        self.assertEqual({1}, {row[3] for row in rows})
        self.assertEqual({"exact_rank_no_contains"}, {row[4] for row in rows})
        for wanted in (("zheer", "这儿"), ("naer", "那儿"), ("naer", "哪儿"), ("zhehuier", "这会儿"),
                       ("wanyier", "玩意儿"), ("yikuaier", "一块儿")):
            self.assertIn(wanted, {row[:2] for row in rows})
        for index, variant in enumerate(("sc", "tc"), 1):
            generated = read_rows(f"dict_clean_{variant}.txt")
            generated.update(read_rows(f"dict_unihan_{variant}.txt"))
            for row in rows:
                self.assertTrue(row[1].endswith(families) and row[1].count("儿") == 1, row)
                self.assertTrue(row[index].endswith(("儿", "兒")) and row[0].endswith("er"), row)
            for absent in (("meikonger", "没空儿"), ("dianer", "点儿"), ("youdianer", "有点儿"),
                           ("faner", "范儿"), ("jiner", "今儿")):
                if variant == "sc":
                    self.assertNotIn(absent, generated, absent)

    def test_new_rows_stay_below_the_words_of_their_key(self):
        for index, variant in enumerate(("sc", "tc"), 1):
            generated = read_rows(f"dict_clean_{variant}.txt")
            generated.update(read_rows(f"dict_unihan_{variant}.txt"))
            keys = {}
            for (pinyin, text), fields in generated.items():
                keys.setdefault(pinyin, {})[text] = int(fields[0])
            new = {(row[0], row[index]) for row in ROWS}
            for row in ROWS:
                pinyin, text, weight = row[0], row[index], row[3]
                if (row[0], row[1]) in STANDARD:
                    continue
                others = [w for t, w in keys[pinyin].items() if t != text and (pinyin, t) not in new]
                if others:
                    # (1 is the lowest weight a row can have)
                    self.assertTrue(weight < max(others) or weight == 1, row)

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

    def test_readings_that_were_errors(self):
        overrides = OVERRIDES.read_text(encoding="utf-8").splitlines()
        for wrong, right, sc, tc in REKEYED:
            for index, variant in enumerate(("sc", "tc"), 1):
                text = (sc, tc)[index - 1]
                self.assertTrue(any(line.startswith(f"{text}	{right}	") for line in overrides), text)
                rows = read_rows(f"dict_clean_{variant}.txt")
                readings = {pinyin for pinyin, word in rows if word == text}
                self.assertIn(right, readings, text)
                self.assertNotIn(wrong, readings, text)


if __name__ == "__main__":
    unittest.main()
