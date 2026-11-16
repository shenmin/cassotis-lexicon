"""Words of 2026-11-16, the second batch of the day: airlines by their short and full names
(东航, 川航, 厦航, 春秋航空, 吉祥航空), the words of a flight (经停, 联程, 选座, 退改签, 送机), X一下 of an everyday
verb with the user's 调一下 read tiao (说一下, 找一下, 聊一下), and 作罢 under 做吧. The user: "再加一批：东航、……",
then "再加：调（tiao）一下；另外，帮我调一下：做吧>作罢". Words of the families at an import weight (登机 and 接机
at 1, 航班号 10) are weighted anew. Weighted as test_daily_hunshu_words (occurrences where the word is no part of a
longer dictionary word, nor before one that its last character begins, nor after one that its first character
ends); a word stays under every more frequent word of its key."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from test_daily_whitespace_phrases import read_rows
from test_daily_cuo_xiu_sha_shui_phrases import block

HEADERS = {'common': "# Everyday words, 2026-11-16, the more frequent ones: airlines by their short and full names (the user's 东航; 川航, 厦航, 深航, 新航, 美联航, 达美, 春秋航空, 国际航空, 新加坡航空, 香港航空), the words of a flight (选座, 退改签, 经停, 联程, 航班延误, 机上, 大飞机, 国内航班, 机组人员, 民航局, 机场大巴, 燃油附加费) and X一下 of an everyday verb (the user's 调一下, read tiao, above 跳一下; 说一下, 找一下, 聊一下, 提一下, 发一下, 用一下, 打一下 above 大一下) with the other common readings of their keys (注意下 above 煮一下, 及以下 above 记一下, 眨一下, 焯一下), weighted by the general text as the batches before.", 'less': '# Everyday words, 2026-11-16, the less frequent ones (山航, 澳航, 荷航, 亚航 and 捷星 above 牙行 and 戒行, 吉祥航空, 厦门航空, 东航物流, 商飞, 送机 above 松鸡, 值机柜台, 随身行李, 常旅客, 乘务长, 准点率, 贵宾厅, 猜一下 above 踩一下, 教一下, 抱一下, 借一下, 催一下, 见一下 and 剪一下 above 煎一下, 划一下, 撞一下, 跑一下, 歇一下), by the same weights; 中国南航, 网上值机, 电子登机牌, 行李转盘, 早班机, 航变, 窄体机, 认一下, 求一下, 喝一下, 请一下, 叫一下, 传一下, 待一下, 举一下, 躺一下 and other words the general text seldom writes as words, at 2.'}
SIZES = {'common': 63, 'less': 218}
REQUESTED = ['东航', '调一下']
HEADER_FORCED = "# Weighted anew on 2026-11-16: import-weight words of the families and of their keys that the general text holds far more often than their weights say (舱位, 航班号, 国际航班, 安检口, 沪杭, 连城, 劫机, 暴击); 登机 above 登基, 接机 and 接济 above 截击, by everyday use; 作罢 set just under 做吧 on the user's word."
FORCED = [('dengji', '登机', '登機', 181), ('cangwei', '舱位', '艙位', 600), ('hangbanhao', '航班号', '航班號', 400), ('anjiankou', '安检口', '安檢口', 200), ('guojihangban', '国际航班', '國際航班', 600), ('jieji', '接机', '接機', 520), ('huhang', '沪杭', '滬杭', 600), ('liancheng', '连城', '連城', 279), ('jieji', '接济', '接濟', 515), ('jieji', '劫机', '劫機', 458), ('baoji', '暴击', '暴擊', 169), ('zuoba', '作罢', '作罷', 279)]
ROWS = tuple(row[:4] for header in HEADERS.values() for row in block(header))


class DailyDonghangWordsTests(unittest.TestCase):
    def test_blocks(self):
        for group, header in HEADERS.items():
            rows = block(header)
            self.assertEqual(SIZES[group], len(rows), group)
            self.assertEqual({"exact_rank_no_contains"}, {row[4] for row in rows}, group)
        self.assertEqual(len(ROWS), len({(row[0], row[1]) for row in ROWS}))
        texts = {row[1] for row in ROWS} | {row[1] for row in FORCED}
        for word in REQUESTED:
            self.assertIn(word, texts, word)

    def test_kinds(self):
        for pinyin, sc, tc, _weight in ROWS + tuple(row[:4] for row in FORCED):
            self.assertIn(len(sc), (2, 3, 4, 5, 6), sc)
            self.assertEqual(len(sc), len(tc), sc)
            self.assertNotIn("'", pinyin)
        keys = {(row[0], row[1]) for row in ROWS + tuple(FORCED)}
        # Readings by the meaning: 调一下 of the user (tiao), 厦航 of Xiamen (xia), 乘务长 (zhang).
        for pinyin, word in (("tiaoyixia", "调一下"), ("xiahang", "厦航"), ("chengwuzhang", "乘务长")):
            self.assertIn((pinyin, word), keys)

    def test_order_on_shared_keys(self):
        # The everyday words of a key stay above the batch's: none listed.
        for variant, index in (("sc", 0), ("tc", 1)):
            rows = read_rows(f"dict_clean_{variant}.txt")
            for pinyin, pair in ():
                (high, low) = (word[index] for word in pair)
                self.assertGreater(int(rows[(pinyin, high)][0]), int(rows[(pinyin, low)][0]), (variant, pinyin))

    def test_zuoba_order(self):
        # The user's order of zuoba: 做吧 above 作罢.
        for variant, words in (("sc", ("做吧", "作罢")), ("tc", ("做吧", "作罷"))):
            rows = read_rows(f"dict_clean_{variant}.txt")
            self.assertGreater(int(rows[("zuoba", words[0])][0]), int(rows[("zuoba", words[1])][0]), variant)

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
