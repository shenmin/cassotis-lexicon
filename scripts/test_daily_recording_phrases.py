"""Recording phrases keep explicit readings and moderate exact ranks."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from test_daily_whitespace_phrases import read_rows

ROWS = (
    ("jiangle", "降了", "降了", 460),
    ("liangdang", "两档", "兩檔", 480),
    ("lucheng", "录成", "錄成", 200),
    ("lushipin", "录视频", "錄視頻", 400),
    ("lule", "录了", "錄了", 240),
    ("luyige", "录一个", "錄一個", 220),
    ("ludao", "录到", "錄到", 280),
    ("luhao", "录好", "錄好", 280),
    ("luhuai", "录坏", "錄壞", 160),
    ("xiaoshi", "小诗", "小詩", 120),
    ("luzuo", "录做", "錄做", 120),
    ("shouxi", "手洗", "手洗", 480),
    ("jixi", "机洗", "機洗", 480),
    ("shouzhi", "手制", "手製", 20),
)

WEIGHT_OVERRIDES = (
    ("dazi", "打字", "打字", 1000),
    ("dazi", "大字", "大字", 897),
)


class DailyRecordingTests(unittest.TestCase):
    def test_explicit_readings_and_ranks_survive_rebuild(self):
        entries, _ = builder._parse_curated_daily_phrase_entries(
            (ROOT / "manifests/curated_daily_supplement_phrases.tsv").read_bytes(), 2)
        wanted = {(row[0], row[1]) for row in ROWS}
        selected = [entry for entry in entries if (entry[3], entry[0]) in wanted]
        regular, exact = builder._partition_curated_daily_post_rank_exact_entries(selected)
        self.assertFalse(regular)
        self.assertEqual(len(ROWS), len(exact))
        maps = ({}, {})
        builder._inject_curated_daily_post_rank_exact_entries(*maps, exact)
        builder._inject_curated_daily_post_rank_exact_entries(*maps, exact)
        for index, mapping in enumerate(maps, 1):
            self.assertEqual({(row[0], row[index]): row[3] for row in ROWS}, mapping)

    def test_generated_entries_and_reading(self):
        for index, variant in enumerate(("sc", "tc"), 1):
            rows = read_rows(f"dict_clean_{variant}.txt")
            for row in ROWS:
                self.assertEqual([str(row[3]), "no_contains"], rows[(row[0], row[index])])
            self.assertNotIn(("xiangle", "降了"), rows)

    def test_preserve_common_homophones(self):
        for variant in ("sc", "tc"):
            rows = read_rows(f"dict_clean_{variant}.txt")
            for pinyin, common, added in (
                ("jiangle", "讲了" if variant == "sc" else "講了", "降了"),
                ("lucheng", "路程", "录成" if variant == "sc" else "錄成"),
                ("xiaoshi", "小事", "小诗" if variant == "sc" else "小詩"),
                ("xiaoshi", "小时" if variant == "sc" else "小時",
                 "小诗" if variant == "sc" else "小詩"),
                ("xiaoshi", "消失", "小诗" if variant == "sc" else "小詩"),
                ("xiaoshi", "消逝", "小诗" if variant == "sc" else "小詩"),
                ("shouxi", "首席", "手洗"),
                ("jixi", "积习" if variant == "sc" else "積習",
                 "机洗" if variant == "sc" else "機洗"),
                ("shouzhi", "手指", "手制" if variant == "sc" else "手製"),
                ("shouzhi", "受制", "手制" if variant == "sc" else "手製"),
                ("shouzhi", "收支", "手制" if variant == "sc" else "手製"),
            ):
                self.assertGreater(int(rows[(pinyin, common)][0]),
                                   int(rows[(pinyin, added)][0]))

    def test_no_fabricated_corpus_support(self):
        for index, variant in enumerate(("sc", "tc"), 1):
            rows = read_rows(f"dict_completion_prior_{variant}.txt")
            for row in ROWS:
                self.assertEqual((80, 0, 0, 0, 0, 0, 0),
                                 tuple(map(int, rows[(row[0], row[index])])))

    def test_typing_preference_survives_rebuild(self):
        entries, _ = builder._parse_curated_daily_phrase_entries(
            (ROOT / "manifests/curated_daily_supplement_phrases.tsv").read_bytes(), 2)
        wanted = {(row[0], row[1]) for row in WEIGHT_OVERRIDES}
        selected = [entry for entry in entries if (entry[3], entry[0]) in wanted]
        regular, exact = builder._partition_curated_daily_post_rank_exact_entries(selected)
        self.assertFalse(regular)
        self.assertEqual(len(WEIGHT_OVERRIDES), len(exact))
        maps = ({("dazi", "打字"): 801, ("dazi", "大字"): 897},
                {("dazi", "打字"): 972, ("dazi", "大字"): 1000})
        builder._inject_curated_daily_post_rank_exact_entries(*maps, exact)
        for index, variant in enumerate(("sc", "tc"), 1):
            self.assertEqual({(row[0], row[index]): row[3] for row in WEIGHT_OVERRIDES},
                             maps[index - 1])
            rows = read_rows(f"dict_clean_{variant}.txt")
            for row in WEIGHT_OVERRIDES:
                self.assertEqual([str(row[3])], rows[(row[0], row[index])])


if __name__ == "__main__":
    unittest.main()
