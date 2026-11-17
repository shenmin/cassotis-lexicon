"""Words of 2026-11-17: the user's 也挺, 也很, 存成, 新开, 新冠, 但我, 该吃, 该还 (read huan), 我配,
贵点, 长点 (read chang), 升级完, 倒满, 弹了 (read tan), 秒睡, 美签, 个号 and the rest of the list, and the words of their
series the lexicon lacked (也太, 存一下, 咋知道, 新租, 待付款, 该休息, 便宜点, 加完, 秒变, 申根签, 主账号). The user:
"再加一批词：也挺、也很、存成、……；有些系列的尽量再拓展一些词库缺少的，全部权衡放入高低频，和赋予合适的权重，确保基准不降低".
Words of the families at an import weight are weighted anew. Weighted as test_daily_donghang_words (occurrences where
the word is no part of a longer dictionary word, nor before one that its last character begins, nor after one that its
first character ends); a word stays under every more frequent word of its key."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from test_daily_whitespace_phrases import read_rows
from test_daily_cuo_xiu_sha_shui_phrases import block

HEADERS = {'common': "# Everyday words, 2026-11-17, the more frequent ones: the user's 也挺, 也很, 存成, 为空, 咋搞, 新开, 新冠, 小差 (read chai), 待处理, 但我, 该吃, 该还 (read huan), 我配, 贵点, 长点 (read chang), 升级完, 生了, 倒满, 看它, 安全地, 他又, 弹了 (read tan), 秒睡, 美签, 个号, 高低频, 慢一点, 很顶, 太顶, 非常顶, 有点顶, 顶顶, 鼎鼎 and the rest of the list, and the words of their series (也太, 也想, 也不错, 存起来, 咋知道, 新认识, 但还是, 该休息, 便宜了, 忙完, 秒变, 旅游签, 备用号, 多一点, 好一点, 小心一点, 顶不住), with 我们有, 你们有, 他们有 and 安全的 above 我们又, 你们又, 他们又 and 安全地, weighted by the general text as the batches before; 也太, 也想, 也挺, 少点, 该睡 and 该去 above words the general text writes about as often, by everyday use.", 'less': '# Everyday words, 2026-11-17, the less frequent ones (存好, 咋滴, 咋过, 咋睡, 新租, 小甜饼, 待审核, 待测试, 该听 above 该停, 该醒, 该回家, 细点, 稳点, 厚点, 升上去, 搬完, 秒批, 电子签, 商务签, 主账号, 生不了 above 升不了, 认真一点, 淡一点), by the same weights; 存一下, 咋没, 待付款, 待发货, 该下班, 淡点, 秒赞, 秒评, 留学签, 辣一点, 超顶 and other words the general text seldom writes as words, at 2.'}
SIZES = {'common': 283, 'less': 210}
REQUESTED = ['也挺', '也很', '存成', '存为', '为空', '咋搞', '新开', '新关', '新冠', '新办', '新看', '新写', '新搞', '新稿', '新告', '新买', '新拿', '新取', '新想', '小差异', '小钗', '小差', '小甜', '多陪', '待处', '待处理', '处理项', '但我', '但你', '但她', '该吃', '该喝', '该睡', '该起', '该出', '该回', '该来', '该走', '该写', '该存', '该开', '该关', '该看', '改听', '该买', '该拿', '该换', '该还', '该付', '该欠', '该要', '该拒', '我配', '你配', '他配', '她配', '贵点', '贵了', '多点', '少点', '长点', '短点', '深点', '浅点', '暗点', '冷点', '升级完', '升完级', '升完', '咋升', '新升', '多升', '多生', '该升', '生了', '升了', '海峰', '用满', '倒满', '灌满', '灌完', '倒完', '我艹', '看它', '安全地', '他又', '她又', '解了', '再弹', '新弹', '弹了', '多弹', '少弹', '多贪', '多探', '多碳', '该贪', '少碳', '秒封', '秒过', '秒答', '秒关', '秒开', '秒会', '秒秒', '秒睡', '秒起', '秒完', '秒撤', '秒退', '秒溜', '美签', '日签', '新签', '韩签', '澳签', '加签', '欧签', '英签', '德签', '法签', '意签', '个号', '主号', '次号', '高低频', '不降低', '慢一点', '很顶', '太顶', '非常顶', '顶顶', '鼎鼎', '有点顶']
HEADER_FORCED = "# Weighted anew on 2026-11-17: import-weight words of the batch's keys that the general text holds far more often than their weights say (亮点, 洗碗, 糕点, 富豪, 庙会, 心声, 心学, 免签, 生蚝, 进店, 端点), and words of the series at an import weight (高点, 看完, 走完, 打完); 秒回 above 庙会 by everyday use."
FORCED = [('gaodian', '高点', '高點', 601), ('tieman', '贴满', '貼滿', 400), ('kanwan', '看完', '看完', 600), ('zouwan', '走完', '走完', 600), ('dawan', '打完', '打完', 601), ('daichu', '带出', '帶出', 600), ('dawan', '大腕', '大腕', 600), ('duandian', '端点', '端點', 600), ('fuhao', '富豪', '富豪', 600), ('gaodian', '糕点', '糕點', 600), ('haifeng', '海丰', '海豐', 400), ('jindian', '进店', '進店', 600), ('liangdian', '亮点', '亮點', 600), ('mianqian', '免签', '免簽', 601), ('mianqian', '棉签', '棉簽', 602), ('miaohui', '秒回', '秒回', 602), ('miaohui', '庙会', '廟會', 601), ('ruandian', '软垫', '軟墊', 400), ('shaosheng', '哨声', '哨聲', 401), ('shenghao', '生蚝', '生蠔', 600), ('shengman', '盛满', '盛滿', 600), ('wocao', '我操', '我操', 341), ('xiandian', '限电', '限電', 600), ('xinling', '心领', '心領', 200), ('xinshang', '心上', '心上', 600), ('xinshang', '心伤', '心傷', 400), ('xinsheng', '心声', '心聲', 279), ('xinxiang', '馨香', '馨香', 283), ('xinxue', '心学', '心學', 469), ('xinyang', '信阳', '信陽', 600), ('xinyang', '新阳', '新陽', 9), ('xiwan', '洗碗', '洗碗', 279), ('zahuo', '杂活', '雜活', 400), ('zaji', '杂记', '雜記', 600), ('danta', '蛋塔', '蛋塔', 98)]
ROWS = tuple(row[:4] for header in HEADERS.values() for row in block(header))


class DailyYetingWordsTests(unittest.TestCase):
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
        # Readings by the meaning: 该还 of the user (huan), 长点 (chang), 弹了 (tan), 解了 (jie), 小差 (chai), 秒会 (hui),
        # 安全地 (de).
        for pinyin, word in (("gaihuan", "该还"), ("changdian", "长点"), ("tanle", "弹了"), ("jiele", "解了"),
                             ("xiaochai", "小差"), ("miaohui", "秒会"), ("anquande", "安全地")):
            self.assertIn((pinyin, word), keys)

    def test_order_on_shared_keys(self):
        # The everyday words of a key stay above the batch's: none listed.
        for variant, index in (("sc", 0), ("tc", 1)):
            rows = read_rows(f"dict_clean_{variant}.txt")
            for pinyin, pair in ():
                (high, low) = (word[index] for word in pair)
                self.assertGreater(int(rows[(pinyin, high)][0]), int(rows[(pinyin, low)][0]), (variant, pinyin))

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
