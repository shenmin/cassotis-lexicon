"""Daily actions and negations keep explicit readings and conservative ranks."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder

ROWS = (
    ("gaowan", "搞完", "搞完", 480),
    ("nongwan", "弄完", "弄完", 480),
    ("secha", "色差", "色差", 560),
    ("shige", "是个", "是個", 120),
    ("zaoci", "造词", "造詞", 420),
    ("wushan", "误删", "誤刪", 480),
    ("gelun", "各轮", "各輪", 240),
    ("liangkeshu", "两棵树", "兩棵樹", 420),
    ("keshu", "棵树", "棵樹", 220),
    ("buzhuang", "不装", "不裝", 300),
    ("buzhuang", "不撞", "不撞", 240),
    ("butao", "不讨", "不討", 160),
    ("butao", "不逃", "不逃", 300),
    ("butao", "不套", "不套", 180),
    ("buhai", "不嗨", "不嗨", 160),
    ("buhui", "不悔", "不悔", 260),
    ("bujian", "不尖", "不尖", 120),
    ("bujian", "不建", "不建", 180),
    ("bujian", "不剪", "不剪", 240),
    ("bushen", "不深", "不深", 260),
    ("buqian", "不签", "不簽", 260),
    ("buqian", "不浅", "不淺", 280),
    ("buqian", "不前", "不前", 180),
    ("buqian", "不欠", "不欠", 260),
    ("youbu", "又不", "又不", 420),
    ("youbuke", "又不可", "又不可", 360),
    ("yibuke", "亦不可", "亦不可", 260),
    ("yibu", "亦不", "亦不", 280),
    ("yebuke", "也不可", "也不可", 480),
    ("shuifen", "水粉", "水粉", 300),
    ("shuifense", "水粉色", "水粉色", 320),
    ("xile", "细了", "細了", 0),
    ("cule", "粗了", "粗了", 240),
    ("meiganshang", "美感上", "美感上", 240),
    ("chuda", "触达", "觸達", 420),
    ("tuceng", "图层", "圖層", 620),
    ("xiuba", "修吧", "修吧", 240),
    ("buba", "不把", "不把", 260),
    ("baoming", "包名", "包名", 260),
    ("faxingbao", "发行包", "發行包", 360),
    ("busha", "不杀", "不殺", 320),
    ("buta", "不踏", "不踏", 180),
    ("zhizai", "只在", "只在", 0),
    ("jinzai", "仅在", "僅在", 420),
    ("yike", "亦可", "亦可", 320),
    ("douke", "都可", "都可", 520),
    ("haike", "还可", "還可", 420),
)


def read_rows(name):
    rows = {}
    for line in (ROOT / "data/generated" / name).read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        fields = line.split("\t")
        key = tuple(fields[:2])
        if key in rows:
            raise AssertionError(f"duplicate entry: {key}")
        rows[key] = fields[2:]
    return rows


class DailyNegationDesignPhraseTests(unittest.TestCase):
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
        builder._inject_curated_daily_post_rank_exact_entries(*maps, exact)
        for index, mapping in enumerate(maps, 1):
            self.assertEqual({(row[0], row[index]): row[3] for row in ROWS}, mapping)

    def test_generated_entries_and_existing_bujian(self):
        for index, variant in enumerate(("sc", "tc"), 1):
            rows = read_rows(f"dict_clean_{variant}.txt")
            for row in ROWS:
                self.assertEqual([str(row[3]), "no_contains"], rows[(row[0], row[index])])
            existing = "不减" if variant == "sc" else "不減"
            self.assertEqual(["1"], rows[("bujian", existing)])
            self.assertNotIn(("sechai", "色差"), rows)
            self.assertNotIn(("duke", "都可"), rows)
            for query, leader_sc, leader_tc, new_sc, new_tc in (
                ("bujian", "不见", "不見", "不剪", "不剪"),
                ("bujian", "部件", "部件", "不建", "不建"),
                ("buhui", "不会", "不會", "不悔", "不悔"),
                ("baoming", "报名", "報名", "包名", "包名"),
                ("xile", "洗了", "洗了", "细了", "細了"),
                ("shuifen", "水分", "水分", "水粉", "水粉"),
                ("shige", "十个", "十個", "是个", "是個"),
                ("shige", "诗歌", "詩歌", "是个", "是個"),
                ("zhizai", "旨在", "旨在", "只在", "只在"),
                ("yike", "一刻", "一刻", "亦可", "亦可"),
            ):
                leader, new = (leader_sc, new_sc) if variant == "sc" else (leader_tc, new_tc)
                self.assertGreater(int(rows[(query, leader)][0]), int(rows[(query, new)][0]))

    def test_no_fabricated_corpus_support(self):
        for index, variant in enumerate(("sc", "tc"), 1):
            rows = read_rows(f"dict_completion_prior_{variant}.txt")
            for row in ROWS:
                self.assertEqual((80, 0, 0, 0, 0, 0, 0),
                                 tuple(map(int, rows[(row[0], row[index])])))


if __name__ == "__main__":
    unittest.main()
