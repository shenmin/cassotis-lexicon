"""X的 beside the adverb X地 where the dictionary had only the latter (正确地
and no 正确的 for zhengquede): one less than X地 in both variants, exact
rows that offer no completions."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from test_daily_whitespace_phrases import read_rows

MANIFEST = ROOT / "manifests/curated_daily_supplement_phrases.tsv"
HEADER = "# X的 beside the adverb X地, 2026-10-15:"


def block():
    rows = []
    inside = False
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        if line.startswith(HEADER):
            inside = True
            continue
        if inside:
            if not line or line.startswith("#"):
                break
            sc, tc, usage, pinyin, mode = line.split("\t")
            rows.append((pinyin, sc, tc, int(round(float(usage) * 1000)), mode))
    return rows


ROWS = tuple(row[:4] for row in block())


class DailyDeParticleTests(unittest.TestCase):
    def test_rows(self):
        rows = block()
        self.assertEqual(63, len(rows))
        self.assertEqual({"exact_rank_exact_only"}, {row[4] for row in rows})
        self.assertIn(("zhengquede", "正确的", "正確的", 799), ROWS)
        for pinyin, sc, tc, weight in ROWS:
            self.assertTrue(pinyin.endswith("de") and sc.endswith("的") and tc.endswith("的"), sc)

    def test_one_below_the_adverb(self):
        for index, variant in enumerate(("sc", "tc"), 1):
            rows = read_rows(f"dict_clean_{variant}.txt")
            for row in ROWS:
                self.assertEqual([str(row[3]), "no_contains"], rows[(row[0], row[index])])
                # one less than X地 in the variant where it weighs less
                adverb = row[index][:-1] + "地"
                self.assertLess(row[3], int(rows[(row[0], adverb)][0]), adverb)

    def test_exact_only_prior(self):
        for index, variant in enumerate(("sc", "tc"), 1):
            rows = read_rows(f"dict_completion_prior_{variant}.txt")
            for row in ROWS:
                self.assertEqual(builder._specialist_completion_prior(),
                                 tuple(map(int, rows[(row[0], row[index])])))


if __name__ == "__main__":
    unittest.main()
