"""Polyphonic characters read by their meaning (2026-10-16). Words that came
without a reading were read character by character, and a polyphonic
character could take a reading its word does not have: 长篇大论 zhang,
角色扮演 jiao, 还原酶 hai, 繁花似锦 shi, 佛罗里达 fu; idioms even kept the
wrong reading beside the right one and above it (讨价还价 haijia 661 beside
huanjia 505, 地理学 delixue 716 beside dilixue 320). pinyin_overrides.tsv
gives each such word one reading, the one its neighbouring words and its
phrase give: chang or zhang by meaning, 似 si except in 似的, 佛 fo except in
仿佛. Words read both ways keep both (明朝, 睡着, 总长), and so do words whose
references misled (了不起, 势在必得, 三人行)."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from test_daily_whitespace_phrases import read_rows

OVERRIDES = ROOT / "manifests/pinyin_overrides.tsv"
HEADER = "# Polyphonic characters by their meaning, 2026-10-16:"
# (variant, text, readings it must have and no other)
SAMPLES = (
    ("sc", "长篇大论", {"changpiandalun"}),
    ("sc", "夜长梦多", {"yechangmengduo"}),
    ("sc", "好景不长", {"haojingbuchang"}),
    ("sc", "灵长", {"lingzhang"}),
    ("sc", "角色扮演", {"juesebanyan"}),
    ("sc", "还原酶", {"huanyuanmei"}),
    ("sc", "讨价还价", {"taojiahuanjia"}),
    ("sc", "慢性阻塞性肺疾病", {"manxingzusexingfeijibing"}),
    ("sc", "断点调试", {"duandiantiaoshi"}),
    ("sc", "风调雨顺", {"fengtiaoyushun"}),
    ("sc", "地理学", {"dilixue"}),
    ("sc", "花园地毯", {"huayuanditan"}),
    ("sc", "光阴似箭", {"guangyinsijian"}),
    ("sc", "佛罗里达", {"foluolida"}),
    ("sc", "人参养荣丸", {"renshenyangrongwan"}),
    ("sc", "卷土重来", {"juantuchonglai"}),
    ("sc", "一模一样", {"yimuyiyang"}),
    ("sc", "朝三暮四", {"zhaosanmusi"}),
    ("tc", "長篇大論", {"changpiandalun"}),
    ("tc", "討價還價", {"taojiahuanjia"}),
    ("tc", "光陰似箭", {"guangyinsijian"}),
    # left alone
    ("sc", "似的", {"shide"}),
    ("sc", "仿佛", {"fangfu", "pangfu"}),
    ("sc", "了不起", {"liaobuqi"}),
    ("sc", "长记性", {"zhangjixing"}),
    ("sc", "东家长西家短", {"dongjiachangxijiaduan"}),
    ("sc", "总长", {"zongzhang", "zongchang"}),
    ("sc", "明朝", {"mingchao", "mingzhao"}),
    ("sc", "睡着", {"shuizhao", "shuizhe"}),
    ("sc", "满满地", {"manmande"}),
)


def section():
    """(text, pinyin) rows of the section of the overrides."""
    rows, inside = [], False
    for line in OVERRIDES.read_text(encoding="utf-8").splitlines():
        if line.startswith(HEADER):
            inside = True
            continue
        if inside and line and not line.startswith("#"):
            rows.append(tuple(line.split("\t")[:2]))
    return rows


class PolyphoneReadingTests(unittest.TestCase):
    def test_overrides_load(self):
        overrides = builder._load_pinyin_overrides(OVERRIDES)
        rows = section()
        self.assertGreater(len(rows), 6000)
        self.assertEqual(len(rows), len({text for text, _pinyin in rows}))
        for text, pinyin in rows:
            self.assertEqual(builder._normalize_explicit_pinyin(pinyin), overrides[text])

    def test_generated_rows_follow_the_overrides(self):
        wanted = {text: pinyin.replace("'", "") for text, pinyin in section()}
        for variant in ("sc", "tc"):
            for pinyin, text in read_rows(f"dict_clean_{variant}.txt"):
                if text in wanted:
                    self.assertEqual(wanted[text], pinyin.replace("'", ""), (pinyin, text))

    def test_samples(self):
        rows = {variant: read_rows(f"dict_clean_{variant}.txt") for variant in ("sc", "tc")}
        for variant, text, readings in SAMPLES:
            found = {pinyin.replace("'", "") for pinyin, row_text in rows[variant] if row_text == text}
            self.assertEqual(readings, found, text)


if __name__ == "__main__":
    unittest.main()
