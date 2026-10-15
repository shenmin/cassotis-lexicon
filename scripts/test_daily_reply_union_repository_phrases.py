"""Colloquial replies with na (那行, 那就好), set operations (并集, 差集) and code
repository terms (公共库, 标准库, 公共服务) keep explicit readings and moderate exact
ranks."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from test_daily_whitespace_phrases import read_rows

# Readings are written as they are typed, without a syllable separator.
REQUESTED = (
    ("naxing", "那行", "那行", 380),
    ("bingji", "并集", "並集", 460),
    ("gonggongku", "公共库", "公共庫", 380),
)

# Words of the same families for which the engine offered no whole candidate
# or a rarer homophone first.
RELATED = (
    ("nahao", "那好", "那好", 360),
    ("najiuhao", "那就好", "那就好", 380),
    ("najiuxing", "那就行", "那就行", 360),
    ("nakeyi", "那可以", "那可以", 320),
    ("nasuanle", "那算了", "那算了", 340),
    ("nahaoba", "那好吧", "那好吧", 340),
    ("naxingba", "那行吧", "那行吧", 320),
    ("nahaode", "那好的", "那好的", 300),
    ("nabuxing", "那不行", "那不行", 320),
    ("nahaixing", "那还行", "那還行", 280),
    ("nameishi", "那没事", "那沒事", 280),
    ("nazheyang", "那这样", "那這樣", 300),
    ("najiuzheyang", "那就这样", "那就這樣", 320),
    ("najiusuanle", "那就算了", "那就算了", 300),
    ("natinghao", "那挺好", "那挺好", 280),
    ("nataihaole", "那太好了", "那太好了", 300),
    ("nazaban", "那咋办", "那咋辦", 260),
    ("nazouba", "那走吧", "那走吧", 260),
    ("nameibanfa", "那没办法", "那沒辦法", 260),
    ("chaji", "差集", "差集", 260),
    ("buji", "补集", "補集", 330),
    ("chaoji", "超集", "超集", 200),
    ("miji", "幂集", "冪集", 140),
    ("duichencha", "对称差", "對稱差", 200),
    ("qubingji", "取并集", "取並集", 260),
    ("qujiaoji", "取交集", "取交集", 260),
    ("qiubingji", "求并集", "求並集", 240),
    ("qiujiaoji", "求交集", "求交集", 240),
    ("gonggongcangku", "公共仓库", "公共倉庫", 300),
    ("bendicangku", "本地仓库", "本地倉庫", 200),
    ("zhuku", "主库", "主庫", 240),
    ("congku", "从库", "從庫", 200),
    ("ziku", "字库", "字庫", 360),
    ("ziku", "子库", "子庫", 200),
    ("biaozhunku", "标准库", "標準庫", 300),
    ("kaiyuanku", "开源库", "開源庫", 260),
    ("jingxiangku", "镜像库", "鏡像庫", 220),
    ("leiku", "类库", "類庫", 240),
    ("gongjuku", "工具库", "工具庫", 260),
    ("zujianku", "组件库", "組件庫", 260),
    ("sucaiku", "素材库", "素材庫", 280),
    ("tuku", "图库", "圖庫", 320),
    ("hexinku", "核心库", "核心庫", 240),
    ("anliku", "案例库", "案例庫", 220),
    ("yangbenku", "样本库", "樣本庫", 220),
    ("ceshiku", "测试库", "測試庫", 260),
    ("shengchanku", "生产库", "生產庫", 220),
    ("kaifaku", "开发库", "開發庫", 220),
    ("zhengshiku", "正式库", "正式庫", 220),
    ("gonggongfuwu", "公共服务", "公共服務", 480),
    ("gonggongzujian", "公共组件", "公共組件", 300),
    ("gonggongmokuai", "公共模块", "公共模塊", 280),
    ("gonggonghanshu", "公共函数", "公共函數", 260),
    ("gonggongfangfa", "公共方法", "公共方法", 260),
    ("gonggongjiekou", "公共接口", "公共接口", 280),
    ("gonggongpeizhi", "公共配置", "公共配置", 260),
    ("gonggongdaima", "公共代码", "公共代碼", 260),
    ("neibuban", "内部版", "內部版", 260),
    ("gongkaiban", "公开版", "公開版", 280),
    ("waibuban", "外部版", "外部版", 220),
    ("sanpingtai", "三平台", "三平臺", 260),
    ("shuangpingtai", "双平台", "雙平臺", 260),
    ("quanpingtai", "全平台", "全平臺", 300),
    ("zimokuai", "子模块", "子模塊", 260),
)

ROWS = REQUESTED + RELATED

# Existing words whose weight this batch sets (pinyin, simplified, traditional,
# weight). Without a context the short promotion table put 病机 above the
# requested 并集 at any weight of 并集 and at 病机 100 or more, and 土庫 above
# 圖庫 (traditional) at 200 or more.
FORCED = (
    ("bingji", "病机", "病機", 50),
    ("tuku", "土库", "土庫", 100),
)

# pinyin, the commoner word (simplified, traditional), the added word
# (simplified, traditional) that stays below it.
COMMON_FIRST = (
    ("chaji", "茶几", "茶几", "差集", "差集"),
    ("buji", "不济", "不濟", "补集", "補集"),
    ("buji", "不及", "不及", "补集", "補集"),
    ("buji", "补给", "補給", "补集", "補集"),
    ("chaoji", "超级", "超級", "超集", "超集"),
    ("miji", "密集", "密集", "幂集", "冪集"),
)

# pinyin, the added word (simplified, traditional), the existing word
# (simplified, traditional) it goes above.
ABOVE = (
    ("naxing", "那行", "那行", "纳星", "納星"),
    ("bingji", "并集", "並集", "病机", "病機"),
    ("tuku", "图库", "圖庫", "土库", "土庫"),
)

# Rows (pinyin, simplified) that stay at the lowest weights: at an ordinary
# weight they took the first place of a commoner word or changed a benchmark
# sentence.
LOW_WEIGHT = (
)


class DailyReplyUnionRepositoryTests(unittest.TestCase):
    def test_rows_are_distinct(self):
        self.assertEqual(len(ROWS), len({(row[0], row[1]) for row in ROWS}))
        self.assertEqual(len(ROWS), len({(row[0], row[2]) for row in ROWS}))
        # Homophones among the additions never tie.
        weights = {}
        for row in ROWS:
            weights.setdefault(row[0], []).append(row[3])
        for pinyin, values in weights.items():
            self.assertEqual(len(values), len(set(values)), pinyin)

    def test_explicit_readings_and_ranks_survive_rebuild(self):
        entries, _ = builder._parse_curated_daily_phrase_entries(
            (ROOT / "manifests/curated_daily_supplement_phrases.tsv").read_bytes(), 2)
        wanted = {(row[0], row[1]) for row in ROWS}
        selected = [entry for entry in entries if (entry[3], entry[0]) in wanted]
        regular, exact = builder._partition_curated_daily_post_rank_exact_entries(selected)
        self.assertFalse(regular)
        self.assertEqual(len(ROWS), len(exact))
        maps = ({}, {})
        builder._inject_curated_daily_post_rank_exact_entries(*maps, exact)
        builder._inject_curated_daily_post_rank_exact_entries(*maps, exact)
        for index, mapping in enumerate(maps, 1):
            self.assertEqual({(row[0], row[index]): row[3] for row in ROWS}, mapping)

    def test_generated_entries(self):
        for index, variant in enumerate(("sc", "tc"), 1):
            rows = read_rows(f"dict_clean_{variant}.txt")
            for row in ROWS:
                self.assertEqual([str(row[3]), "no_contains"], rows[(row[0], row[index])])

    def test_preserve_common_homophones(self):
        for variant, common_index, added_index in (("sc", 1, 3), ("tc", 2, 4)):
            rows = read_rows(f"dict_clean_{variant}.txt")
            for pair in COMMON_FIRST:
                self.assertGreater(int(rows[(pair[0], pair[common_index])][0]),
                                   int(rows[(pair[0], pair[added_index])][0]), pair)

    def test_requested_order(self):
        for variant, added_index, existing_index in (("sc", 1, 3), ("tc", 2, 4)):
            rows = read_rows(f"dict_clean_{variant}.txt")
            for pair in ABOVE:
                self.assertGreater(int(rows[(pair[0], pair[added_index])][0]),
                                   int(rows[(pair[0], pair[existing_index])][0]), pair)

    def test_forced_weights(self):
        entries, _ = builder._parse_curated_daily_phrase_entries(
            (ROOT / "manifests/curated_daily_supplement_phrases.tsv").read_bytes(), 2)
        wanted = {(row[0], row[1]) for row in FORCED}
        selected = [entry for entry in entries if (entry[3], entry[0]) in wanted]
        regular, exact = builder._partition_curated_daily_post_rank_exact_entries(selected)
        self.assertFalse(regular)
        self.assertEqual(len(FORCED), len(exact))
        for index, variant in enumerate(("sc", "tc"), 1):
            rows = read_rows(f"dict_clean_{variant}.txt")
            for row in FORCED:
                self.assertEqual(str(row[3]), rows[(row[0], row[index])][0], row)

    def test_low_weight_rows_stay_low(self):
        weights = {(row[0], row[1]): row[3] for row in ROWS}
        for key in LOW_WEIGHT:
            self.assertLessEqual(weights[key], 2, key)

    def test_no_fabricated_corpus_support(self):
        for index, variant in enumerate(("sc", "tc"), 1):
            rows = read_rows(f"dict_completion_prior_{variant}.txt")
            for row in ROWS:
                self.assertEqual((80, 0, 0, 0, 0, 0, 0),
                                 tuple(map(int, rows[(row[0], row[index])])))


if __name__ == "__main__":
    unittest.main()
