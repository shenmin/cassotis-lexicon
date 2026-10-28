"""Words of 2026-10-27 in three kinds, weighted as test_daily_suo_bijiao_phrases
(occurrences where the word is no part of a longer dictionary word, nor before
one that its last character begins, nor after one that its first character
ends; a requested word at least at the least weight of a requested word, but
below a commoner word of its key):
- words of 帧 (a frame of video or of data): 关键帧 was no word ("guanjianzhen"
  gave 关键针), nor 帧数. The words the user took (关键帧, 帧数, 逐帧, 掉帧, 丢帧,
  插帧, 补帧, 每秒帧数) and more of the kind (帧数 under 真书, 逐帧 under 助阵,
  补帧 under 不振);
- verbs with their result: 补回 and 挤掉, which the user asked for, and more
  of 补, 挤 and X掉 (补回 under 不会 and 不悔, 挤掉 under 基调);
- the X啦 and X呀 of 2026-10-26 that batch had left out because, typed as
  their key, they come before a word still being typed (用啦 before 用来): the
  word the keys spell goes first (the user: "单证 本来全拼就是danzheng，
  danzhen不应该被他挤掉").
补发, 补完 and 推掉, at an import's weight, are weighted by the same rules (补发
under 步伐, 不法 and 步法, which the general text holds more often)."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from test_daily_whitespace_phrases import read_rows
from test_daily_cuo_xiu_sha_shui_phrases import block, keys

HEADERS = {'common': '# Words of 帧, 2026-10-27, the more frequent ones: the words the user took (关键帧, 帧数, 逐帧, 掉帧, 丢帧, 插帧, 补帧, 每秒帧数) and more of the kind (每一帧, 数据帧, 帧图像). Weighted as the blocks of 2026-10-20 (occurrences where the word is no part of a longer dictionary word, nor before one that its last character begins, nor after one that its first character ends); a requested word goes below a commoner word of its key (帧数 under 真书, 逐帧 under 助阵, 补帧 under 不振).', 'less': '# Words of 帧, 2026-10-27, the less frequent ones of the same kind, by the same weights (每帧, 多帧, 视频帧, 帧同步, 高帧率).', 'verb_common': '# Verbs with their result, 2026-10-27, the more frequent ones: 补回 and 挤掉, which the user asked for, and more of 补, 挤 and X掉 (补回来, 补录, 挤到, 戒掉, 刷掉, 卸掉). Weighted as the blocks of 2026-10-20; a requested word goes below a commoner word of its key (补回 under 不会 and 不悔, 挤掉 under 基调).', 'verb_less': '# Verbs with their result, 2026-10-27, the less frequent ones, by the same weights (补进, 补满, 挤走, 挤下去, 涂掉).', 'back_common': "# Everyday words of 2026-10-26 put back, 2026-10-27, the more frequent ones: X啦 and X呀 that batch had left out because, typed as their key, they come before a word still being typed (用啦 at yongla before 用来); the word the keys spell goes first. By that batch's weights (多呀, 飞呀, 贵呀).", 'back_less': '# Everyday words of 2026-10-26 put back, 2026-10-27, the less frequent ones (说啦, 买啦, 快啦, 过啦, 醒啦, 拿呀).'}
SIZES = {'common': 11, 'less': 17, 'verb_common': 14, 'verb_less': 11, 'back_common': 4, 'back_less': 34}
HEADER_FORCED = "# Words at an import's weight, 2026-10-27, weighted by the same rules: 补发 (under 步伐, 不法 and 步法, which the general text holds more often), 补完 and 推掉 (under 退掉)."
REQUESTED = ['关键帧', '帧数', '逐帧', '掉帧', '丢帧', '插帧', '补帧', '每秒帧数', '补回', '挤掉']
PUT_BACK = ['买啦', '会呀', '会啦', '哭啦', '唱呀', '坏呀', '坏啦', '多呀', '学啦', '少呀', '快呀', '快啦', '慢呀', '拿呀', '掉啦', '早呀', '烦啦', '熟啦', '用呀', '用啦', '病呀', '痛呀', '白呀', '穿呀', '穿啦', '累呀', '苦呀', '说啦', '贵呀', '跳呀', '过呀', '过啦', '远呀', '醒啦', '问啦', '闹呀', '飞呀', '饿呀']
FORCED = [('buwan', '补完', '補完', 400), ('bufa', '补发', '補發', 12), ('tuidiao', '推掉', '推掉', 279)]
# (pinyin, word, other): word above other on the key
ABOVE = [("diaozhen", "掉帧", "钓针")]
BELOW = [("zhenshu", "帧数", "真书"), ("zhuzhen", "逐帧", "助阵"), ("buzhen", "补帧", "不振"),
         ("yizhen", "一帧", "一阵"), ("buhui", "补回", "不会"), ("jidiao", "挤掉", "基调"),
         ("tuidiao", "推掉", "退掉"), ("bufa", "补发", "步伐"), ("buman", "补满", "布满"),
         ("zhentou", "帧头", "针头")]
ROWS = tuple(row[:4] for header in HEADERS.values() for row in block(header))


class DailyZhenFrameTests(unittest.TestCase):
    def test_blocks(self):
        for group, header in HEADERS.items():
            rows = block(header)
            self.assertEqual(SIZES[group], len(rows), group)
            self.assertEqual({"exact_rank_no_contains"}, {row[4] for row in rows}, group)
        self.assertEqual(len(ROWS), len({(row[0], row[1]) for row in ROWS}))
        texts = {row[1] for row in ROWS}
        for word in REQUESTED + PUT_BACK:
            self.assertIn(word, texts, word)
        self.assertIn(("guanjianzhen", "关键帧", "關鍵幀"), {row[:3] for row in ROWS})
        self.assertIn(("danzhen", "单帧", "單幀"), {row[:3] for row in ROWS})
        forced = block(HEADER_FORCED)
        self.assertEqual(sorted(tuple(row) for row in FORCED), sorted(row[:4] for row in forced))
        self.assertEqual({"exact_rank"}, {row[4] for row in forced})

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
        for pinyin, word, _tc, weight in ROWS + tuple(FORCED):
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
            for row in FORCED:
                self.assertEqual(str(row[3]), rows[(row[0], row[index])][0])


if __name__ == "__main__":
    unittest.main()
