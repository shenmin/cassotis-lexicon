"""Lines of classical poems (the school curriculum, 唐诗三百首, 千家诗, 宋词三百首)
are exact rows: typed in full they are the first candidate, they take no
part in ranking or path statistics, and they offer no completions (their
completion prior is the exact-only layer: the prefixes of 8,000 lines changed
the short promotion of words such as 演播 and 伺候). 本机 goes above 本纪 and 笨鸡."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from test_daily_whitespace_phrases import read_rows

MANIFEST = ROOT / "manifests/curated_daily_supplement_phrases.tsv"
HEADER_POETRY = "# Classical poetry lines, 2026-10-15:"
HEADER_FORCED = "# Existing words set higher, 2026-10-15: 本机"
# Lines that must be there with their reading as typed.
SAMPLES = (
    ("chunmianbujuexiao", "春眠不觉晓", "春眠不覺曉"),
    ("chuchuwentiniao", "处处闻啼鸟", "處處聞啼鳥"),
    ("bairiyishanjin", "白日依山尽", "白日依山盡"),
    ("xiaohecailujianjianjiao", "小荷才露尖尖角", "小荷才露尖尖角"),
    ("xiantianxiazhiyoueryou", "先天下之忧而忧", "先天下之憂而憂"),
    ("guanguanjujiu", "关关雎鸠", "關關雎鳩"),
)
# Verse readings get a second row: 千里江陵一日还 (huan) beside the everyday hai.
SECOND_READINGS = (
    ("qianlijianglingyirihuan", "千里江陵一日还"),
    ("qianlijianglingyirihai", "千里江陵一日还"),
)
FORCED = (("benji", "本机", "本機", 760),)


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


ROWS = tuple(row[:4] for row in block(HEADER_POETRY))


class DailyClassicalPoetryTests(unittest.TestCase):
    def test_block_rows(self):
        rows = block(HEADER_POETRY)
        self.assertGreater(len(rows), 8000)
        self.assertEqual({"exact_rank_exact_only"}, {row[4] for row in rows})
        self.assertEqual(len(rows), len({(row[0], row[1]) for row in rows}))
        self.assertEqual(len(rows), len({(row[0], row[2]) for row in rows}))
        weights = {}
        for pinyin, sc, tc, weight, _ in rows:
            self.assertTrue(4 <= len(sc) <= 11, sc)
            self.assertEqual(len(sc), len(tc), sc)
            self.assertTrue(pinyin.isascii() and pinyin.islower() and pinyin.isalpha(), pinyin)
            # four characters 200, school poems 360, the rest 300 (homophones one less)
            self.assertTrue(any(top - 3 <= weight <= top for top in (200, 300, 360)), (sc, weight))
            weights.setdefault(pinyin, []).append(weight)
        for pinyin, values in weights.items():
            self.assertEqual(len(values), len(set(values)), pinyin)
        for sample in SAMPLES + tuple((p, s, None) for p, s in SECOND_READINGS):
            self.assertTrue(any(row[0] == sample[0] and row[1] == sample[1] and
                                (sample[2] is None or row[2] == sample[2]) for row in rows), sample)

    def test_explicit_readings_and_ranks_survive_rebuild(self):
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

    def test_generated_entries(self):
        for index, variant in enumerate(("sc", "tc"), 1):
            rows = read_rows(f"dict_clean_{variant}.txt")
            for row in ROWS:
                self.assertEqual([str(row[3]), "no_contains"], rows[(row[0], row[index])])

    def test_exact_only_prior(self):
        for index, variant in enumerate(("sc", "tc"), 1):
            rows = read_rows(f"dict_completion_prior_{variant}.txt")
            for row in ROWS:
                self.assertEqual(builder._specialist_completion_prior(),
                                 tuple(map(int, rows[(row[0], row[index])])))

    def test_no_completions(self):
        for index, variant in enumerate(("sc", "tc"), 1):
            # (a line already in the dictionary under another reading keeps its
            # completions)
            keys = {(row[0], row[index]) for row in ROWS}
            for line in (ROOT / "data/generated" / f"dict_completion_lookup_{variant}.txt").read_text(
                    encoding="utf-8").splitlines():
                # prefix, pinyin, text, scores
                fields = line.split("\t")
                if len(fields) > 2:
                    self.assertNotIn((fields[1], fields[2]), keys, line)

    def test_forced_weights(self):
        self.assertEqual(FORCED, tuple(row[:4] for row in block(HEADER_FORCED)))
        self.assertEqual({"exact_rank"}, {row[4] for row in block(HEADER_FORCED)})
        for index, variant in enumerate(("sc", "tc"), 1):
            rows = read_rows(f"dict_clean_{variant}.txt")
            for row in FORCED:
                self.assertEqual(str(row[3]), rows[(row[0], row[index])][0], row)
            # above the history book and the farm chicken
            for other in (("本纪", "本紀"), ("笨鸡", "笨雞")):
                self.assertGreater(int(rows[("benji", FORCED[0][index])][0]),
                                   int(rows[("benji", other[index - 1])][0]), other)


if __name__ == "__main__":
    unittest.main()
