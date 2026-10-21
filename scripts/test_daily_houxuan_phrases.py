"""Words of an input method's candidates, 2026-10-21 (the user's 候选里: houxuanli
gave 后绚丽 and no other phrase, since neither the character LM nor the
pinyin-conditioned correction knows 候选里), and words of its kind as the
lexicon's 词库里, 词库中 and 在词库里. Weighted as test_daily_suo_bijiao_phrases;
the keys held no word before, so each row is the first of its key."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from test_daily_whitespace_phrases import read_rows
from test_daily_cuo_xiu_sha_shui_phrases import block, keys

HEADER = "# Words of an input method's candidates, 2026-10-21"
REQUESTED = ["候选里"]
ROWS = tuple(row[:4] for row in block(HEADER))


class DailyHouxuanTests(unittest.TestCase):
    def test_block(self):
        rows = block(HEADER)
        self.assertEqual({"exact_rank_no_contains"}, {row[4] for row in rows})
        self.assertEqual(len(ROWS), len({(row[0], row[1]) for row in ROWS}))
        texts = {row[1] for row in ROWS}
        for word in REQUESTED:
            self.assertIn(word, texts, word)
        self.assertIn(("houxuanli", "候选里", "候選裡", 400), ROWS)

    def test_first_of_its_key(self):
        for index, variant in enumerate(("sc", "tc"), 1):
            rows = keys(variant)
            for row in ROWS:
                weights = rows[row[0]]
                self.assertEqual(row[index], max(weights, key=weights.get), (variant, row))

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
        for index, mapping in enumerate(maps, 1):
            self.assertEqual({(row[0], row[index]): row[3] for row in ROWS}, mapping)

    def test_generated_entries_and_prior(self):
        for index, variant in enumerate(("sc", "tc"), 1):
            rows = read_rows(f"dict_clean_{variant}.txt")
            prior = read_rows(f"dict_completion_prior_{variant}.txt")
            for row in ROWS:
                self.assertEqual([str(row[3]), "no_contains"], rows[(row[0], row[index])])
                self.assertEqual(["80", "0", "0", "0", "0", "0", "0"], prior[(row[0], row[index])])


if __name__ == "__main__":
    unittest.main()
