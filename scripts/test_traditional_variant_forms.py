"""The traditional dictionary takes each character's common traditional form
(2026-11-03). The builder's simplified-to-traditional map had taken a rare
variant for some characters (鉅 for 巨, 葯 for 药, 噹 for 当, 囌 for 苏, 喫 for
吃): converted by it, 巨人 became 鉅人 and 農藥 農葯, and words in a form no
source writes lost their signal of use and left the traditional dictionary
(巨人, 吃喝, 吃力). TC_CHAR_MAP_CORRECTIONS puts OpenCC's default form into the
map, the backfill of traditional rows from simplified ones converts by
OpenCC's phrases first (吞嚥, 叮噹, 痊癒), and the curated manifests' traditional
columns hold no character only simplified text writes."""
from pathlib import Path
import os
import sys
import unittest

import opencc

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder

GEN = ROOT / "data/generated"
PRESENT = {"juren": "巨人", "jutou": "巨頭", "juxing": "巨型", "juda": "巨大", "chihe": "吃喝",
           "chili": "吃力", "guimi": "閨蜜", "zhenshiqingkuang": "真實情況", "dangran": "當然",
           "nongyao": "農藥", "suzhou": "蘇州", "laoyao": "老么", "quanyu": "痊癒", "tunyan": "吞嚥",
           "dingdang": "叮噹", "bingzao": "病灶", "zaotai": "灶台", "jushixibao": "巨噬細胞",
           "chaojijuxing": "超級巨星", "juxibaobingdu": "巨細胞病毒", "jubian": "巨變", "nawodang": "拿我當",
           "jiannan": "艱難", "shiwujuxi": "事無鉅細"}
GONE = {"juren": "鉅人", "juda": "鉅大", "dangran": "噹然", "nongyao": "農葯", "chihe": "喫喝",
        "suzhou": "囌州", "laoyao": "老麼", "jushixibao": "鉅噬細胞", "chaojijuxing": "超級鉅星",
        "juxibaobingdu": "鉅細胞病毒", "jubian": "鉅變", "nawodang": "拿我噹"}


def clean_texts(name):
    rows = {}
    for line in (GEN / name).read_text(encoding="utf-8").splitlines():
        fields = line.split("\t")
        if not line.startswith("#") and len(fields) >= 3:
            rows.setdefault(fields[0], set()).add(fields[1])
    return rows


def simplified_only_characters():
    """Characters OpenCC converts and writes in no traditional form."""
    folder = Path(os.path.dirname(opencc.__file__)) / "dictionary"
    keys, values = set(), set()
    for name in ("STCharacters.txt", "TWVariants.txt"):
        for line in (folder / name).read_text(encoding="utf-8").splitlines():
            if "\t" in line:
                key, value = line.split("\t", 1)
                if name == "STCharacters.txt":
                    keys.add(key)
                values.update(value.split())
    s2tw = opencc.OpenCC("s2tw")
    return {key for key in keys - values if s2tw.convert(key) != key}


class TraditionalVariantFormsTests(unittest.TestCase):
    def test_corrections(self):
        for simp_ch, trad_ch in builder.TC_CHAR_MAP_CORRECTIONS.items():
            self.assertEqual(1, len(simp_ch))
            self.assertEqual(1, len(trad_ch), simp_ch)
        mapping = {"巨": "鉅", "药": "葯", "当": "噹", "苏": "囌", "吃": "喫", "么": "麼", "灶": "竈", "后": "後"}
        sc_chars, tc_chars = set(mapping), set()
        stats = builder._apply_tc_char_map_corrections(mapping, sc_chars=sc_chars, tc_chars=tc_chars)
        self.assertEqual({"药": "藥", "当": "當", "苏": "蘇", "后": "後"}, mapping)
        # A character kept as it is belongs to both scripts.
        self.assertEqual({"巨", "吃", "么", "灶"}, tc_chars)
        self.assertEqual(4, stats["tc_char_map_corrections_removed"])
        self.assertEqual(3, stats["tc_char_map_corrections_replaced"])

    def test_backfill_converts_by_phrases(self):
        phrases = {"吞咽": {"吞嚥"}, "疗愈": {builder.TC_EXTRA_PHRASES["疗愈"]}}
        char_map = {"疗": "療", "药": "藥"}
        convert = lambda text: builder._convert_sc_text_to_tc_with_phrase_hints(text, phrases, char_map)
        sc = {("tunyan", "吞咽"): 497, ("liaoyu", "疗愈"): 198, ("nongyao", "农药"): 440}
        tc, stats = builder._backfill_tc_mapping_from_sc_with_char_map(sc, {}, char_map, convert_text=convert)
        self.assertEqual({("tunyan", "吞嚥"), ("liaoyu", "療癒"), ("nongyao", "农藥")}, set(tc))
        self.assertEqual(3, stats["tc_backfill_from_sc_added"])
        # OpenCC's phrase 巨细 -> 鉅細 would match inside 巨细胞.
        phrases = {"巨细": {"鉅細"}, "巨细胞": {builder.TC_EXTRA_PHRASES["巨细胞"]}}
        char_map = {"细": "細", "胞": "胞", "病": "病", "毒": "毒"}
        self.assertEqual("巨細胞病毒", builder._convert_sc_text_to_tc_with_phrase_hints("巨细胞病毒", phrases, char_map))
        self.assertEqual("事無鉅細", builder._convert_sc_text_to_tc_with_phrase_hints(
            "事无巨细", {"巨细": {"鉅細"}}, {"无": "無"}))

    def test_extra_phrases(self):
        simplified_only = simplified_only_characters()
        for sc_word, tc_word in builder.TC_EXTRA_PHRASES.items():
            self.assertEqual(len(sc_word), len(tc_word), sc_word)
            self.assertFalse(set(tc_word) & simplified_only, tc_word)

    def test_generated_words(self):
        rows = clean_texts("dict_clean_tc.txt")
        for pinyin, text in PRESENT.items():
            self.assertIn(text, rows.get(pinyin, set()), text)
        for pinyin, text in GONE.items():
            self.assertNotIn(text, rows.get(pinyin, set()), text)
        # The simplified dictionary is not touched.
        sc_rows = clean_texts("dict_clean_sc.txt")
        for pinyin, text in (("juren", "巨人"), ("chihe", "吃喝"), ("nongyao", "农药")):
            self.assertIn(text, sc_rows[pinyin], text)

    def test_curated_traditional_columns(self):
        # A column copied from the simplified word (闺蜜) or holding OpenCC's
        # list of forms ("此話一齣 一出") gave no traditional row.
        simplified_only = simplified_only_characters()
        self.assertIn("闺", simplified_only)
        self.assertNotIn("么", simplified_only)
        for name in ("curated_daily_phrases.tsv", "curated_daily_supplement_phrases.tsv"):
            for line in (ROOT / "manifests" / name).read_text(encoding="utf-8").splitlines():
                if not line or line.startswith("#"):
                    continue
                tc = line.split("\t")[1]
                self.assertNotIn(" ", tc, (name, line))
                self.assertFalse(set(tc) & simplified_only, (name, line))


if __name__ == "__main__":
    unittest.main()
