"""The traditional dictionary writes Taiwan's forms (2026-10-20, the user:
"统一繁体固定使用台湾用字字形，处理掉混用"): manifests/traditional_taiwan_forms.tsv,
applied to the generated traditional files by normalize_traditional_forms.py.
Before, it held both standards (因為 beside 爲了, 這裡 beside 這裏, 喫飯 and
羣眾 beside 吃了 and 觀眾)."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import normalize_traditional_forms as normalizer

GEN = ROOT / "data/generated"
FORMS = normalizer.load_forms(ROOT / normalizer.MANIFEST)
PRESENT = {"weile": "為了", "zheli": "這裡", "limian": "裡面", "chifan": "吃飯", "qunzhong": "群眾",
           "xianxinghuigui": "線性迴歸", "zhaoji": "著急", "shenmi": "神秘"}
GONE = {"weile": "爲了", "zheli": "這裏", "limian": "裏面", "chifan": "喫飯", "qunzhong": "羣眾",
        "xianxinghuigui": "綫性迴歸", "zhaoji": "着急", "shenmi": "神祕"}


def texts(name, pinyin_col, text_col, columns):
    rows = {}
    for line in (GEN / name).read_text(encoding="utf-8").splitlines():
        fields = line.split("\t")
        if not line.startswith("#") and len(fields) >= columns:
            rows.setdefault(fields[pinyin_col].replace("'", ""), set()).add(fields[text_col])
    return rows


class TraditionalTaiwanFormsTests(unittest.TestCase):
    def test_manifest(self):
        self.assertGreater(len(FORMS), 90)
        self.assertEqual("為", FORMS["爲"])
        self.assertEqual("著", FORMS["着"])
        self.assertEqual("裡", FORMS["裏"])
        # Taiwan writes these as well, beside the other form.
        for kept in "泄台煙濕醣塚餬鎚纍陞踰綑滙":
            self.assertNotIn(kept, FORMS, kept)
        self.assertFalse(set(FORMS.values()) & set(FORMS), "a form maps to another")

    def test_words_take_the_forms_and_characters_stay(self):
        self.assertEqual("為了", normalizer.normalize_text("爲了", FORMS))
        self.assertEqual("爲", normalizer.normalize_text("爲", FORMS))
        self.assertEqual("店|裡", normalizer.normalize_path("店|裏", FORMS))
        self.assertEqual("裏", normalizer.normalize_path("裏", FORMS))

    def test_generated_files_hold_no_other_form(self):
        for name, text_col, columns in (("dict_clean_tc.txt", 1, 3), ("dict_completion_prior_tc.txt", 1, 3),
                                        ("dict_completion_lookup_tc.txt", 2, 4)):
            for line in (GEN / name).read_text(encoding="utf-8").splitlines():
                fields = line.split("\t")
                if line.startswith("#") or len(fields) < columns or len(fields[text_col]) < 2:
                    continue
                self.assertFalse(set(fields[text_col]) & set(FORMS), (name, fields[text_col]))
        for name in ("dict_lm_transition_tc.txt", "dict_query_path_prior_tc.txt"):
            for line in (GEN / name).read_text(encoding="utf-8").splitlines():
                fields = line.split("\t")
                if len(fields) >= 3 and len(fields[1].replace("|", "")) >= 2:
                    self.assertFalse(set(fields[1]) & set(FORMS), (name, fields[1]))

    def test_character_ngrams_hold_taiwans_forms(self):
        # Counted on text in OpenCC's forms; merged, 眼裡 has both counts.
        for name in ("dict_char_lm_tc.txt", "dict_char_reverse_lm_tc.txt"):
            for line in (GEN / name).read_text(encoding="utf-8").splitlines()[1:]:
                self.assertFalse(set(line.split("\t")[0]) & set(FORMS), (name, line))
        grams = {}
        for line in (GEN / "dict_char_lm_tc.txt").read_text(encoding="utf-8").splitlines()[1:]:
            fields = line.split("\t")
            grams[fields[0]] = int(fields[1])
        self.assertIn("眼裡", grams)
        self.assertNotIn("眼裏", grams)

    def test_words(self):
        rows = texts("dict_clean_tc.txt", 0, 1, 3)
        for pinyin, text in PRESENT.items():
            self.assertIn(text, rows[pinyin], text)
        for pinyin, text in GONE.items():
            self.assertNotIn(text, rows.get(pinyin, set()), text)
        # A character stays: a variant can be typed on purpose, but Taiwan's
        # form comes first (the inventory had 喫, 羣, 牀 and no 吃, 群, 床).
        singles = texts("dict_unihan_tc.txt", 0, 1, 3)
        self.assertIn("裏", singles["li"])
        weights = {}
        for name in ("dict_unihan_tc.txt", "dict_clean_tc.txt"):
            for line in (GEN / name).read_text(encoding="utf-8").splitlines():
                fields = line.split("\t")
                if not line.startswith("#") and len(fields) >= 3 and len(fields[1]) == 1:
                    weights[(fields[0], fields[1])] = max(weights.get((fields[0], fields[1]), 0), int(fields[2]))
        for (pinyin, text), weight in weights.items():
            if text in FORMS:
                self.assertGreater(weights[(pinyin, FORMS[text])], weight, (pinyin, text))
        # The simplified dictionary is not touched.
        self.assertIn("着急", texts("dict_clean_sc.txt", 0, 1, 3)["zhaoji"])


if __name__ == "__main__":
    unittest.main()
