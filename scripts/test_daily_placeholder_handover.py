"""Weights and canonical readings for UI and handover vocabulary."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORDS = {
    "sc": [("xinjian", "\u65b0\u5efa", 780), ("zhanwei", "\u5360\u4f4d", 620),
           ("huangei", "\u6362\u7ed9", 380), ("meiye", "\u6bcf\u9875", 620),
           ("meigaomei", "\u7f8e\u9ad8\u6885", 480)],
    "tc": [("xinjian", "\u65b0\u5efa", 780), ("zhanwei", "\u4f54\u4f4d", 620),
           ("huangei", "\u63db\u7d66", 380), ("meiye", "\u6bcf\u9801", 620),
           ("meigaomei", "\u7f8e\u9ad8\u6885", 480)],
}


class DailyPlaceholderHandoverTests(unittest.TestCase):
    def test_brand_completion_lookup_is_present(self):
        for variant in WORDS:
            with (ROOT / f"data/generated/dict_completion_lookup_{variant}.txt").open(encoding="utf-8") as stream:
                found = [line.rstrip().split("\t") for line in stream
                         if line.startswith("meigao\tmeigaomei\t\u7f8e\u9ad8\u6885\t")]
            self.assertEqual(1, len(found), variant)
            self.assertEqual("480", found[0][3], variant)

    def test_generated_weights_readings_and_priority(self):
        for variant, words in WORDS.items():
            rows = {}
            with (ROOT / f"data/generated/dict_clean_{variant}.txt").open(encoding="utf-8") as stream:
                for line in stream:
                    fields = line.rstrip().split("\t")
                    if len(fields) >= 3:
                        rows[tuple(fields[:2])] = fields[2:]
            for py, text, weight in words:
                with self.subTest(variant=variant, word=text):
                    self.assertEqual([str(weight), "no_contains"], rows[(py, text)])
            self.assertGreater(int(rows[("xinjian", "\u65b0\u5efa")][0]),
                               int(rows[("xinjian", "\u4fe1\u4ef6")][0]))
            self.assertGreater(int(rows[("xinjian", "\u4fe1\u4ef6")][0]), 500)
            self.assertNotIn(("huanji", words[2][1]), rows)
            returned = "\u8fd8\u7ed9" if variant == "sc" else "\u9084\u7d66"
            self.assertGreater(int(rows[("huangei", returned)][0]),
                               int(rows[("huangei", words[2][1])][0]))
            self.assertGreater(int(rows[("meiye", words[3][1])][0]),
                               int(rows[("meiye", "\u6bcf\u591c")][0]))


if __name__ == "__main__":
    unittest.main()
