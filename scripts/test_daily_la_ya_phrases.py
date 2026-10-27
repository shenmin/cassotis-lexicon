"""Everyday words of 2026-10-26 (the user's list: 部署到, and a verb or an
adjective of one character with the particle 啦 or 呀, 睡啦 to 跑啦 and 追呀 to
添呀; 着 read zhe, 重 zhong), the other particle of a listed character, more
characters with either particle, and verbs that take 到 as 部署到 does.
Weighted as test_daily_suo_bijiao_phrases (occurrences where the word is no
part of a longer dictionary word, nor before one that its last character
begins, nor after one that its first character ends): a requested word at
least at the least weight of a requested word, but below a commoner word of
its key (傻啦 under 莎拉, 填呀 under 天涯); the words with a particle kept from
20 occurrences in the general text, which writes them rarely, and none of the
added kinds that would take the first place from a word three times as
frequent whose last syllable is being typed (同样 at tongya)."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from test_daily_whitespace_phrases import read_rows
from test_daily_cuo_xiu_sha_shui_phrases import block, keys

HEADER_COMMON = "# Everyday words, 2026-10-26 (X啦, X呀, 部署到), the more frequent ones:"
HEADER_LESS = "# Everyday words, 2026-10-26 (X啦, X呀, 部署到), the less frequent ones"
REQUESTED = "部署到 睡啦 吃啦 喝啦 别啦 要啦 疼啦 傻啦 做啦 写啦 完啦 晚啦 玩啦 弯啦 热啦 冷啦 冰啦 病啦 红啦 亮啦 暗啦 跪啦 贵啦 开啦 关啦 着啦 看啦 听啦 喊啦 叫啦 点啦 打啦 伤啦 上啦 下啦 动啦 死啦 活啦 大啦 小啦 高啦 矮啦 低啦 胖啦 瘦啦 重啦 轻啦 美啦 丑啦 紧啦 松啦 深啦 浅啦 生啦 升啦 省啦 舔啦 加啦 减啦 填啦 添啦 跑啦 追呀 跑呀 睡呀 喝呀 别呀 要呀 疼呀 傻呀 写呀 玩呀 热呀 冷呀 跪呀 开呀 关呀 着呀 听呀 喊呀 叫呀 点呀 打呀 上呀 下呀 动呀 死呀 活呀 大呀 小呀 高呀 矮呀 低呀 胖呀 瘦呀 重呀 轻呀 美呀 丑呀 紧呀 松呀 深呀 浅呀 升呀 生呀 舔呀 加呀 减呀 填呀 添呀".split()
# (pinyin, word, other): word above other on the key
ABOVE = [("tingla", "听啦", "挺辣"), ("wanla", "玩啦", "晚啦"), ("wanla", "完啦", "弯啦")]
BELOW = [("shala", "傻啦", "莎拉"), ("tianya", "填呀", "天涯"), ("diya", "低呀", "抵押")]
ROWS = tuple(row[:4] for row in block(HEADER_COMMON) + block(HEADER_LESS))


class DailyLaYaTests(unittest.TestCase):
    def test_blocks(self):
        common, less = block(HEADER_COMMON), block(HEADER_LESS)
        self.assertEqual(137, len(common))
        self.assertEqual(52, len(less))
        self.assertEqual({"exact_rank_no_contains"}, {row[4] for row in common + less})
        self.assertEqual(len(ROWS), len({(row[0], row[1]) for row in ROWS}))
        texts = {row[1] for row in ROWS}
        for word in REQUESTED:
            self.assertIn(word, texts, word)
        self.assertIn(("bushudao", "部署到", "部署到"), {row[:3] for row in ROWS})
        # The readings the user gave, and Taiwan's form of zhe.
        self.assertIn(("zhela", "着啦", "著啦"), {row[:3] for row in ROWS})
        self.assertIn(("zhongya", "重呀", "重呀"), {row[:3] for row in ROWS})

    def test_order(self):
        rows = keys("sc")
        for pinyin, word, other in ABOVE:
            self.assertGreater(rows[pinyin][word], rows[pinyin][other], word)
        for pinyin, word, other in BELOW:
            self.assertLess(rows[pinyin][word], rows[pinyin][other], word)
        # No weight of the batch ties with another word of its key.
        by_key = {}
        for (pinyin, text), fields in read_rows("dict_clean_sc.txt").items():
            by_key.setdefault(pinyin, {})[text] = int(fields[0])
        for pinyin, word, _tc, weight in ROWS:
            others = [text for text, value in by_key[pinyin].items() if text != word and value == weight]
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


if __name__ == "__main__":
    unittest.main()
