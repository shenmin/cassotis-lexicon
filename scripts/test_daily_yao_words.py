"""Words of 2026-11-04: 要 with a verb, a noun or an adjective (要装, 要煲, 要房,
要黑, 要买, 要钱) and 要 with a short phrase of daily speech (要回家, 要小心,
要走了). The user: "再添加一下：要装、要抱、要弄、要保、要煲、要报、要包、要房、要车、要找、要招、要带、
要戴、要等、要搞、要告、要舔、要唱、要喊、要黑、……" (要舔 was in the dictionary.) Weighted
as test_daily_hui_dong_words
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

HEADERS = {'common': "# Everyday words, 2026-11-04, the more frequent ones: 要装, 要抱, 要弄, 要保, 要煲, 要报, 要包, 要房, 要车, 要找, 要招, 要带, 要戴, 要等, 要搞, 要告, 要唱, 要喊 and 要黑 (the user's examples, with 要舔, which the dictionary had; 要带 and 要戴, 要搞 and 要告, 要唱 and 要房 stay under the more frequent 腰带, 药膏, 药厂, 药房 and 药方; 要车 at 200, where 400 turned a long Tab case), 要 with a verb, a noun or an adjective (要买, 要给, 要靠, 要换, 要快) and 要 with a short phrase (要回家, 要上班, 要小心, 要好好, 要走了). Weighted as the blocks of 2026-11-04 (occurrences where the word is no part of a longer dictionary word, nor before one that its last character begins, nor after one that its first character ends); a word stays under every more frequent word of its key, an import's weight included; a requested word at least 400 where no more frequent word holds it lower. At 2: 要取, whose weight turned a long case, and 要学, 要杀, 要拍, 要涂, which went first without a context over the more frequent 药学, 要啥, 要派 and 要图.", 'less': '# Everyday words, 2026-11-04, the less frequent ones (要擦, 要拆, 要疯, 要哄, 要扔, 要下班, 要过年, 要哭了, 要饿死), by the same weights; at weight 2 要怕 and 要脱, which went first without a context over the more frequent 要趴 and 要拖, and the words the general text holds fewer than 50 times (要催, 要宠, 要饿, 要困, 要晕, 要慌, 要哪个).'}
SIZES = {'common': 142, 'less': 91}
REQUESTED = ['要装', '要抱', '要弄', '要保', '要煲', '要报', '要包', '要房', '要车', '要找', '要招', '要带', '要戴', '要等', '要搞', '要告', '要唱', '要喊', '要黑']
HEADER_FORCED = '# Weighted anew on 2026-11-04: import-weight words that held a word of the batch under them on its key (咬人, 窈窕, 腰腹, 妖气, 舀起, 腰际; 耀斑 and 腰板 at 202 and 201, just above 要搬: higher weights turned the long case 当下有正事要办) and 要用 and 要饭 of earlier blocks, weighted as the blocks above.'
FORCED = [('yaoyong', '要用', '要用', 414), ('yaofan', '要饭', '要飯', 271), ('yaofu', '腰腹', '腰腹', 600), ('yaoban', '腰板', '腰板', 201), ('yaoban', '耀斑', '耀斑', 202), ('yaotiao', '窈窕', '窈窕', 600), ('yaoqi', '妖气', '妖氣', 400), ('yaoqi', '舀起', '舀起', 201), ('yaoji', '腰际', '腰際', 202), ('yaoren', '咬人', '咬人', 600)]
ROWS = tuple(row[:4] for header in HEADERS.values() for row in block(header))


class DailyYaoWordsTests(unittest.TestCase):
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
        # 要还 reads huan (returning), 要弹 tan (弹琴), 要教 jiao.
        keys = {(row[0], row[1]) for row in ROWS}
        for pinyin, word in (("yaohuan", "要还"), ("yaotan", "要弹"), ("yaojiao", "要教"), ("yaobao", "要煲"),
                             ("yaonong", "要弄"), ("yaozhao", "要招"), ("yaohei", "要黑")):
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
