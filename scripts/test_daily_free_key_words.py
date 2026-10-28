"""Words of 2026-10-27 on keys of two syllables that had no word at all.
"laodu" showed 劳顿 first (du read as the dun still being typed) and nothing
that reads lao du; the user wanted real words on such keys, not phrases the
engine puts together. The words are those of jieba's dict.txt, CC-CEDICT and
THUOCL the dictionary lacked on such a key and the general text holds 1,000
times or more, reviewed by hand (names and pieces of phrases left out), and
老杜 beside 牢度; 鲁莽, an import's row only the traditional dictionary had
kept, weighted anew. Weighted as test_daily_suo_bijiao_phrases (occurrences where
the word is no part of a longer dictionary word, nor before one that its last
character begins, nor after one that its first character ends)."""
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from test_daily_whitespace_phrases import read_rows
from test_daily_cuo_xiu_sha_shui_phrases import block, keys

HEADERS = {'common': '# Words on keys of two syllables that had no word, 2026-10-27, the more frequent ones: "laodu" read only as 劳顿, a word still being typed, and the user asked for real words of such keys (牢度, 老杜); the words of jieba\'s dict.txt, CC-CEDICT and THUOCL that the general text holds 1,000 times or more, reviewed by hand (马虎, 廉政, 党建, 爱戴, 好戏, 佛系; names and pieces of phrases left out). Weighted as the blocks of 2026-10-20 (occurrences where the word is no part of a longer dictionary word, nor before one that its last character begins, nor after one that its first character ends).', 'less': '# Words on keys of two syllables that had no word, 2026-10-27, the less frequent ones, by the same weights (热塑, 案外, 叠被, 求成).'}
SIZES = {'common': 1151, 'less': 4}
REQUESTED = ['牢度', '老杜']
HEADER_FORCED = "# Words at an import's weight, 2026-10-27, weighted by the same rules: 鲁莽 (the simplified dictionary had not kept the import's row)."
FORCED = [('lumang', '鲁莽', '魯莽', 600)]
ROWS = tuple(row[:4] for header in HEADERS.values() for row in block(header))


class DailyFreeKeyWordsTests(unittest.TestCase):
    def test_blocks(self):
        for group, header in HEADERS.items():
            rows = block(header)
            self.assertEqual(SIZES[group], len(rows), group)
            self.assertEqual({"exact_rank_no_contains"}, {row[4] for row in rows}, group)
        self.assertEqual(len(ROWS), len({(row[0], row[1]) for row in ROWS}))
        texts = {row[1] for row in ROWS}
        for word in REQUESTED:
            self.assertIn(word, texts, word)
        self.assertIn(("laodu", "牢度", "牢度"), {row[:3] for row in ROWS})
        self.assertIn(("laodu", "老杜", "老杜"), {row[:3] for row in ROWS})
        forced = block(HEADER_FORCED)
        self.assertEqual(sorted(tuple(row) for row in FORCED), sorted(row[:4] for row in forced))
        self.assertEqual({"exact_rank"}, {row[4] for row in forced})

    def test_keys_had_no_word(self):
        # The batch's keys held no word but the batch's own; a later daily
        # block may add words of its own there (只隔 beside 制革 at zhige,
        # 2026-10-28).
        later = set()
        newest = ""
        for line in (ROOT / "manifests/curated_daily_supplement_phrases.tsv").read_text(encoding="utf-8").splitlines():
            if line.startswith("#"):
                newest = max(re.findall(r"20\d\d-\d\d-\d\d", line), default="")
                continue
            fields = line.split("	")
            if newest > "2026-10-27" and len(fields) >= 4:
                later.update({(fields[3], fields[0]), (fields[3], fields[1])})
        for variant, index in (("sc", 1), ("tc", 2)):
            ours = {(row[0], row[index]) for row in ROWS + tuple(FORCED)}
            batch_keys = {row[0] for row in ROWS + tuple(FORCED)}
            for (pinyin, text) in read_rows(f"dict_clean_{variant}.txt"):
                if pinyin.replace("'", "") in batch_keys and (pinyin, text) not in later:
                    self.assertIn((pinyin, text), ours, (variant, pinyin, text))

    def test_order(self):
        rows = keys("sc")
        self.assertGreater(rows["laodu"]["牢度"], rows["laodu"]["老杜"])
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
