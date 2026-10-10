"""Reciprocal-action phrases without overriding common homophones."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from test_daily_whitespace_phrases import read_rows

ROWS = (
    ("huyou", "互有", "互有", 120),
    ("yaotui", "要推", "要推", 260),
    ("buyaotui", "不要推", "不要推", 360),
    ("hunie", "互捏", "互捏", 120),
    ("husun", "互损", "互損", 160),
    ("huma", "互骂", "互罵", 200),
    ("huda", "互打", "互打", 160),
    ("hutui", "互推", "互推", 180),
    ("huti", "互踢", "互踢", 100),
    ("hushuai", "互摔", "互摔", 80),
    ("hupai", "互拍", "互拍", 140),
    ("hula", "互拉", "互拉", 120),
    ("hutai", "互抬", "互抬", 100),
    ("huchai", "互拆", "互拆", 100),
    ("huxie", "互写", "互寫", 100),
    ("hufa", "互发", "互發", 8),
)


class DailyReciprocalTests(unittest.TestCase):
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
                ("huyou", "忽悠", "互有"),
                ("yaotui", "腰腿", "要推"),
                ("hupai", "胡牌", "互拍"),
                ("hula", "呼啦", "互拉"),
                ("hufa", "护发" if variant == "sc" else "護髮",
                 "互发" if variant == "sc" else "互發"),
                ("hufa", "护法" if variant == "sc" else "護法",
                 "互发" if variant == "sc" else "互發"),
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
