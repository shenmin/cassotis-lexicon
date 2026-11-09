"""Words of 2026-11-07: 这, 那 and 哪 before a measure word (这封, 那封), 封 after a numeral
or a demonstrative (两封, 这几封) and the phrases such a measure word makes with its noun (这封信, 这本书).
The user: "帮我再添加一批：这封、那封、……". Weighted as test_daily_hui_dong_words
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

HEADERS = {'common': "# Everyday words, 2026-11-07, the more frequent ones: 这封 and 那封 (the user's examples), 这, 那 and 哪 before a measure word or a word of time (这颗, 那枚, 哪条, 这趟), the phrases such a measure word makes with its noun (这封信, 一封信, 这本书, 那件事, 这段时间), weighted by the general text as the batches before, and the words such a word would take off its page or put below itself (这可, 那可, 这一章).", 'less': '# Everyday words, 2026-11-07, the less frequent ones (那摞, 这撮, 哪顶, 八封), by the same weights.'}
SIZES = {'common': 234, 'less': 388}
REQUESTED = ['这封', '那封']
HEADER_FORCED = "# Weighted anew on 2026-11-07: import-weight words of the family, which the general text holds far more often than their weights say (这间, 这所, 这股, 这帮, 这根, 这棵, 这门, 这招, 那辆, 那本, 那所, 那副, 那套, 哪次); and on daojia 到家 1000 above 道家 1, by the user's judgement (到家 had stood at 1 under 道家 1000)."
FORCED = [('zhejian', '这间', '這間', 279), ('zhesuo', '这所', '這所', 600), ('zhegu', '这股', '這股', 314), ('zhebang', '这帮', '這幫', 600), ('zhegen', '这根', '這根', 600), ('zheke', '这棵', '這棵', 600), ('zhemen', '这门', '這門', 600), ('zhezhao', '这招', '這招', 600), ('naliang', '那辆', '那輛', 600), ('naben', '那本', '那本', 600), ('nasuo', '那所', '那所', 400), ('nafu', '那副', '那副', 600), ('natao', '那套', '那套', 600), ('naci', '哪次', '哪次', 200), ('neiben', '那本', '那本', 600), ('daojia', '到家', '到家', 1000), ('daojia', '道家', '道家', 1)]
ROWS = tuple(row[:4] for header in HEADERS.values() for row in block(header))


class DailyZhefengWordsTests(unittest.TestCase):
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
        for pinyin, word in (("zhefeng", "这封"), ("nafeng", "那封")):
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
