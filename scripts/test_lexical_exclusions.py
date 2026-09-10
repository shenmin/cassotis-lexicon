#!/usr/bin/env python3
"""Keep explicitly removed terms out of imports and snapshot restoration."""

from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_external_cedict as builder

AUDITED_JAPANESE_TERMS = (
    "\u751f\u5730\u4ed5\u4e0a", "\u6539\u672d\u53e3", "\u7384\u95a2",
    "\u4fe1\u53f7\u767a\u751f\u5668", "\u4fe1\u865f\u767a\u751f\u5668",
    "\u6807\u51c6\u4fe1\u53f7\u767a\u751f\u5668",
    "\u6a19\u6e96\u4fe1\u865f\u767a\u751f\u5668",
    "\u5e2f\u96fb\u5fae\u7c92\u5b50",
    "\u9069\u5fdc\u4fe1\u865f\u51e6\u7406",
    # The follow-up review covers both script variants, including SC leftovers.
    "\u4ea4\u901a\u611f\u5fdc\u4fe1\u53f7",
    "\u4ea4\u901a\u611f\u5fdc\u4fe1\u865f",
    "\u4fe1\u53f7\u51e6\u7406\u56de\u8def",
    "\u4fe1\u53f7\u5bfe\u96d1\u97f3\u6bd4",
    "\u4fe1\u53f7\u767a\u632f\u5668",
    "\u4fe1\u865f\u51e6\u7406\u8ff4\u8def",
    "\u4fe1\u865f\u5bfe\u96d1\u97f3\u6bd4",
    "\u4fe1\u865f\u767a\u632f\u5668",
    "\u51b2\u6483\u7c92\u5b50",
    "\u5358\u7dda\u5f0f\u4fe1\u865f\u6a5f",
    "\u5358\u7ebf\u5f0f\u4fe1\u53f7\u673a",
    "\u540c\u671f\u4fe1\u53f7\u767a\u751f\u5668",
    "\u540c\u671f\u4fe1\u865f\u767a\u751f\u5668",
    "\u56de\u8ee2\u4fe1\u53f7\u673a",
    "\u56de\u8ee2\u4fe1\u865f\u6a5f",
    "\u5929\u4f53\u7269\u7406\u89b3\u6d4b\u6240",
    "\u5929\u9ad4\u7269\u7406\u89b3\u6e2c\u6240",
    "\u5e2f\u7535\u5fae\u7c92\u5b50",
    "\u5fdc\u7528\u7269\u7406\u5b66",
    "\u5fdc\u7528\u7269\u7406\u5b78",
    "\u5fdc\u7b54\u4fe1\u53f7",
    "\u5fdc\u7b54\u4fe1\u865f",
    "\u60c5\u5831\u4f1d\u9054\u7c92\u5b50",
    "\u60c5\u62a5\u4f1d\u8fbe\u7c92\u5b50",
    "\u6c34\u7d20\u51b7\u5374\u767a\u7535\u673a",
    "\u6c34\u7d20\u51b7\u537b\u767a\u96fb\u6a5f",
    "\u7269\u7406\u691c\u5c42",
    "\u7269\u7406\u691c\u5c64",
    "\u7c92\u5b50\u7d4c\u8def",
    "\u885d\u6483\u7c92\u5b50",
    "\u8996\u899a\u4fe1\u865f",
    "\u89c6\u899a\u4fe1\u53f7",
    "\u8fc7\u654f\u75c7\u5c02\u79d1\u533b\u751f",
    "\u9002\u5fdc\u4fe1\u53f7\u51e6\u7406",
    "\u904e\u654f\u75c7\u5c02\u79d1\u91ab\u751f",
    "\u9244\u9053\u4fe1\u53f7",
    "\u9244\u9053\u4fe1\u865f",
)


class LexicalExclusionTests(unittest.TestCase):
    def test_audited_japanese_terms_cannot_return_from_imports_or_snapshots(self):
        old = {("query", text): 1000 for text in AUDITED_JAPANESE_TERMS}
        filtered, count = builder._drop_explicit_multi_char_terms(
            old, builder.MULTI_CHAR_TERM_DROP_OVERRIDES
        )
        self.assertEqual(len(old), count)
        self.assertFalse(filtered)
        restored, stats = builder._restore_missing_texts_from_snapshot(
            {}, old, builder.MULTI_CHAR_TERM_DROP_OVERRIDES, "test",
            wiki_augmented_terms=set(),
        )
        self.assertFalse(restored)
        self.assertEqual(len(old), stats["test_snapshot_rows_skipped_explicit_drop"])

    def test_standard_spellings_and_proper_names_are_not_excluded(self):
        entries = {("query", text): 461 for text in (
            "\u7384\u5173", "\u7384\u95dc",
            "\u4fe1\u53f7\u53d1\u751f\u5668",
            "\u4fe1\u865f\u767c\u751f\u5668",
            "\u9ad8\u7551\u52cb", "\u6e90\u6c0f\u7269\u8bed",
        )}
        filtered, count = builder._drop_explicit_multi_char_terms(
            entries, builder.MULTI_CHAR_TERM_DROP_OVERRIDES
        )
        self.assertEqual(0, count)
        self.assertEqual(entries, filtered)

    def test_published_base_and_completion_data_exclude_audited_terms(self):
        root = Path(__file__).resolve().parents[1] / "data/generated"
        forbidden = set(AUDITED_JAPANESE_TERMS)
        for variant in ("sc", "tc"):
            for stem, column in (("dict_clean", 1), ("dict_completion_prior", 1),
                                 ("dict_completion_lookup", 2)):
                path = root / f"{stem}_{variant}.txt"
                with path.open(encoding="utf-8") as stream:
                    for number, line in enumerate(stream, 1):
                        parts = line.rstrip("\r\n").split("\t")
                        if len(parts) > column and (
                            parts[column] in forbidden
                            or "\u68c0\u67fb" in parts[column]
                            or "\u6aa2\u67fb" in parts[column]
                        ):
                            self.fail(f"Removed term in {path.name}:{number}")

    def test_inspection_variants_are_blocked_by_text_not_pronunciation(self):
        bad = {
            ("jiankangjianzha", "\u5065\u5eb7\u68c0\u67fb"): 750,
            ("jiankangjiancha", "\u5065\u5eb7\u68c0\u67fb"): 750,
            ("shentijianzha", "\u8eab\u9ad4\u6aa2\u67fb"): 570,
        }
        good = {
            ("jiankangjiancha", "\u5065\u5eb7\u68c0\u67e5"): 570,
            ("shentijiancha", "\u8eab\u9ad4\u6aa2\u67e5"): 570,
            ("zha", "\u67fb"): 100,
            ("cha", "\u67e5"): 1000,
            ("zha", "\u67e5"): 800,
            ("chali", "\u67e5\u7406"): 100,
        }
        filtered, count = builder._drop_explicit_multi_char_terms(
            {**good, **bad}, builder.MULTI_CHAR_TERM_DROP_OVERRIDES
        )
        self.assertEqual(len(bad), count)
        self.assertEqual(good, filtered)
        restored, stats = builder._restore_missing_texts_from_snapshot(
            good, bad, builder.MULTI_CHAR_TERM_DROP_OVERRIDES, "test",
            wiki_augmented_terms=set(),
        )
        self.assertEqual(good, restored)
        self.assertEqual(len(bad), stats["test_snapshot_rows_skipped_explicit_drop"])

    def test_standard_traditional_xuanguan_keeps_simplified_weight(self):
        payload = "\u7384\u5173\t\u7384\u95dc\t0.461\txuanguan\texact_rank\n".encode("utf-8")
        entries, _ = builder._parse_curated_daily_phrase_entries(payload, 2)
        regular, exact = builder._partition_curated_daily_post_rank_exact_entries(entries)
        self.assertFalse(regular)
        sc, tc = {("xuanguan", "\u7384\u5173"): 461}, {}
        builder._inject_curated_daily_post_rank_exact_entries(sc, tc, exact)
        self.assertEqual({("xuanguan", "\u7384\u5173"): 461}, sc)
        self.assertEqual({("xuanguan", "\u7384\u95dc"): 461}, tc)

    def test_writer_rejects_late_injection_even_with_preserved_pinyin(self):
        entries = {
            ("daidianweilizi", "\u5e2f\u7535\u5fae\u7c92\u5b50"): 750,
            ("shiyingxinhaochuli", "\u9002\u5fdc\u4fe1\u53f7\u51e6\u7406"): 801,
            ("jiankangjianzha", "\u5065\u5eb7\u68c0\u67fb"): 750,
            ("shentijianzha", "\u8eab\u9ad4\u6aa2\u67fb"): 570,
            ("jiankangjiancha", "\u5065\u5eb7\u68c0\u67e5"): 570,
            ("yingyongwulixue", "\u5e94\u7528\u7269\u7406\u5b66"): 738,
            ("zha", "\u67fb"): 100,
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dictionary.txt"
            path.write_text("jiankangjianzha\t\u5065\u5eb7\u68c0\u67fb\t750\n", encoding="utf-8")
            builder._write_dict(
                path, entries, preserve_pinyin_keys=set(entries),
                preferred_terms={text for _, text in entries},
            )
            self.assertEqual({
                "jiankangjiancha\t\u5065\u5eb7\u68c0\u67e5\t570",
                "yingyongwulixue\t\u5e94\u7528\u7269\u7406\u5b66\t738",
                "zha\t\u67fb\t100",
            }, set(path.read_text(encoding="utf-8").splitlines()))

    def test_removed_shishizhe_terms_are_filtered_by_text(self):
        entries = {
            ("shishizhe", "\u4ed5\u4e8b\u7740"): 1000,
            ("shigotogi", "\u4ed5\u4e8b\u7740"): 1000,
            ("shishizhe", "\u65bd\u4e8b\u8005"): 379,
            ("shishizhe", "\u5b9e\u65bd\u8005"): 460,
            ("shishizhe", "\u5be6\u65bd\u8005"): 460,
            ("shi", "\u4ed5"): 300,
        }
        filtered, removed = builder._drop_explicit_multi_char_terms(
            entries, builder.MULTI_CHAR_TERM_DROP_OVERRIDES
        )
        self.assertEqual(3, removed)
        self.assertEqual(
            {key: value for key, value in entries.items() if key[1] not in
             ("\u4ed5\u4e8b\u7740", "\u65bd\u4e8b\u8005")},
            filtered,
        )

    def test_old_snapshot_cannot_restore_removed_terms(self):
        current = {("shishizhe", "\u5b9e\u65bd\u8005"): 460}
        old = {
            ("shishizhe", "\u4ed5\u4e8b\u7740"): 1000,
            ("shishizhe", "\u65bd\u4e8b\u8005"): 379,
        }
        restored, stats = builder._restore_missing_texts_from_snapshot(
            current, old, builder.MULTI_CHAR_TERM_DROP_OVERRIDES, "test",
            wiki_augmented_terms=set(),
        )
        self.assertEqual(current, restored)
        self.assertEqual(2, stats["test_snapshot_rows_skipped_explicit_drop"])

    def test_everyday_replacement_has_its_own_exact_weight(self):
        payload = (
            "\u5b9e\u65bd\u8005\t\u5be6\u65bd\u8005\t0.460\tshishizhe"
            "\texact_rank_no_contains\n"
        ).encode("utf-8")
        entries, _ = builder._parse_curated_daily_phrase_entries(payload, 2)
        regular, exact = builder._partition_curated_daily_post_rank_exact_entries(entries)
        self.assertFalse(regular)
        sc, tc = {}, {}
        builder._inject_curated_daily_post_rank_exact_entries(sc, tc, exact)
        self.assertEqual({("shishizhe", "\u5b9e\u65bd\u8005"): 460}, sc)
        self.assertEqual({("shishizhe", "\u5be6\u65bd\u8005"): 460}, tc)


if __name__ == "__main__":
    unittest.main()
