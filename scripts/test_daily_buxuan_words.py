"""Words of 2026-11-24: the user's words and their kinds: a verb or an
adjective of one character before the particles 啊 and 嘛, a word of place or kind before 版 (editions), 不 before a
verb, 薅 before its complement, a numeral or a demonstrative before 轮 (rounds), a verb before 给, before 成 (its
result) and before 点 (a little of it), and a verb before 码 (a code). The user: "日常库继续添加：不选、给点、本版、该版、小曼、海峰表、也下架、做一轮、四轮、改从、我本机、
贴给、才最、在靠、跑成、四角星、爽啊、帅啊、……、前版、上版、下版、后版、……", then "再加一个：发码、收码". Words of the families' keys at an import weight are
weighted anew. Weighted as test_daily_wohen_words (occurrences where the word is no part of a longer dictionary word,
nor before one that its last character begins, nor after one that its first character ends); a word stays under
every more frequent word of its key."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from test_daily_whitespace_phrases import read_rows
from test_daily_cuo_xiu_sha_shui_phrases import block

HEADERS = {'common': "# Everyday words, 2026-11-24, the more frequent ones: the user's 不选, 给点, 本版, 该版, 小曼, 海峰表, 也下架, 做一轮, 四轮, 改从, 我本机, 贴给, 才最, 在靠, 跑成, 四角星, 也怪, 指哪打哪, 薅出, 薅出来, 艾玛, 哎妈, 癌吗, 不帮, 不薅, 不肏, 不操, 前版, 上版, 下版, 后版, 发码, 收码 and their verbs and adjectives before 啊 and 嘛 (爽啊, 帅啊, 帮嘛, 是嘛), and their kinds the lexicon lacked: a verb or an adjective of one character before 啊 and 嘛 (爱啊, 大啊, 累啊, 找啊), a word of place or kind before 版 (此版, 两版, 整版), 不 before a verb (不抱, 不碰, 不抢, 不约), a numeral or a demonstrative before 轮 (本轮, 上轮, 五轮), a verb before 给 (写给, 寄给, 说给), before 成 (堆成, 剪成, 修成, 学成) and before 点 (吃点, 喝点, 带点, 赚点), a verb before 码, a code (验码, 亮码, 刷码, 赋码), weighted by the general text as the batches before; 不选, 不约, 带点, 讲给 and 慢啊 above a word of their key by everyday conversation, and a verb or an adjective before 啊 or 嘛 above a word conversation writes ten times as seldom, unless the general text writes that word thirty times as often (对嘛, 点嘛, 多嘛, 过嘛, 做嘛, 懒啊, 困啊, 近啊).", 'less': '# Everyday words, 2026-11-24, the less frequent ones (verbs and adjectives before 啊 and 嘛, 不 before a verb, verbs before 给, 成, 点 and 码, 薅 before its complement, numerals before 轮 and words before 版 that the general text seldom writes), by the same weights; words the general text seldom writes as words at 2 or below.'}
SIZES = {'common': 225, 'less': 314}
REQUESTED = ['不选', '给点', '本版', '该版', '小曼', '海峰表', '也下架', '做一轮', '四轮', '改从', '我本机', '贴给', '才最', '在靠', '跑成', '四角星', '爽啊', '帅啊', '靓啊', '美啊', '疼啊', '痛啊', '帮啊', '棒啊', '拉啊', '跳啊', '听啊', '抓啊', '抓嘛', '帮嘛', '拉嘛', '跳嘛', '听嘛', '是嘛', '做嘛', '别啊', '别嘛', '也怪', '指哪打哪', '薅出', '薅出来', '薅嘛', '薅啊', '写嘛', '写啊', '发嘛', '送嘛', '高啊', '矮啊', '癌啊', '癌吗', '艾玛', '哎妈', '跑嘛', '干啊', '艹啊', '肏啊', '操啊', '操嘛', '肏嘛', '下啊', '下嘛', '上嘛', '不肏', '不操', '贴嘛', '贴啊', '靠啊', '考嘛', '考啊', '不帮', '不薅', '前版', '上版', '下版', '后版', '发码', '收码']
HEADER_FORCED = "# Weighted anew on 2026-11-24: the words of the batch's keys at an import weight by the general text (本班, 补强, 两半, 牵绊, 政论, 页码, 对骂, 贺电, 汗马, 不保, 补报, 布包, 不薄, 绩点, 价码); 河马 above 荷马 and 盒马 by everyday conversation, and 同班 and 天马 right under the first word of their key (铜板, 天麻), which conversation would put them above."
FORCED = [('benban', '本班', '本班', 600), ('bubao', '不保', '不保', 469), ('bubao', '不薄', '不薄', 399), ('bubao', '布包', '布包', 467), ('bubao', '补报', '補報', 468), ('buchang', '不畅', '不暢', 183), ('bupai', '补拍', '補拍', 200), ('buqiang', '补强', '補強', 600), ('duima', '对骂', '對罵', 400), ('hanma', '汗马', '汗馬', 351), ('hedian', '贺电', '賀電', 400), ('hema', '河马', '河馬', 900), ('huigei', '汇给', '匯給', 198), ('jiama', '价码', '價碼', 159), ('jiana', '迦纳', '迦納', 200), ('jiaocheng', '搅成', '攪成', 151), ('jidian', '绩点', '績點', 89), ('kaima', '开骂', '開罵', 200), ('liangban', '两半', '兩半', 600), ('liangban', '良伴', '良伴', 200), ('manma', '漫骂', '漫罵', 199), ('qianban', '牵绊', '牽絆', 600), ('tianma', '天马', '天馬', 999), ('tongban', '同班', '同班', 998), ('tongban', '铜版', '銅版', 400), ('yema', '页码', '頁碼', 559), ('zhenglun', '政论', '政論', 600)]
ROWS = tuple(row[:4] for header in HEADERS.values() for row in block(header))


class DailyBuxuanWordsTests(unittest.TestCase):
    def test_blocks(self):
        for group, header in HEADERS.items():
            rows = block(header)
            self.assertEqual(SIZES[group], len(rows), group)
            self.assertEqual({"exact_rank_no_contains"}, {row[4] for row in rows}, group)
        self.assertEqual(len(ROWS), len({(row[0], row[1]) for row in ROWS}))
        texts = {row[1] for row in ROWS} | {row[1] for row in FORCED}
        for word in REQUESTED:
            self.assertIn(word, texts, word)
        forced = block(HEADER_FORCED)
        self.assertEqual({"exact_rank"}, {row[4] for row in forced})
        self.assertEqual({row[:4] for row in FORCED}, {tuple(row[:4]) for row in forced})

    def test_kinds(self):
        for pinyin, sc, tc, _weight in ROWS + tuple(row[:4] for row in FORCED):
            self.assertIn(len(sc), (2, 3, 4), sc)
            self.assertEqual(len(sc), len(tc), sc)
            self.assertNotIn("'", pinyin)
        keys = {(row[0], row[1]) for row in ROWS + tuple(FORCED)}
        # Readings by the meaning: 靓 liang, 干 gan of doing, 薅 hao, 哪 na.
        for pinyin, word in (("lianga", "靓啊"), ("gana", "干啊"), ("haochu", "薅出"), ("zhinadana", "指哪打哪")):
            self.assertIn((pinyin, word), keys)

    def test_order(self):
        by_key = {}
        for (pinyin, text), fields in read_rows("dict_clean_sc.txt").items():
            by_key.setdefault(pinyin, {})[text] = int(fields[0])
        for pinyin, word, _tc, weight in ROWS + tuple(FORCED):
            self.assertEqual(weight, by_key[pinyin][word], word)
            others = [text for text, value in by_key[pinyin].items() if text != word and value == weight]
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
