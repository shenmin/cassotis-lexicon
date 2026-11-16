"""Words of 2026-11-16: 混 before a verb or noun, mixing (混输 of input methods, 混码, 混动, 混检),
只 as "only" before a verb (只提, 只换, 只修, 只坐, 只上, 只下), 止 before what it stops (止疼, 止泻, 止盈),
指交, and a unit of text before 首, 尾, 末 or 头, its beginning or end (句尾, 段首, 文末, 章首, 篇末; 行尾, 行末
and 行首 read hang). The user: "帮我再添加一批词：混输、混码、只提、只指、只办、……、止疼、指交、句尾、句末、段尾、
……、词首、词头、……". Words of the families at an import weight (混音 at 1, 词尾 61, 字首 1) are weighted anew,
and 行末, which an import read xingmo, takes hangmo. Weighted as test_daily_zhefeng_words (occurrences where the
word is no part of a longer dictionary word, nor before one that its last character begins, nor after one that
its first character ends); a word stays under every more frequent word of its key."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from test_daily_whitespace_phrases import read_rows
from test_daily_cuo_xiu_sha_shui_phrases import block

HEADERS = {'common': '# Everyday words, 2026-11-16, the more frequent ones: 混 before a verb or noun, mixing (the user\'s 混输 and 混码; 混动, 混居, 混频, 混流, 混色), 只 as "only" before a verb (the user\'s 只提, 只换, 只跟, 只更, 只修, 只坐, 只上, 只下, 只报, 只保, 只包, 只泡, 只服 and more; 只待, 只配, 只图, 只闻) and the user\'s 只和 (only with), 止 before what it stops (the user\'s 止疼; 止泻, 止盈, 止呕, 止于), the user\'s 指交, and a unit of text before 首, 尾, 末 or 头 (the user\'s 句尾, 句末, 段首, 文末, 列首, 词头, and 行尾, 行末 and 行首 read hang; 卷尾, 卷末, 篇末, 字尾), eyewear (the user\'s 依视路, 蔡司 and 渐进片; 万新, 屈光, 视光, 膜层, 近视眼镜, 眼镜店, 防蓝光) and 你 before an adverb, a modal or a preposition (the user\'s 你又; 你都, 你别, 你得, 你跟, 你给; 你总 and 你只 at 2, where they turned benchmark cases), weighted by the general text as the batches before.', 'less': "# Everyday words, 2026-11-16, the less frequent ones (混肥, 混业, 混检, 混群, 只送, 只抓, 只租, 只挂, 止滑, 止戈, 章末, 队首, 表尾, 豪雅, 非球面, 多焦点, 树脂镜片, 你挺, 你瞎), by the same weights; 混拼, 只登, 只烤, 只跳, 章首, 链头, 链尾, 帧首, 帧尾 and other words the general text seldom writes as words, at 2; 只讨 first on its key, on the user's word."}
SIZES = {'common': 146, 'less': 236}
REQUESTED = ['混输', '混码', '只提', '只指', '只办', '只搬', '只换', '只跟', '只更', '只抄', '只吵', '只炒', '只摸', '只骗', '只贴', '只喜', '只吸', '只欠', '只爬', '只热', '只修', '只造', '只坐', '只上', '只下', '只疼', '只报', '只保', '只包', '只抱', '只泡', '只服', '止疼', '指交', '句尾', '句末', '段尾', '段末', '文尾', '文末', '列尾', '行尾', '行末', '列末', '话尾', '话末', '词末', '句首', '句头', '段首', '段头', '文首', '文头', '列首', '行首', '话首', '词首', '词头', '只和', '依视路', '蔡司', '渐进片', '你又']
HEADER_FORCED = "# Weighted anew on 2026-11-16: import-weight words of the families and of their keys that the general text holds far more often than their weights say (混音, 止渴, 止境, 词尾, 字首, 居首, 断尾, 列位, 支座, 至宝, 之余, 芥末, 指路, 婚介, 度数, 读数, 镜框, 弱视, 弱势, 瞳距, 逆光); 直营 raised above 支应, which the general text writes a sixth as often; 指套 raised above 制陶 on the user's word, with 只讨 above both; 行末 reads hangmo, the end of a line, where an import had read it xingmo."
FORCED = [('hangmo', '行末', '行末', 331), ('dushu', '度数', '度數', 600), ('jingkuang', '镜框', '鏡框', 600), ('ruoshi', '弱视', '弱視', 600), ('kuangjiayanjing', '框架眼镜', '框架眼鏡', 400), ('tongju', '瞳距', '瞳距', 200), ('jingtui', '镜腿', '鏡腿', 200), ('yanjingbu', '眼镜布', '眼鏡布', 200), ('hunyin', '混音', '混音', 600), ('zhike', '止渴', '止渴', 439), ('zhijing', '止境', '止境', 401), ('ciwei', '词尾', '詞尾', 104), ('zishou', '字首', '字首', 400), ('jushou', '居首', '居首', 266), ('jushou', '巨兽', '巨獸', 265), ('duanwei', '断尾', '斷尾', 69), ('liewei', '列位', '列位', 600), ('zhizuo', '支座', '支座', 279), ('zhibao', '至宝', '至寶', 183), ('duanshou', '短寿', '短壽', 400), ('zhigen', '植根', '植根', 600), ('zhigen', '指根', '指根', 601), ('zhiyu', '之余', '之餘', 601), ('zhishu', '支书', '支書', 153), ('zhiqing', '知青', '知青', 279), ('jiemo', '芥末', '芥末', 439), ('zhilu', '指路', '指路', 279), ('zhiliao', '质料', '質料', 328), ('zhili', '质粒', '質粒', 279), ('zhishou', '职守', '職守', 277), ('zhixiao', '职校', '職校', 156), ('hunjie', '婚介', '婚介', 600), ('dushu', '读数', '讀數', 601), ('ruoshi', '弱势', '弱勢', 601), ('wanxin', '玩心', '玩心', 401), ('niguang', '逆光', '逆光', 600), ('zhiying', '直营', '直營', 600), ('zhitao', '指套', '指套', 601)]
ROWS = tuple(row[:4] for header in HEADERS.values() for row in block(header))


class DailyHunshuWordsTests(unittest.TestCase):
    def test_blocks(self):
        for group, header in HEADERS.items():
            rows = block(header)
            self.assertEqual(SIZES[group], len(rows), group)
            self.assertEqual({"exact_rank_no_contains"}, {row[4] for row in rows}, group)
        self.assertEqual(len(ROWS), len({(row[0], row[1]) for row in ROWS}))
        # 行末 is a forced row: an import had read it xingmo.
        texts = {row[1] for row in ROWS} | {row[1] for row in FORCED}
        for word in REQUESTED:
            self.assertIn(word, texts, word)

    def test_kinds(self):
        for pinyin, sc, tc, _weight in ROWS + tuple(row[:4] for row in FORCED):
            self.assertIn(len(sc), (2, 3, 4, 5), sc)
            self.assertEqual(len(sc), len(tc), sc)
            self.assertNotIn("'", pinyin)
        keys = {(row[0], row[1]) for row in ROWS + tuple(FORCED)}
        # Readings by the meaning: 行 of a line of text (hang, the user), 只更 updates (geng), 混行 (xing), 你都 (dou), 你得
        # of "must" (dei), 单光 (guang).
        for pinyin, word in (("hangwei", "行尾"), ("hangmo", "行末"), ("hangshou", "行首"), ("zhigeng", "只更"),
                             ("hunxing", "混行"), ("nidou", "你都"), ("nidei", "你得"), ("danguang", "单光")):
            self.assertIn((pinyin, word), keys)
        rows = read_rows("dict_clean_sc.txt")
        for pinyin, word in (("xingwei", "行尾"), ("xingmo", "行末"), ("xingshou", "行首")):
            self.assertNotIn((pinyin, word), rows)

    def test_order_on_shared_keys(self):
        # The everyday words of a key stay above the batch's: 华为 above 话尾, 举手 above 句首, 巨头 above 句头,
        # 猎手 above 列首, 列为 above 列尾, 制造 above 只造, 制作 above 只坐, 之前 above 只欠, 对手 above 队首,
        # 你有 above 你又, 你想 above 你向, 时光 above 视光, 好呀 above 豪雅, 读书 above 度数.
        for variant, index in (("sc", 0), ("tc", 1)):
            rows = read_rows(f"dict_clean_{variant}.txt")
            for pinyin, pair in (('huawei', (('华为', '華為'), ('话尾', '話尾'))), ('jushou', (('举手', '舉手'), ('句首', '句首'))), ('jutou', (('巨头', '巨頭'), ('句头', '句頭'))), ('lieshou', (('猎手', '獵手'), ('列首', '列首'))), ('liewei', (('列为', '列為'), ('列尾', '列尾'))), ('zhizao', (('制造', '製造'), ('只造', '只造'))), ('zhizuo', (('制作', '製作'), ('只坐', '只坐'))), ('zhiqian', (('之前', '之前'), ('只欠', '只欠'))), ('duishou', (('对手', '對手'), ('队首', '隊首'))), ('niyou', (('你有', '你有'), ('你又', '你又'))), ('nixiang', (('你想', '你想'), ('你向', '你向'))), ('shiguang', (('时光', '時光'), ('视光', '視光'))), ('haoya', (('好呀', '好呀'), ('豪雅', '豪雅'))), ('dushu', (('读书', '讀書'), ('度数', '度數')))):
                (high, low) = (word[index] for word in pair)
                self.assertGreater(int(rows[(pinyin, high)][0]), int(rows[(pinyin, low)][0]), (variant, pinyin))

    def test_zhitao_order(self):
        # The user's order of zhitao: 只讨 above 指套 above 制陶.
        for variant, words in (("sc", ("只讨", "指套", "制陶")), ("tc", ("只討", "指套", "製陶"))):
            rows = read_rows(f"dict_clean_{variant}.txt")
            weights = [int(rows[("zhitao", word)][0]) for word in words]
            self.assertGreater(weights[0], weights[1], variant)
            self.assertGreater(weights[1], weights[2], variant)

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
