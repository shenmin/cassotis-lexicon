"""事实 under shishi weighted anew on 2026-11-23 (the user, of the short-word cases without a context of v2.9.0:
事实 -> 实施 has to be fixed): one above 实施 in both variants, where the short-word choice without a context of the
distilled character LM (stage E2) put 实施 first by a hair. One weight orders both variants."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from test_daily_whitespace_phrases import read_rows
from test_daily_cuo_xiu_sha_shui_phrases import block

HEADER_FORCED = '# Reweighted 2026-11-23 (exact_rank, the weight / 1000): 事实 one above 实施 under shishi in both variants, where the short-word choice without a context of the distilled character LM (stage E2) put 实施 first by a hair (the user asked for 事实).'
FORCED = (('shishi', '事实', '事實', 629),)
PASSED = {"sc": "实施", "tc": "實施"}


class DailyReweightShishiTests(unittest.TestCase):
    def test_block(self):
        rows = block(HEADER_FORCED)
        self.assertEqual({"exact_rank"}, {row[4] for row in rows})
        self.assertEqual(set(FORCED), {tuple(row[:4]) for row in rows})

    def test_generated_weights(self):
        for index, variant in enumerate(("sc", "tc"), 1):
            rows = read_rows(f"dict_clean_{variant}.txt")
            for pinyin, sc, tc, weight in FORCED:
                self.assertEqual(str(weight), rows[(pinyin, (sc, tc)[index - 1])][0], variant)
                self.assertLess(int(rows[(pinyin, PASSED[variant])][0]), weight, variant)
                others = [text for (key, text), fields in rows.items()
                          if key == pinyin and text != (sc, tc)[index - 1] and int(fields[0]) == weight]
                self.assertFalse(others, variant)


if __name__ == "__main__":
    unittest.main()
