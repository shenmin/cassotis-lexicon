"""Daily phrases keep explicit ranks and preserve established homophones."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from test_daily_whitespace_phrases import read_rows

ROWS = (
    ("youpa", "又怕", "又怕", 450),
    ("chengbao", "撑爆", "撐爆", 200),
    ("zuidazhi", "最大值", "最大值", 600),
    ("zhongzhi", "中值", "中值", 200),
    ("pingta", "凭他", "憑他", 160),
    ("pingni", "凭你", "憑你", 240),
    ("pingsha", "凭啥", "憑啥", 280),
    ("pingwo", "凭我", "憑我", 240),
    ("pingzhang", "凭仗", "憑仗", 120),
    ("pingji", "凭几", "憑几", 80),
    ("jiahui", "加回", "加回", 320),
    ("jiahuiqu", "加回去", "加回去", 360),
)


class DailyPreferenceTests(unittest.TestCase):
    def test_explicit_weights_survive_rebuild(self):
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

    def test_generated_rows(self):
        for index, variant in enumerate(("sc", "tc"), 1):
            rows = read_rows(f"dict_clean_{variant}.txt")
            for row in ROWS:
                self.assertEqual([str(row[3]), "no_contains"], rows[(row[0], row[index])])

    def test_preserve_common_homophones(self):
        for variant in ("sc", "tc"):
            rows = read_rows(f"dict_clean_{variant}.txt")
            for pinyin, established, added in (
                ("chengbao", "承包", "撑爆" if variant == "sc" else "撐爆"),
                ("chengbao", "城堡", "撑爆" if variant == "sc" else "撐爆"),
                ("zhongzhi", "终止" if variant == "sc" else "終止", "中值"),
                ("zhongzhi", "种植" if variant == "sc" else "種植", "中值"),
                ("pingzhang", "屏障", "凭仗" if variant == "sc" else "憑仗"),
                ("pingji", "评级" if variant == "sc" else "評級",
                 "凭几" if variant == "sc" else "憑几"),
            ):
                self.assertGreater(int(rows[(pinyin, established)][0]),
                                   int(rows[(pinyin, added)][0]))

    def test_no_fabricated_corpus_support(self):
        for index, variant in enumerate(("sc", "tc"), 1):
            rows = read_rows(f"dict_completion_prior_{variant}.txt")
            for row in ROWS:
                self.assertEqual((80, 0, 0, 0, 0, 0, 0),
                                 tuple(map(int, rows[(row[0], row[index])])))


if __name__ == "__main__":
    unittest.main()
