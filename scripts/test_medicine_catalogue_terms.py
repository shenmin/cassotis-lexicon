"""The medicine layer's catalogue terms are exact only (2026-10-19, the user:
"对于'落下灰'这种专业词条，在输入中应该权重很低，全匹配时才候选"). The layer
(MeSH and the like) holds everyday words too, with the same evidence values
(深度学习 and 罗夏克墨迹测试 share every one), so the terms are the words of the
layer that the general text the character LM was trained on holds fewer than
50 times (manifests/medicine_catalogue_terms.tsv: 16,924 words; 落下灰 7
times, 深度学习 15,614). They keep their dictionary rows and are candidates
when typed in full; their completion prior is the specialist prior (layer 4)
and the completion lookup has no rows for them, so they are no Tab
completion: "luoxia" suggested 落下灰 of 放射性落下灰."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder

GEN = ROOT / "data/generated"
CATALOGUE = {"sc": ("落下灰", "罗夏克墨迹测试", "放射性落下灰"), "tc": ("落下灰", "羅夏克墨跡測試")}
EVERYDAY = {"sc": ("深度学习", "机器学习", "不确定", "癌症"), "tc": ("深度學習", "機器學習", "不確定", "癌症")}


def prior_rows(variant):
    rows = {}
    for line in (GEN / f"dict_completion_prior_{variant}.txt").read_text(encoding="utf-8").splitlines():
        fields = line.split("\t")
        if len(fields) >= 9 and not line.startswith("#"):
            rows.setdefault(fields[1], []).append(fields[2:9])
    return rows


def lookup_texts(variant):
    texts = set()
    for line in (GEN / f"dict_completion_lookup_{variant}.txt").read_text(encoding="utf-8").splitlines():
        fields = line.split("\t")
        if len(fields) >= 3:
            texts.add(fields[2])
    return texts


class MedicineCatalogueTermsTests(unittest.TestCase):
    def test_manifest(self):
        simplified, traditional = builder._load_medicine_catalogue_terms(
            ROOT / "manifests/medicine_catalogue_terms.tsv")
        self.assertGreater(len(simplified), 15000)
        self.assertGreater(len(traditional), 15000)
        for word in CATALOGUE["sc"]:
            self.assertIn(word, simplified)
        for word in EVERYDAY["sc"]:
            self.assertNotIn(word, simplified)
        self.assertIn("羅夏克墨跡測試", traditional)

    def test_generated_rows(self):
        for variant in ("sc", "tc"):
            prior, lookup = prior_rows(variant), lookup_texts(variant)
            for word in CATALOGUE[variant]:
                self.assertTrue(prior[word], word)
                for values in prior[word]:
                    self.assertEqual(["1", "0", "0", "1", "150", "4", "0"], values, word)
                self.assertNotIn(word, lookup, word)
            for word in EVERYDAY[variant]:
                self.assertTrue(all(values[5] != "4" for values in prior[word]), word)


if __name__ == "__main__":
    unittest.main()
