"""Tax terms stay selectable without promoting everyday homophone replacements."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder

ROWS = (
    ("shuihao", "税号", "稅號", 200),
    ("shuiyuan", "税源", "稅源", 420),
    ("shuiji", "税基", "稅基", 360),
    ("shuizhong", "税种", "稅種", 8),
    ("guoshui", "国税", "國稅", 420),
    ("shangshui", "上税", "上稅", 220),
    ("gaishui", "改税", "改稅", 120),
    ("jiashui", "加税", "加稅", 8),
    ("fenshuizhi", "分税制", "分稅制", 360),
    ("fenshui", "分税", "分稅", 260),
    ("keshui", "课税", "課稅", 160),
)


def read_rows(name):
    rows = {}
    for line in (ROOT / "data/generated" / name).read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        fields = line.split("\t")
        key = tuple(fields[:2])
        if key in rows:
            raise AssertionError(f"duplicate entry: {key}")
        rows[key] = fields[2:]
    return rows


class DailyTaxTests(unittest.TestCase):
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
        builder._inject_curated_daily_post_rank_exact_entries(*maps, exact)
        for index, mapping in enumerate(maps, 1):
            self.assertEqual({(row[0], row[index]): row[3] for row in ROWS}, mapping)

    def test_generated_entries_and_homophone_protection(self):
        protected = {
            "shuihao": "睡好", "shuiyuan": "水源", "shuiji": "水基",
            "shuizhong": "水中", "shangshui": "上水", "gaishui": "改水",
            "jiashui": "加水", "fenshui": "分水", "keshui": "瞌睡",
        }
        for index, variant in enumerate(("sc", "tc"), 1):
            rows = read_rows(f"dict_clean_{variant}.txt")
            for row in ROWS:
                self.assertEqual([str(row[3]), "no_contains"], rows[(row[0], row[index])])
                if row[0] in protected:
                    self.assertGreater(int(rows[(row[0], protected[row[0]])][0]), row[3])

    def test_no_fabricated_corpus_support(self):
        for index, variant in enumerate(("sc", "tc"), 1):
            rows = read_rows(f"dict_completion_prior_{variant}.txt")
            for row in ROWS:
                self.assertEqual((80, 0, 0, 0, 0, 0, 0),
                                 tuple(map(int, rows[(row[0], row[index])])))


if __name__ == "__main__":
    unittest.main()
