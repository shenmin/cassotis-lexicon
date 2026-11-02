"""Simplified and traditional readings kept apart (2026-11-02, the user:
"简繁体需要严格分开……两个独立的文件，互不干扰"). Each dictionary has its own
word overrides (pinyin_overrides.sc.tsv and .tc.tsv), and the reading of a
curated or vertical row, which is its simplified word's, reaches the
traditional text only when that text is the same word in the other script
(_is_same_word_in_tc). The one shared file gave the traditional 合著, which is
also the simplified 合着, the simplified hezhu alone; and a Taiwan term of a
vertical row (伺服器 for 服务器) took the simplified term's pinyin, fuwuqi. Such a
term reads by its own characters (the user's choice). 翻天复地, 地复天翻, 著色剂
and 重覆促发 read as misspellings in simplified text (翻天覆地, 着色剂, 重复促发)
and left the simplified dictionary; the traditional 著色劑 and 重覆促發 stay."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from test_daily_whitespace_phrases import read_rows
from test_medicine_catalogue_terms import lookup_texts, prior_rows

OVERRIDES = ROOT / "manifests/pinyin_overrides.sc.tsv"
# Traditional terms of vertical rows that are other words: their own reading,
# the simplified term and its reading.
OWN_READINGS = (
    ("伺服器", "sifuqi", "服务器", "fuwuqi"),
    ("伺服器負載", "sifuqifuzai", "服务器负载", "fuwuqifuzai"),
    ("資訊流", "zixunliu", "信息流", "xinxiliu"),
    ("小程式", "xiaochengshi", "小程序", "xiaochengxu"),
    ("執行狀態", "zhixingzhuangtai", "运行状态", "yunxingzhuangtai"),
    ("紐西蘭", "niuxilan", "新西兰", "xinxilan"),
    ("衣索比亞", "yisuobiya", "埃塞俄比亚", "aisaiebiya"),
    ("羅浮宮", "luofugong", "卢浮宫", "lufugong"),
    ("雪梨歌劇院", "xueligejuyuan", "悉尼歌剧院", "xinigejuyuan"),
    ("東京鐵塔", "dongjingtieta", "东京塔", "dongjingta"),
    ("聖伯多祿大殿", "shengboduoludadian", "圣彼得大教堂", "shengbidedajiaotang"),
    ("羅馬競技場", "luomajingjichang", "罗马斗兽场", "luomadoushouchang"),
    ("伊斯坦堡", "yisitanbao", "伊斯坦布尔", "yisitanbuer"),
    ("約翰尼斯堡", "yuehannisibao", "约翰内斯堡", "yuehanneisibao"),
    ("蒙特婁", "mengtelou", "蒙特利尔", "mengtelier"),
)
DROPPED_SC = ("翻天复地", "地复天翻", "著色剂", "重覆促发")
KEPT = {"sc": ("翻天覆地", "地覆天翻", "着色剂", "重复促发"), "tc": ("著色劑", "重覆促發", "翻天覆地")}
PAIRS = {("後", "后"), ("來", "来"), ("務", "务"), ("東", "东"), ("著", "着")}


def readings(rows, text):
    return {pinyin.replace("'", "") for pinyin, row_text in rows if row_text == text}


class VariantReadingTests(unittest.TestCase):
    def test_each_variant_has_its_own_overrides(self):
        sc, tc = builder._load_variant_pinyin_overrides(OVERRIDES)
        self.assertEqual("hezhu", sc["合著"])
        self.assertNotIn("合著", tc)
        for tc_text, own, sc_text, _sc_reading in OWN_READINGS:
            self.assertEqual(own, tc[tc_text], tc_text)
            self.assertNotIn(tc_text, sc)
            self.assertNotIn(sc_text, tc)

    def test_a_row_reading_reaches_the_same_word_only(self):
        same = builder._is_same_word_in_tc
        self.assertTrue(same("后来", "後來", PAIRS))
        self.assertTrue(same("着色", "著色", PAIRS))
        self.assertFalse(same("服务器", "伺服器", PAIRS))
        self.assertFalse(same("东京塔", "東京鐵塔", PAIRS))
        entries = [("服务器", "伺服器", 0.5, "fuwuqi", "computing", "test"),
                   ("后来", "後來", 0.5, "houlai", "daily", "test")]
        self.assertEqual({"服务器": "fuwuqi", "后来": "houlai", "後來": "houlai"},
                         builder._build_explicit_term_pinyin_override_map(entries, PAIRS))

    def test_post_rank_rows_read_another_word_by_the_traditional_overrides(self):
        entries = [("服务器", "伺服器", -5.0, "fuwuqi"), ("东京塔", "東京鐵塔", -5.0, "dongjingta"),
                   ("后来", "後來", -5.0, "houlai")]
        sc, tc = {}, {}
        stats = builder._inject_curated_daily_post_rank_exact_entries(
            sc, tc, entries, {"伺服器": "sifuqi"}, PAIRS)
        self.assertEqual({"fuwuqi", "dongjingta", "houlai"}, {pinyin for pinyin, _text in sc})
        self.assertEqual({("sifuqi", "伺服器"), ("houlai", "後來")}, set(tc))
        self.assertEqual(1, stats["curated_daily_post_rank_exact_tc_other_word_unread"])

    def test_generated_readings(self):
        rows = {variant: read_rows(f"dict_clean_{variant}.txt") for variant in ("sc", "tc")}
        self.assertEqual({"hezhu"}, readings(rows["sc"], "合著"))
        self.assertEqual({"hezhu", "hezhe"}, readings(rows["tc"], "合著"))
        for tc_text, own, sc_text, sc_reading in OWN_READINGS:
            self.assertEqual({own}, readings(rows["tc"], tc_text), tc_text)
            self.assertIn(sc_reading, readings(rows["sc"], sc_text), sc_text)

    def test_variant_spellings_left_the_simplified_dictionary(self):
        for word in DROPPED_SC:
            self.assertIn(word, builder.MULTI_CHAR_TERM_DROP_OVERRIDES)
        texts = {variant: {text for _pinyin, text in read_rows(f"dict_clean_{variant}.txt")}
                 for variant in ("sc", "tc")}
        prior, lookup = prior_rows("sc"), lookup_texts("sc")
        for word in DROPPED_SC:
            self.assertFalse(word in texts["sc"] or word in prior or word in lookup, word)
        for variant, words in KEPT.items():
            for word in words:
                self.assertTrue(word in texts[variant], word)


if __name__ == "__main__":
    unittest.main()
