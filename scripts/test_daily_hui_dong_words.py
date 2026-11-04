"""Words of 2026-11-04: a person or a pronoun with 动 or 懂 (你动, 人懂,
谁动, 没人懂), 会 with a verb or an adjective (会选, 会调, 会冷, 会倒) and 会 with
a short phrase of daily speech (会开车, 会回来). The user: "有空的时候，再帮我添加日常词：
你动、我动、他动、它动、她动、人动、人懂、会选、会挑、会挑、会调（tiao）、会回、会来、会写、会打、会吃、
会喝、会编、会发、会守、会踢、会玩、会完、会晚、会早、会认、会忍、会老、会变、会认、会摸、会看、会听、
会动、会懂、会喊、会冷、会热、会报、会包、会抱、会烫、会躺、会睡、会醒、会起、会倒、……；还是一样高低频
和权重，确保基准不降低" Weighted as test_daily_pi_fan_ka_words (occurrences where
the word is no part of a longer dictionary word, nor before one that its last
character begins, nor after one that its first character ends); a word stays
under every more frequent word of its key."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from test_daily_whitespace_phrases import read_rows
from test_daily_cuo_xiu_sha_shui_phrases import block

HEADERS = {'common': "# Everyday words, 2026-11-04, the more frequent ones: 你动, 我动, 他动, 它动, 她动, 人动, 人懂, 会选, 会挑, 会调 (read tiao), 会回, 会来, 会写, 会打, 会吃, 会喝, 会编, 会发, 会守, 会踢, 会玩, 会完, 会晚, 会早, 会认, 会忍, 会老, 会变, 会摸, 会看, 会听, 会动, 会懂, 会喊, 会冷, 会热, 会报, 会包, 会抱, 会烫, 会躺, 会睡, 会醒, 会起 and 会倒 (the user's examples; 会打, 会倒 and 会报 stay under the more frequent 回答, 回到 and 回报; 会选 and 会打, like 会赢 and 会给, at 200 and 会问 at 2, where higher weights turned benchmark cases of 回旋, 回稳, 回答 and 回应), a person or a pronoun with 动 or 懂 (能动, 也懂, 我不懂, 都不懂, 你懂的, 我懂了), 会 with a verb or an adjective (会说, 会让, 会给, 会等, 会疼, 会累, 会怕) and 会 with a short phrase (会开车, 会说话, 会后悔, 会更好, 会回来). Weighted as the blocks of 2026-11-03 (occurrences where the word is no part of a longer dictionary word, nor before one that its last character begins, nor after one that its first character ends); a word stays under every more frequent word of its key, an import's weight included; a requested word at least 400 where no more frequent word holds it lower.", 'less': '# Everyday words, 2026-11-04, the less frequent ones (谁懂, 也动, 想动, 你懂吗, 别乱动, 会饿, 会丢, 会坏, 会摔, 会疯, 会晕, 会痒, 会吵, 会画画, 会骑车, 会吃亏, 会过期), by the same weights; at weight 2 the words the general text holds fewer than 50 times (你动了, 没人动, 会删, 会骗, 会馋, 会想你) and 会收 and 会穿, whose presence turned benchmark cases (会穿 at 0 under 汇川).'}
SIZES = {'common': 123, 'less': 132}
REQUESTED = ['你动', '我动', '他动', '它动', '她动', '人动', '人懂', '会选', '会挑', '会调', '会回', '会来', '会写', '会打', '会吃', '会喝', '会编', '会发', '会守', '会踢', '会玩', '会完', '会晚', '会早', '会认', '会忍', '会老', '会变', '会摸', '会看', '会听', '会动', '会懂', '会喊', '会冷', '会热', '会报', '会包', '会抱', '会烫', '会躺', '会睡', '会醒', '会起', '会倒']
HEADER_FORCED = "# Weighted anew on 2026-11-04: import-weight words that held a word of the batch under them on its key (灰心, 回乡, 会东, 会心, 会商, 会集, 汇流, 回填, 回校, 挥刀, 挥拍, 辉石, 挥师, 灰褐, 灰土, 会昌, 会首, 回班) and import-weight words of the batch's kinds (不许动, 会来事), weighted as the blocks above."
FORCED = [('buxudong', '不许动', '不許動', 200), ('huilaishi', '会来事', '會來事', 200), ('huixiang', '回乡', '回鄉', 600), ('huishou', '会首', '會首', 200), ('huidong', '会东', '會東', 200), ('huiliu', '汇流', '匯流', 600), ('huipai', '挥拍', '揮拍', 279), ('huiji', '会集', '會集', 400), ('huishi', '辉石', '輝石', 94), ('huihe', '灰褐', '灰褐', 40), ('huixin', '灰心', '灰心', 601), ('huitu', '灰土', '灰土', 400), ('huishi', '挥师', '揮師', 93), ('huidao', '挥刀', '揮刀', 400), ('huiban', '回班', '回班', 200), ('huixiao', '回校', '回校', 600), ('huitian', '回填', '回填', 600), ('huichang', '会昌', '會昌', 566), ('huixin', '会心', '會心', 600), ('huishang', '会商', '會商', 279)]
ROWS = tuple(row[:4] for header in HEADERS.values() for row in block(header))


class DailyHuiDongWordsTests(unittest.TestCase):
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
            self.assertIn(len(sc), (2, 3, 4), sc)
            self.assertEqual(len(sc), len(tc), sc)
            self.assertNotIn("'", pinyin)
        # 会调 reads tiao as the user asked (会调整), 会还 huan, 会倒 dao.
        keys = {(row[0], row[1]) for row in ROWS}
        for pinyin, word in (("huitiao", "会调"), ("huitiao", "会挑"), ("huidao", "会倒"), ("nidong", "你动"),
                             ("tadong", "她动"), ("rendong", "人懂"), ("huidong", "会懂")):
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
