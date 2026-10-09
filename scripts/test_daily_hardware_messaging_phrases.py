"""Hardware and messaging additions keep explicit readings and bounded weights."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder

ROWS = (
    ("duxian", "独显", "獨顯", 700),
    ("zhengjiuzhe", "拯救者", "拯救者", 560),
    ("pianyide", "便宜得", "便宜得", 260),
    ("fani", "发你", "發你", 480),
    ("fawo", "发我", "發我", 480),
    ("fata", "发他", "發他", 420),
    ("fata", "发她", "發她", 420),
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


class DailyHardwareMessagingTests(unittest.TestCase):
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

    def test_generated_readings_and_relative_weights(self):
        for index, variant in enumerate(("sc", "tc"), 1):
            rows = read_rows(f"dict_clean_{variant}.txt")
            for row in ROWS:
                self.assertEqual([str(row[3]), "no_contains"], rows[(row[0], row[index])])
            self.assertNotIn(("bianyide", "便宜得"), rows)
            self.assertGreater(int(rows[("pianyide", "便宜的")][0]),
                               int(rows[("pianyide", "便宜得")][0]))
            display = "独显" if variant == "sc" else "獨顯"
            self.assertGreater(int(rows[("duxian", display)][0]),
                               int(rows[("duxian", "毒腺")][0]))

    def test_no_fabricated_corpus_support(self):
        for index, variant in enumerate(("sc", "tc"), 1):
            rows = read_rows(f"dict_completion_prior_{variant}.txt")
            for row in ROWS:
                self.assertEqual((80, 0, 0, 0, 0, 0, 0),
                                 tuple(map(int, rows[(row[0], row[index])])))


if __name__ == "__main__":
    unittest.main()
