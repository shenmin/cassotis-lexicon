"""Song names are available; looking something up outranks its homophones."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from test_daily_whitespace_phrases import read_rows

ROWS = (
    ("geming", "歌名", "歌名", 500),
    ("chadao", "查到", "查到", 933),
    ("chadao", "岔道", "岔道", 898),
    ("chadao", "茶道", "茶道", 700),
)


class DailySongLookupTests(unittest.TestCase):
    def test_explicit_weights_replace_old_order_on_rebuild(self):
        entries, _ = builder._parse_curated_daily_phrase_entries(
            (ROOT / "manifests/curated_daily_supplement_phrases.tsv").read_bytes(), 2)
        wanted = {(row[0], row[1]) for row in ROWS}
        selected = [entry for entry in entries if (entry[3], entry[0]) in wanted]
        regular, exact = builder._partition_curated_daily_post_rank_exact_entries(selected)
        self.assertFalse(regular)
        self.assertEqual(len(ROWS), len(exact))
        old = {("chadao", "茶道"): 933, ("chadao", "岔道"): 898,
               ("chadao", "查到"): 700}
        maps = (dict(old), dict(old))
        builder._inject_curated_daily_post_rank_exact_entries(*maps, exact)
        builder._inject_curated_daily_post_rank_exact_entries(*maps, exact)
        for index, mapping in enumerate(maps, 1):
            self.assertEqual({(row[0], row[index]): row[3] for row in ROWS}, mapping)

    def test_generated_order_and_visibility_flags(self):
        for index, variant in enumerate(("sc", "tc"), 1):
            rows = read_rows(f"dict_clean_{variant}.txt")
            for row in ROWS:
                flags = ["no_contains"] if row[0] == "geming" else []
                self.assertEqual([str(row[3]), *flags], rows[(row[0], row[index])])
            order = sorted((key for key in rows if key[0] == "chadao"),
                           key=lambda key: -int(rows[key][0]))
            self.assertEqual(["查到", "岔道", "茶道"], [key[1] for key in order[:3]])
            self.assertGreater(int(rows[("geming", "革命")][0]),
                               int(rows[("geming", "歌名")][0]))

    def test_new_entry_has_no_fabricated_corpus_support(self):
        for variant in ("sc", "tc"):
            rows = read_rows(f"dict_completion_prior_{variant}.txt")
            self.assertEqual((80, 0, 0, 0, 0, 0, 0),
                             tuple(map(int, rows[("geming", "歌名")])))


if __name__ == "__main__":
    unittest.main()
