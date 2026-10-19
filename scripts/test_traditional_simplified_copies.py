"""Simplified copies in the traditional dictionary (2026-10-19, the user:
"繁体库里为什么会有简体？"). The backfill gives every simplified row a
traditional row of its key through a character map, and the map leaves a
character with more than one traditional form as it is (于 for 於 or the
surname, 后 for 後 or 皇后, 干 for 乾, 幹 or 干涉), so 高于 went into the
traditional dictionary beside 高於 at the same weight and came first. The
backfill now gives the weight to a traditional twin of the key instead
(variant pairs of the aligned words), and the generated files lost such
copies: 1,371 clean and 10 Unihan rows whose text no OpenCC standard (s2t,
s2tw, s2twp, s2hk) or CEDICT keeps, where the key held a twin. Copies whose
twin is wrong itself stay (布 of a transliteration is no 佈). Copies without
a twin stay too: converting them char by char gets names and
transliterations wrong (朴信惠, 果戈里, 甩干 to 甩幹)."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from test_daily_whitespace_phrases import read_rows

DROPPED = {"gaoyu": ("高于", "高於"), "diyu": ("低于", "低於"), "houqi": ("后期", "後期"),
           "ganzao": ("干燥", "乾燥"), "fengfu": ("丰富", "豐富"), "daogu": ("稻谷", "稻穀"),
           "fanben": ("范本", "範本"), "henchou": ("很丑", "很醜"), "zaiyu": ("在于", "在於")}
# Copies whose twin is wrong itself.
KEPT = {"bulie": "布列", "buliesiteyaosai": "布列斯特要塞"}
# Traditional forms the standards keep beside a converted twin.
STANDARD = {"wutai": ("舞台", "舞臺"), "caikeyi": ("才可以", "纔可以"), "limian": ("裡面", "裏面")}


def keys(variant):
    rows = read_rows(f"dict_clean_{variant}.txt")
    rows.update(read_rows(f"dict_unihan_{variant}.txt"))
    result = {}
    for (pinyin, text), fields in rows.items():
        result.setdefault(pinyin.replace("'", ""), {})[text] = int(fields[0])
    return result


class TraditionalSimplifiedCopiesTests(unittest.TestCase):
    def test_backfill_gives_the_weight_to_a_traditional_twin(self):
        sc = {("gaoyu", "高于"): 1000, ("ganbei", "干杯"): 900, ("dian", "电"): 800}
        tc = {("gaoyu", "高於"): 800}
        result, stats = builder._backfill_tc_mapping_from_sc_with_char_map(
            sc, tc, {"电": "電"}, {("於", "于"), ("電", "电")})
        self.assertNotIn(("gaoyu", "高于"), result)
        self.assertEqual(1000, result[("gaoyu", "高於")])
        self.assertEqual(900, result[("ganbei", "干杯")])
        self.assertEqual(800, result[("dian", "電")])
        self.assertEqual(1, stats["tc_backfill_from_sc_twin"])

    def test_variant_pairs_hold_the_ambiguous_characters(self):
        pairs = builder._build_char_variant_pairs({"高於": {"高于"}, "皇后": {"皇后"}}, [("后期", "後期")])
        self.assertEqual({("於", "于"), ("後", "后")}, pairs)

    def test_generated_traditional_rows(self):
        rows = keys("tc")
        for pinyin, (copy, twin) in DROPPED.items():
            self.assertNotIn(copy, rows[pinyin], pinyin)
            self.assertIn(twin, rows[pinyin], pinyin)
        for pinyin, text in KEPT.items():
            self.assertIn(text, rows[pinyin], text)
        for pinyin, texts in STANDARD.items():
            for text in texts:
                self.assertIn(text, rows[pinyin], text)
        # The simplified dictionary is not touched.
        self.assertIn("高于", keys("sc")["gaoyu"])


if __name__ == "__main__":
    unittest.main()
