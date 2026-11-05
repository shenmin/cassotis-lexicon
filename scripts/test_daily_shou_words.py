"""Words of 2026-11-05: 首 with a character for the first of something (首字, 首句,
首段, 首张, 首战, 首周) and the words and short phrases it begins (首班车, 首次见面).
The user: "再帮我加一批：首字、首句、首善、……". Weighted as test_daily_hui_dong_words
(occurrences where the word is no part of a longer dictionary word, nor
before one that its last character begins, nor after one that its first
character ends); a word stays under every more frequent word of its key."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from test_daily_whitespace_phrases import read_rows
from test_daily_cuo_xiu_sha_shui_phrases import block

HEADERS = {'common': "# Everyday words, 2026-11-05, the more frequent ones: 首字, 首句 and 首善 (the user's examples), 首 with a character for the first of something: a part of a text (首段, 首篇, 首联), a thing counted (首张, 首场, 首笔), a first event (首战, 首飞, 首诊), a period (首周, 首月, 首年), and the words and short phrases it begins (首班车, 首映礼, 首先是, 首次出现, 首席科学家). Weighted as the blocks of 2026-11-04 (occurrences where the word is no part of a longer dictionary word, nor before one that its last character begins, nor after one that its first character ends); a word stays under every more frequent word of its key, an import's weight included; a requested word at least 400 where no more frequent word holds it lower.", 'less': '# Everyday words, 2026-11-05, the less frequent ones (首恶, 首犯, 首登, 首发价, 首次见面, 首发阵容), by the same weights; at weight 2 首胜, which went first without a context over the more frequent 收声, and the words the general text holds fewer than 50 times (首帧, 首吻, 首遍, 首单优惠, 首屏加载).'}
SIZES = {'common': 76, 'less': 106}
REQUESTED = ['首字', '首句', '首善']
HEADER_FORCED = '# Weighted anew on 2026-11-05: import-weight words that held a word of the batch under them on its key (手绘, 兽医, 寿险, 手语, 收银, 手记, 手链, 手笔, 手卷, 收工, 手相, 守时, 授业) and 首度, 首款, 首富 and 首选项 of earlier blocks, weighted as the blocks above.'
FORCED = [('shoudu', '首度', '首度', 600), ('shoukuan', '首款', '首款', 600), ('shoufu', '首富', '首富', 183), ('shouzhong', '首重', '首重', 114), ('shouqu', '首曲', '首曲', 200), ('shouxuanxiang', '首选项', '首選項', 400), ('shoushihe', '首饰盒', '首飾盒', 200), ('shoushidian', '首饰店', '首飾店', 200), ('shouxilvshi', '首席律师', '首席律師', 80), ('shouhui', '手绘', '手繪', 600), ('shouyi', '兽医', '獸醫', 156), ('shouxian', '寿险', '壽險', 265), ('shouyu', '手语', '手語', 634), ('shouyin', '收银', '收銀', 94), ('shouji', '手记', '手記', 106), ('shoulian', '手链', '手鍊', 601), ('shoubi', '手笔', '手筆', 600), ('shoujuan', '手卷', '手卷', 600), ('shougou', '受够', '受夠', 200), ('shouwan', '售完', '售完', 400), ('shouye', '守业', '守業', 401), ('shoujian', '收监', '收監', 183), ('shoushu', '寿数', '壽數', 400), ('shouxian', '寿限', '壽限', 200), ('shougong', '收工', '收工', 600), ('shoushi', '收市', '收市', 104), ('shouxiang', '手相', '手相', 600), ('shoufu', '收腹', '收腹', 182), ('shoushi', '守时', '守時', 103), ('shoufu', '收服', '收服', 181), ('shoushu', '手书', '手書', 601), ('shoushou', '瘦瘦', '瘦瘦', 183), ('shouye', '受业', '受業', 400), ('shoushi', '授时', '授時', 102), ('shoujuan', '手绢', '手絹', 401), ('shoujin', '收尽', '收盡', 200), ('shoujuan', '收卷', '收卷', 400), ('shoujin', '手巾', '手巾', 400), ('shougao', '瘦高', '瘦高', 200), ('shougong', '守宫', '守宮', 400), ('shouyu', '手谕', '手諭', 81), ('shouji', '手迹', '手跡', 105), ('shoushu', '收束', '收束', 600), ('shouye', '守夜', '守夜', 402), ('shoushi', '收尸', '收屍', 101), ('shouye', '授业', '授業', 600)]
ROWS = tuple(row[:4] for header in HEADERS.values() for row in block(header))


class DailyShouWordsTests(unittest.TestCase):
    def test_blocks(self):
        for group, header in HEADERS.items():
            rows = block(header)
            self.assertEqual(SIZES[group], len(rows), group)
            self.assertEqual({"exact_rank_no_contains"}, {row[4] for row in rows}, group)
        self.assertEqual(len(ROWS), len({(row[0], row[1]) for row in ROWS}))
        texts = {row[1] for row in ROWS}
        for word in REQUESTED:
            self.assertIn(word, texts, word)

    def test_kinds(self):
        for pinyin, sc, tc, _weight in ROWS + tuple(row[:4] for row in FORCED):
            self.assertIn(len(sc), (2, 3, 4, 5), sc)
            self.assertEqual(len(sc), len(tc), sc)
            self.assertNotIn("'", pinyin)
        keys = {(row[0], row[1]) for row in ROWS}
        for pinyin, word in (("shouzi", "首字"), ("shouju", "首句"), ("shoushan", "首善")):
            self.assertIn((pinyin, word), keys)

    def test_order(self):
        by_key = {}
        for (pinyin, text), fields in read_rows("dict_clean_sc.txt").items():
            by_key.setdefault(pinyin, {})[text] = int(fields[0])
        for pinyin, word, _tc, weight in ROWS + tuple(FORCED):
            self.assertEqual(weight, by_key[pinyin][word], word)
            others = [text for text, value in by_key[pinyin].items() if text != word and value == weight]
            # Under a word at 1 (an import's weight) the batch's words go to 0,
            # where they cannot be ordered (只招 and 只找 under 支招).
            if weight > 0:
                self.assertFalse(others, (pinyin, word))

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
        for index, mapping in enumerate(maps, 1):
            self.assertEqual({(row[0], row[index]): row[3] for row in ROWS}, mapping)

    def test_generated_entries_and_prior(self):
        for index, variant in enumerate(("sc", "tc"), 1):
            rows = read_rows(f"dict_clean_{variant}.txt")
            prior = read_rows(f"dict_completion_prior_{variant}.txt")
            for row in ROWS:
                self.assertEqual([str(row[3]), "no_contains"], rows[(row[0], row[index])])
                self.assertEqual(["80", "0", "0", "0", "0", "0", "0"], prior[(row[0], row[index])])
            for row in FORCED:
                self.assertEqual(str(row[3]), rows[(row[0], row[index])][0])


if __name__ == "__main__":
    unittest.main()
