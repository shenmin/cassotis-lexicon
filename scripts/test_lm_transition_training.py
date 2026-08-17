#!/usr/bin/env python3
"""Regression tests for corpus-trained exact pair transitions."""

from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest


SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import build_external_cedict as builder  # noqa: E402
import prepare_lm_transition_corpus as preparer  # noqa: E402


class LmTransitionTrainingTests(unittest.TestCase):
    def test_runtime_compact_parser_matches_completion_prefix_boundaries(self) -> None:
        self.assertEqual(["ti", "gao", "hen"], builder._runtime_parse_compact_pinyin("tigaohen"))
        self.assertEqual(["bian"], builder._runtime_parse_compact_pinyin("bian"))

    def test_transition_completion_rejects_runtime_boundary_ambiguity(self) -> None:
        mapping = {
            ("bi'an", "\u5f7c\u5cb8"): 500,
            ("hua", "\u82b1"): 600,
        }
        evidence = {
            ("bianhua", "\u5f7c\u5cb8|\u82b1"): (
                30, 8, 26, 7, 0, 1, 1.0, 2.0, 500
            ),
        }
        readings = {
            "\u5f7c": {"bi"},
            "\u5cb8": {"an"},
            "\u82b1": {"hua"},
        }
        completions, stats = builder._build_transition_completion_index(
            mapping,
            evidence,
            unihan_map={text: next(iter(values)) for text, values in readings.items()},
            unihan_readings_map=readings,
            unihan_source_rank_map={},
            unihan_pinlu_detail_map={},
            stats_prefix="test",
        )
        self.assertEqual({}, completions)
        self.assertEqual(
            1,
            stats[
                "test_transition_completion_skipped_runtime_prefix_boundary"
            ],
        )

    def test_transition_completion_index_is_strict_and_prefix_unambiguous(self) -> None:
        mapping = {
            ("tigao", "\u63d0\u9ad8"): 720,
            ("henduo", "\u5f88\u591a"): 680,
            ("zhiliang", "\u8d28\u91cf"): 690,
        }
        evidence = {
            ("tigaohenduo", "\u63d0\u9ad8|\u5f88\u591a"): (
                30, 8, 26, 7, 0, 1, 1.0, 0.8, 460
            ),
            ("tigaozhiliang", "\u63d0\u9ad8|\u8d28\u91cf"): (
                29, 8, 25, 7, 0, 1, 1.0, 2.1, 460
            ),
        }
        readings = {
            "\u63d0": {"ti"},
            "\u9ad8": {"gao"},
            "\u5f88": {"hen"},
            "\u591a": {"duo"},
            "\u8d28": {"zhi"},
            "\u91cf": {"liang"},
        }
        defaults = {text: next(iter(values)) for text, values in readings.items()}

        completions, stats = builder._build_transition_completion_index(
            mapping,
            evidence,
            unihan_map=defaults,
            unihan_readings_map=readings,
            unihan_source_rank_map={},
            unihan_pinlu_detail_map={},
            stats_prefix="test",
        )

        self.assertFalse(
            any(key[0] == "tigao" for key in completions),
            "equally strong completions must suppress the ambiguous prefix",
        )
        self.assertIn(
            (
                "tigaohen",
                "ti'gao'hen'duo",
                "\u63d0\u9ad8\u5f88\u591a",
                "\u63d0\u9ad8|\u5f88\u591a",
            ),
            completions,
        )
        self.assertGreater(
            stats["test_transition_completion_skipped_ambiguous_prefix"], 0
        )

    def test_transition_completion_excludes_exact_and_weak_paths(self) -> None:
        mapping = {
            ("tigao", "\u63d0\u9ad8"): 720,
            ("henduo", "\u5f88\u591a"): 680,
            ("tigaohenduo", "\u63d0\u9ad8\u5f88\u591a"): 500,
            ("xiaolv", "\u6548\u7387"): 690,
        }
        evidence = {
            ("tigaohenduo", "\u63d0\u9ad8|\u5f88\u591a"): (
                30, 8, 26, 7, 0, 1, 1.0, 2.2, 460
            ),
            ("tigaoxiaolv", "\u63d0\u9ad8|\u6548\u7387"): (
                30, 1, 26, 1, 0, 1, 1.0, 2.2, 460
            ),
        }
        readings = {
            "\u63d0": {"ti"},
            "\u9ad8": {"gao"},
            "\u5f88": {"hen"},
            "\u591a": {"duo"},
            "\u6548": {"xiao"},
            "\u7387": {"lv"},
        }
        defaults = {text: next(iter(values)) for text, values in readings.items()}

        completions, stats = builder._build_transition_completion_index(
            mapping,
            evidence,
            unihan_map=defaults,
            unihan_readings_map=readings,
            unihan_source_rank_map={},
            unihan_pinlu_detail_map={},
            stats_prefix="test",
        )

        self.assertEqual({}, completions)
        self.assertEqual(
            1, stats["test_transition_completion_skipped_full_exact"]
        )
        self.assertEqual(
            1, stats["test_transition_completion_skipped_weak_evidence"]
        )

    def test_transition_completion_requires_five_independent_sources(self) -> None:
        mapping = {
            ("tigao", "\u63d0\u9ad8"): 720,
            ("henduo", "\u5f88\u591a"): 680,
        }
        readings = {
            "\u63d0": {"ti"},
            "\u9ad8": {"gao"},
            "\u5f88": {"hen"},
            "\u591a": {"duo"},
        }
        defaults = {text: next(iter(values)) for text, values in readings.items()}

        def build(source_count: int):
            evidence = {
                ("tigaohenduo", "\u63d0\u9ad8|\u5f88\u591a"): (
                    22,
                    source_count,
                    22,
                    source_count,
                    0,
                    1,
                    1.0,
                    -0.5,
                    443,
                ),
            }
            return builder._build_transition_completion_index(
                mapping,
                evidence,
                unihan_map=defaults,
                unihan_readings_map=readings,
                unihan_source_rank_map={},
                unihan_pinlu_detail_map={},
                stats_prefix="test",
            )[0]

        completions = build(5)
        self.assertIn(
            (
                "tigaohen",
                "ti'gao'hen'duo",
                "\u63d0\u9ad8\u5f88\u591a",
                "\u63d0\u9ad8|\u5f88\u591a",
            ),
            completions,
        )
        self.assertEqual({}, build(4))

    def test_transition_completion_is_revalidated_against_final_dictionary(
        self,
    ) -> None:
        rows = {
            ("tigaohen", "tigaohenduo", "\u63d0\u9ad8\u5f88\u591a", "\u63d0\u9ad8|\u5f88\u591a"): 570,
            ("aichi", "aichide", "\u7231\u5403\u7684", "\u7231|\u5403\u7684"): 580,
            ("youxiang", "youxiangdizhi", "\u90ae\u7bb1\u5730\u5740", "\u90ae\u7bb1|\u5730\u5740"): 600,
            ("cifudian", "cifudianji", "\u4f3a\u670d\u7535\u673a", "\u4f3a\u670d|\u7535\u673a"): 590,
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            dictionary_path = pathlib.Path(temp_dir) / "dict.txt"
            dictionary_path.write_text(
                "tigao\t\u63d0\u9ad8\t720\n"
                "henduo\t\u5f88\u591a\t680\n"
                "youxiang\t\u90ae\u7bb1\t600\n"
                "dizhi\t\u5730\u5740\t700\n"
                "youxiangdizhi\t\u90ae\u7bb1\u5730\u5740\t500\n"
                "sifu\t\u4f3a\u670d\t500\n"
                "dianji\t\u7535\u673a\t700\n"
                "chide\t\u5403\u7684\t700\n",
                encoding="utf-8",
            )
            filtered, stats = (
                builder._filter_transition_completion_against_written_dictionary(
                    rows,
                    dictionary_path,
                    single_char_readings_map={"\u7231": {"ai"}},
                    stats_prefix="test",
                )
            )

        self.assertEqual(
            {
                (
                    "tigaohen",
                    "tigaohenduo",
                    "\u63d0\u9ad8\u5f88\u591a",
                    "\u63d0\u9ad8|\u5f88\u591a",
                ): 570,
                (
                    "aichi",
                    "aichide",
                    "\u7231\u5403\u7684",
                    "\u7231|\u5403\u7684",
                ): 580,
            },
            filtered,
        )
        self.assertEqual(
            1, stats["test_transition_completion_final_dropped_full_exact"]
        )
        self.assertEqual(
            1,
            stats[
                "test_transition_completion_final_dropped_component_reading"
            ],
        )

    def test_audited_low_priority_medical_procedure_is_capped(self) -> None:
        mapping = {
            ("duotai", "堕胎"): 539,
            ("duotai", "多态"): 347,
            ("jibing", "疾病"): 660,
        }

        stats = builder._cap_medical_specific_term_weights(
            mapping,
            {"堕胎": 0.30, "疾病": 0.60},
            {"堕胎": 2, "疾病": 3},
            {},
            {"堕胎": 0.50},
            set(),
            "test",
        )

        self.assertEqual(80, mapping[("duotai", "堕胎")])
        self.assertEqual(347, mapping[("duotai", "多态")])
        self.assertEqual(660, mapping[("jibing", "疾病")])
        self.assertEqual(1, stats["test_low_priority_medical_procedure_capped"])

    def test_curated_exact_rank_mode_injects_fixed_weight(self) -> None:
        entries, stats = builder._parse_curated_daily_phrase_entries(
            "多台\t多台\t0.347\tduotai\texact_rank\n".encode("utf-8"),
            2,
            stats_prefix="test_curated",
        )
        regular, post_rank = builder._partition_curated_daily_post_rank_exact_entries(
            entries
        )
        sc_map = {("duotai", "多台"): 0, ("duotai", "多态"): 347}
        tc_map = {("duotai", "多台"): 0, ("duotai", "多態"): 310}

        self.assertEqual([], regular)
        self.assertEqual(1, len(post_rank))
        self.assertEqual(1, stats["test_curated_exact_rank"])
        inject_stats = builder._inject_curated_daily_post_rank_exact_entries(
            sc_map,
            tc_map,
            post_rank,
        )
        self.assertEqual(347, sc_map[("duotai", "多台")])
        self.assertEqual(347, tc_map[("duotai", "多台")])
        self.assertEqual(
            1, inject_stats["curated_daily_post_rank_exact_sc_forced_rank"]
        )
        self.assertEqual(
            1, inject_stats["curated_daily_post_rank_exact_tc_forced_rank"]
        )

    def test_curated_exact_zero_mode_injects_true_zero_weight(self) -> None:
        entries, stats = builder._parse_curated_daily_phrase_entries(
            "多台\t多台\t0.00\tduotai\texact_zero\n".encode("utf-8"),
            2,
            stats_prefix="test_curated",
        )
        regular, post_rank = builder._partition_curated_daily_post_rank_exact_entries(
            entries
        )
        sc_map = {("duotai", "多态"): 347}
        tc_map = {("duotai", "多態"): 347}

        self.assertEqual([], regular)
        self.assertEqual(1, len(post_rank))
        self.assertEqual(1, stats["test_curated_exact_zero"])
        builder._inject_curated_daily_post_rank_exact_entries(
            sc_map,
            tc_map,
            post_rank,
        )
        self.assertEqual(0, sc_map[("duotai", "多台")])
        self.assertEqual(0, tc_map[("duotai", "多台")])

    def test_unihan_phrase_updates_preserve_existing_single_char_weights(self) -> None:
        existing_char = "\u82f1"
        new_char = "\u65b0"
        removed_char = "\u65e7"
        phrase = "\u5168\u82f1\u6587"
        mapping = {
            ("ying", existing_char): 459,
            ("xin", new_char): 320,
            ("quanyingwen", phrase): 800,
        }
        previous = {
            ("ying", existing_char): 579,
            ("jiu", removed_char): 401,
            ("quanyingwen", phrase): 700,
        }

        stats = builder._preserve_existing_unihan_single_char_weights(
            mapping,
            previous,
            "test",
        )

        self.assertEqual(579, mapping[("ying", existing_char)])
        self.assertEqual(320, mapping[("xin", new_char)])
        self.assertNotIn(("jiu", removed_char), mapping)
        self.assertEqual(800, mapping[("quanyingwen", phrase)])
        self.assertEqual(1, stats["test_existing_single_char_rows_considered"])
        self.assertEqual(1, stats["test_existing_single_char_weights_preserved"])

    def test_post_rank_zero_marker_overrides_existing_weight(self) -> None:
        zero_text = "\u4f46\u4e5f"
        natural_text = "\u81ea\u7136"
        visible_text = "\u53ef\u89c1"
        sc_map = {
            ("danye", zero_text): 280,
            ("ziran", natural_text): 400,
        }
        tc_map = dict(sc_map)

        stats = builder._inject_curated_daily_post_rank_exact_entries(
            sc_map,
            tc_map,
            [
                (zero_text, zero_text, -2.0, "danye"),
                (natural_text, natural_text, -1.99, "ziran"),
                (visible_text, visible_text, -1.99, "kejian"),
            ],
        )

        self.assertEqual(0, sc_map[("danye", zero_text)])
        self.assertEqual(0, tc_map[("danye", zero_text)])
        self.assertEqual(400, sc_map[("ziran", natural_text)])
        self.assertEqual(400, tc_map[("ziran", natural_text)])
        self.assertEqual(1, sc_map[("kejian", visible_text)])
        self.assertEqual(1, tc_map[("kejian", visible_text)])
        self.assertEqual(
            1, stats["curated_daily_post_rank_exact_sc_forced_zero"]
        )
        self.assertEqual(
            1, stats["curated_daily_post_rank_exact_tc_forced_zero"]
        )

    @staticmethod
    def _ensure_test_single_entries(
        entries: dict[str, list[tuple[str, str, int, int, int]]],
        rows: list[tuple[str, str]],
    ) -> None:
        for sentence, _source_name in rows:
            for char in sentence:
                if char in entries:
                    continue
                entries[char] = [
                    (f"ctx{ord(char):x}", char, 700, 1, 700)
                ]

    def test_general_lm_keeps_near_best_segmentation_boundaries(self) -> None:
        def entry(
            pinyin: str, text: str
        ) -> tuple[str, str, int, int, int]:
            return pinyin, text, 800, 1, 800

        sentence = "甲乙丙丁戊"
        entries = {
            "甲乙": [entry("jiayi", "甲乙")],
            "丙丁戊": [entry("bingdingwu", "丙丁戊")],
            "甲乙丙": [entry("jiayibing", "甲乙丙")],
            "丁戊": [entry("dingwu", "丁戊")],
        }

        segmentations = builder._segment_lm_sentence_nbest(
            sentence,
            entries,
            max_segment_units=4,
        )
        paths = {
            tuple(item[1] for item in segments)
            for segments, _confidence in segmentations
        }
        self.assertIn(("甲乙", "丙丁戊"), paths)
        self.assertIn(("甲乙丙", "丁戊"), paths)

        rows = [(sentence, f"source-{index}") for index in range(12)]
        priors, stats = builder._collect_lm_transition_priors(
            rows,
            entries,
            max_segment_units=4,
        )
        separator = builder.QUERY_PATH_FILE_SEPARATOR
        self.assertIn(
            ("jiayibingdingwu", f"甲乙{separator}丙丁戊"),
            priors,
            str(stats),
        )
        self.assertIn(
            ("jiayibingdingwu", f"甲乙丙{separator}丁戊"),
            priors,
            str(stats),
        )
        self.assertEqual(24, stats["lm_corpus_segmentations"])

    def test_strong_single_pairs_require_sparse_independent_dominant_evidence(
        self,
    ) -> None:
        def entry(
            pinyin: str,
            text: str,
            weight: int,
            rank: int = 1,
            top_weight: int | None = None,
        ) -> tuple[str, str, int, int, int]:
            return pinyin, text, weight, rank, top_weight or weight

        entries = {
            "\u4f60": [entry("ni", "\u4f60", 700)],
            "\u8bf4": [entry("shuo", "\u8bf4", 680)],
            "\u8fd8": [entry("hai", "\u8fd8", 660)],
            "\u6765": [entry("lai", "\u6765", 650)],
            "\u67d0": [entry("mou", "\u67d0", 180, 12, 700)],
            "\u4eba": [entry("ren", "\u4eba", 700)],
            "\u5206": [entry("fen", "\u5206", 700)],
            "\u4e86": [entry("le", "\u4e86", 700)],
            # Existing exact words must remain in the ordinary dictionary path.
            "\u4f60\u597d": [entry("nihao", "\u4f60\u597d", 1000)],
            "\u597d": [entry("hao", "\u597d", 700)],
        }
        rows: list[tuple[str, str]] = []
        left_contexts = "\u7532\u4e59\u4e19\u4e01\u620a\u5df1\u5e9a\u8f9b"
        right_contexts = "\u5b50\u4e11\u5bc5\u536f\u8fb0\u5df3\u5348\u672a"
        for index in range(20):
            rows.append(
                (
                    left_contexts[index % len(left_contexts)]
                    + "\u4f60\u8bf4"
                    + right_contexts[(index + 1) % len(right_contexts)],
                    f"say-{index % 6}",
                )
            )
        for index in range(12):
            rows.append(
                (
                    left_contexts[index % len(left_contexts)]
                    + "\u8fd8\u6765"
                    + right_contexts[(index + 2) % len(right_contexts)],
                    "one-source",
                )
            )
        for index in range(20):
            rows.append(
                (
                    left_contexts[index % len(left_contexts)]
                    + "\u4f60\u597d"
                    + right_contexts[index % len(right_contexts)],
                    f"exact-{index}",
                )
            )
        for index in range(20):
            rows.append(
                (
                    left_contexts[index % len(left_contexts)]
                    + "\u67d0\u4eba"
                    + right_contexts[index % len(right_contexts)],
                    f"rare-{index}",
                )
            )
        for index in range(20):
            rows.append(
                (
                    left_contexts[index % len(left_contexts)]
                    + "\u5206\u4e86"
                    + right_contexts[index % len(right_contexts)],
                    f"hidden-exact-{index}",
                )
            )
        self._ensure_test_single_entries(entries, rows)

        priors, stats = builder._collect_strong_single_pair_transition_priors(
            rows,
            entries,
            exact_texts={"\u5206\u4e86"},
        )
        separator = builder.QUERY_PATH_FILE_SEPARATOR
        self.assertIn(
            ("nishuo", f"\u4f60{separator}\u8bf4"),
            priors,
            str(stats),
        )
        self.assertNotIn(("hailai", f"\u8fd8{separator}\u6765"), priors)
        self.assertNotIn(("nihao", f"\u4f60{separator}\u597d"), priors)
        self.assertNotIn(("mouren", f"\u67d0{separator}\u4eba"), priors)
        self.assertNotIn(("fenle", f"\u5206{separator}\u4e86"), priors)
        self.assertEqual(1, stats["strong_single_pair_priors_emitted"])

    def test_strong_single_pairs_keep_one_path_per_query_without_clear_winner(
        self,
    ) -> None:
        def entry(pinyin: str, text: str) -> tuple[str, str, int, int, int]:
            return pinyin, text, 700, 1, 700

        entries = {
            "\u4f60": [entry("ni", "\u4f60")],
            "\u8bf4": [entry("shuo", "\u8bf4")],
            "\u502a": [entry("ni", "\u502a")],
            "\u6714": [entry("shuo", "\u6714")],
        }
        rows: list[tuple[str, str]] = []
        for index in range(20):
            rows.append(
                (
                    f"{chr(0x4e70 + (index % 8))}\u4f60\u8bf4{chr(0x4e10 + index)}",
                    f"a-{index}",
                )
            )
        for index in range(15):
            rows.append(
                (
                    f"{chr(0x4e90 + (index % 8))}\u502a\u6714{chr(0x4e30 + index)}",
                    f"b-{index}",
                )
            )
        self._ensure_test_single_entries(entries, rows)

        priors, stats = builder._collect_strong_single_pair_transition_priors(
            rows,
            entries,
        )
        self.assertLessEqual(
            sum(1 for query, _path in priors if query == "nishuo"),
            1,
        )
        self.assertGreater(stats["strong_single_pair_skipped_query_dominance"], 0)

    def test_strong_single_pairs_allow_only_an_exceptional_second_path(
        self,
    ) -> None:
        def entry(pinyin: str, text: str) -> tuple[str, str, int, int, int]:
            return pinyin, text, 700, 1, 700

        entries = {
            "\u4f60": [entry("ni", "\u4f60")],
            "\u8bf4": [entry("shuo", "\u8bf4")],
            "\u502a": [entry("ni", "\u502a")],
            "\u6714": [entry("shuo", "\u6714")],
        }
        rows: list[tuple[str, str]] = []
        for index in range(48):
            rows.append(
                (
                    f"{chr(0x4e10 + (index % 12))}\u4f60\u8bf4"
                    f"{chr(0x4e40 + (index % 12))}",
                    f"top-{index % 12}",
                )
            )
        for index in range(40):
            rows.append(
                (
                    f"{chr(0x4e70 + (index % 12))}\u502a\u6714"
                    f"{chr(0x4ea0 + (index % 12))}",
                    f"runner-{index % 12}",
                )
            )
        self._ensure_test_single_entries(entries, rows)

        priors, stats = builder._collect_strong_single_pair_transition_priors(
            rows,
            entries,
        )
        separator = builder.QUERY_PATH_FILE_SEPARATOR
        self.assertIn(("nishuo", f"\u4f60{separator}\u8bf4"), priors)
        self.assertIn(("nishuo", f"\u502a{separator}\u6714"), priors)
        self.assertEqual(
            2,
            sum(1 for query, _path in priors if query == "nishuo"),
        )
        self.assertEqual(1, stats["strong_single_pair_runner_up_emitted"])

    def test_strong_single_pairs_do_not_cross_dictionary_word_boundaries(
        self,
    ) -> None:
        def entry(pinyin: str, text: str) -> tuple[str, str, int, int, int]:
            return pinyin, text, 700, 1, 700

        entries = {
            "\u5e73": [entry("ping", "\u5e73")],
            "\u5b89": [entry("an", "\u5b89")],
            "\u4e0d": [entry("bu", "\u4e0d")],
            "\u884c": [entry("xing", "\u884c")],
            "\u5e73\u5b89": [entry("pingan", "\u5e73\u5b89")],
            "\u4e0d\u884c": [entry("buxing", "\u4e0d\u884c")],
        }
        rows = [
            (f"{chr(0x4e10 + index)}\u5e73\u5b89\u4e0d\u884c{chr(0x4e40 + index)}", f"source-{index % 6}")
            for index in range(18)
        ]
        self._ensure_test_single_entries(entries, rows)

        priors, stats = builder._collect_strong_single_pair_transition_priors(
            rows,
            entries,
        )
        separator = builder.QUERY_PATH_FILE_SEPARATOR
        self.assertNotIn(("anbu", f"\u5b89{separator}\u4e0d"), priors)
        self.assertGreater(stats["strong_single_pair_skipped_count"], 0)

    def test_single_character_lm_entries_use_stable_primary_reading(self) -> None:
        char = "\u5dee"
        entries, _rank_info = builder._build_lm_entry_indexes(
            {},
            max_segment_units=4,
            single_char_readings_map={char: {"cha", "chai"}},
            single_char_default_pinyin_map={char: "cha"},
            single_char_source_rank_map={(char, "cha"): 3, (char, "chai"): 3},
            single_char_pinlu_detail_map={(char, "cha"): 241, (char, "chai"): 26},
            char_frequency_prior={char: 0.8},
        )

        self.assertEqual("cha", entries[char][0][0])
        self.assertGreater(entries[char][0][2], entries[char][1][2])

    def test_jsonl_chat_is_streamed_and_holdout_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            corpus_dir = pathlib.Path(temp_dir)
            train_dir = corpus_dir / "chat"
            train_dir.mkdir()
            train_record = {
                "messages": [
                    {"role": "user", "content": "\u63d0\u9ad8\u5f88\u591a"},
                    {"role": "assistant", "content": "\u5dee\u4e0d\u5c11"},
                ]
            }
            (train_dir / "train.jsonl").write_text(
                json.dumps(train_record, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            (train_dir / "validation.jsonl").write_text(
                json.dumps(
                    {"text": "\u4e0d\u5e94\u8fdb\u5165\u8bad\u7ec3"},
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            stats = builder._new_lm_corpus_stats()
            rows = list(
                builder._stream_lm_corpus_sentences(
                    corpus_dir,
                    min_units=3,
                    max_units=40,
                    convert_text=lambda value: value,
                    stats=stats,
                )
            )

            self.assertEqual(
                ["\u63d0\u9ad8\u5f88\u591a", "\u5dee\u4e0d\u5c11"],
                [text for text, _source in rows],
            )
            self.assertEqual(1, stats["lm_corpus_jsonl_skipped_holdout_files"])

    def test_mixed_and_long_chat_content_preserves_local_transitions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            corpus_dir = pathlib.Path(temp_dir)
            long_prefix = "\u8fd9\u662f\u4e00\u6bb5\u8d85\u8fc7\u56db\u5341\u4e2a\u5b57\u4f46\u662f\u6ca1\u6709\u4efb\u4f55\u6807\u70b9\u7684\u4e2d\u6587\u804a\u5929\u5185\u5bb9\u7528\u6765\u9a8c\u8bc1\u957f\u6587\u5207\u5206\u540e\u4ecd\u7136\u4fdd\u7559"
            record = {
                "messages": [
                    {
                        "role": "user",
                        "content": f"meta1{long_prefix}\u5dee\u4e0d\u5c11\u540e\u7eed\u5185\u5bb9",
                    }
                ]
            }
            (corpus_dir / "train.jsonl").write_text(
                json.dumps(record, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

            stats = builder._new_lm_corpus_stats()
            rows = list(
                builder._stream_lm_corpus_sentences(
                    corpus_dir,
                    min_units=4,
                    max_units=40,
                    convert_text=lambda value: value,
                    stats=stats,
                )
            )

            self.assertTrue(any("\u5dee\u4e0d\u5c11" in text for text, _source in rows))
            self.assertGreater(stats["lm_corpus_salvaged_mixed_fragments"], 0)
            self.assertGreater(stats["lm_corpus_split_long_runs"], 0)

    def test_large_corpus_preparation_uses_overlapping_cjk_chunks(self) -> None:
        target = "\u5dee\u4e0d\u5c11"
        prefix = "\u8bed\u6599" * 20
        fragments = list(
            preparer._iter_fragments(
                f"meta1{prefix}{target}\u540e\u7eed\u5185\u5bb9",
                min_units=4,
                max_units=40,
            )
        )

        self.assertTrue(any(target in fragment for fragment in fragments))
        self.assertTrue(all(4 <= len(fragment) <= 40 for fragment in fragments))

    def test_exact_pairs_use_independent_evidence_and_homophone_guard(self) -> None:
        self.assertIn("\u9084", builder.LM_PRODUCTIVE_SINGLE_PREFIX_CHARS)
        self.assertIn("\u6703", builder.LM_PRODUCTIVE_PREDICATE_ONLY_HEADS)

        def entry(
            pinyin: str,
            text: str,
            weight: int,
            rank: int = 1,
            top_weight: int | None = None,
        ) -> tuple[str, str, int, int, int]:
            return pinyin, text, weight, rank, top_weight or weight

        entries = {
            "\u5dee": [entry("cha", "\u5dee", 445, 4, 451)],
            "\u4e0d\u5c11": [entry("bushao", "\u4e0d\u5c11", 1000)],
            "\u53ef": [entry("ke", "\u53ef", 700)],
            "\u80fd": [entry("neng", "\u80fd", 700)],
            "\u9a8c\u8bc1": [entry("yanzheng", "\u9a8c\u8bc1", 1000)],
            "\u8981": [entry("yao", "\u8981", 766)],
            "\u5347\u7ea7": [entry("shengji", "\u5347\u7ea7", 1000)],
            "\u9700\u8981": [entry("xuyao", "\u9700\u8981", 1000)],
            "\u60f3\u8981": [entry("xiangyao", "\u60f3\u8981", 1000)],
            "\u8fd8\u8981": [entry("haiyao", "\u8fd8\u8981", 900)],
            "\u5c31\u8981": [entry("jiuyao", "\u5c31\u8981", 900)],
            "\u4e0d\u8981": [entry("buyao", "\u4e0d\u8981", 1000)],
            "\u53ea\u8981": [entry("zhiyao", "\u53ea\u8981", 1000)],
            "\u5c06\u8981": [entry("jiangyao", "\u5c06\u8981", 900)],
            "\u5feb\u8981": [entry("kuaiyao", "\u5feb\u8981", 900)],
            "\u4e0d": [entry("bu", "\u4e0d", 800)],
            "\u5e76\u4e0d": [entry("bingbu", "\u5e76\u4e0d", 720)],
            "\u80fd\u4e0d": [entry("nengbu", "\u80fd\u4e0d", 700)],
            "\u5c31\u4e0d": [entry("jiubu", "\u5c31\u4e0d", 760)],
            "\u4f7f\u7528": [entry("shiyong", "\u4f7f\u7528", 1036)],
            "\u5b9e\u7528": [entry("shiyong", "\u5b9e\u7528", 628, 2, 1036)],
            "\u597d\u5403": [entry("haochi", "\u597d\u5403", 1000)],
            "\u5403\u996d": [entry("chifan", "\u5403\u996d", 1000)],
            "\u5c31": [entry("jiu", "\u5c31", 760)],
            "\u7ea2\u8272": [entry("hongse", "\u7ea2\u8272", 1000)],
            "\u6210\u5c31": [entry("chengjiu", "\u6210\u5c31", 1000)],
            "\u53ef\u4ee5": [entry("keyi", "\u53ef\u4ee5", 1000)],
            "\u4f1a": [entry("hui", "\u4f1a", 760)],
            "\u671f\u95f4": [entry("qijian", "\u671f\u95f4", 1000)],
            "\u8fd0\u52a8\u4f1a": [entry("yundonghui", "\u8fd0\u52a8\u4f1a", 1000)],
            "\u59d4\u5458\u4f1a": [entry("weiyuanhui", "\u59d4\u5458\u4f1a", 1000)],
            "\u53d1\u5e03\u4f1a": [entry("fabuhui", "\u53d1\u5e03\u4f1a", 1000)],
            "\u4ea4\u6d41\u4f1a": [entry("jiaoliuhui", "\u4ea4\u6d41\u4f1a", 1000)],
            "\u6280\u672f": [entry("jishu", "\u6280\u672f", 1000)],
            "\u90fd": [entry("dou", "\u90fd", 780)],
            "\u5317\u4eac": [entry("beijing", "\u5317\u4eac", 1000)],
            "\u63d0\u9ad8": [entry("tigao", "\u63d0\u9ad8", 1000)],
            "\u964d\u4f4e": [entry("jiangdi", "\u964d\u4f4e", 1000)],
            "\u5f88\u591a": [entry("henduo", "\u5f88\u591a", 700)],
            "\u6548\u7387": [entry("xiaolv", "\u6548\u7387", 1000)],
            "\u5927\u5bb6": [entry("dajia", "\u5927\u5bb6", 1000)],
            "\u5f88\u5feb": [entry("henkuai", "\u5f88\u5feb", 700)],
            "\u6062\u590d": [entry("huifu", "\u6062\u590d", 945)],
            "\u56de\u590d": [entry("huifu", "\u56de\u590d", 525, 2, 945)],
            "\u4f26\u7406": [entry("lunli", "\u4f26\u7406", 700)],
            "\u8bba\u7406": [entry("lunli", "\u8bba\u7406", 634, 2, 700)],
            "\u539f\u5219": [entry("yuanze", "\u539f\u5219", 1000)],
        }
        left_contexts = "\u7532\u4e59\u4e19\u4e01\u620a\u5df1\u5e9a\u8f9b\u58ec\u7678"
        right_contexts = "\u5b50\u4e11\u5bc5\u536f\u8fb0\u5df3\u5348\u672a\u7533\u9149"
        rows: list[tuple[str, str]] = []

        for index in range(4):
            # Four independent sentence-final occurrences exercise the
            # medium-confidence exact-pair tier without looking like one
            # lexical embedding context.
            suffix = ""
            rows.append(
                (
                    left_contexts[index] + "\u5dee\u4e0d\u5c11" + suffix,
                    f"difference-{index}",
                )
            )
        for index in range(12):
            rows.append(
                (
                    left_contexts[index % len(left_contexts)]
                    + "\u53ef\u9a8c\u8bc1"
                    + right_contexts[index % len(right_contexts)],
                    f"validate-{index}",
                )
            )
        for index in range(4):
            rows.append(
                (
                    left_contexts[index] + "\u53ef\u5403\u996d" + right_contexts[index],
                    f"weak-edible-{index}",
                )
            )
        embedded_upgrade_heads = "\u9700\u60f3\u8fd8\u5c31\u4e0d\u53ea\u5c06\u5feb"
        for index in range(20):
            head = embedded_upgrade_heads[index % len(embedded_upgrade_heads)]
            rows.append(
                (
                    head + "\u8981\u5347\u7ea7" +
                    right_contexts[index % len(right_contexts)],
                    f"upgrade-embedded-{index}",
                )
            )
        for index in range(12):
            rows.append(
                (
                    left_contexts[index % len(left_contexts)] +
                    "\u8981\u5347\u7ea7" +
                    right_contexts[index % len(right_contexts)],
                    f"upgrade-direct-{index}",
                )
            )
        # Inflate both component marginals so 要|升级 has deliberately low
        # PMI. Its 24 independent observations and unambiguous query still
        # constitute strong absolute evidence.
        for index in range(80):
            rows.append(("\u8981\u5403\u996d", f"upgrade-left-noise-{index}"))
            rows.append(("\u53ef\u4ee5\u5347\u7ea7", f"upgrade-right-noise-{index}"))
        embedded_meeting_heads = (
            "\u8fd0\u52a8\u4f1a",
            "\u59d4\u5458\u4f1a",
            "\u53d1\u5e03\u4f1a",
            "\u4ea4\u6d41\u4f1a",
        )
        for index in range(24):
            rows.append(
                (
                    embedded_meeting_heads[index % len(embedded_meeting_heads)]
                    + "\u671f\u95f4"
                    + right_contexts[index % len(right_contexts)],
                    f"embedded-meeting-period-{index}",
                )
            )
            rows.append(
                (
                    left_contexts[index % len(left_contexts)]
                    + "\u80fd\u6280\u672f"
                    + right_contexts[index % len(right_contexts)],
                    f"nonpredicate-technology-{index}",
                )
            )
            rows.append(
                (
                    left_contexts[index % len(left_contexts)]
                    + "\u90fd\u5317\u4eac"
                    + right_contexts[index % len(right_contexts)],
                    f"named-tail-beijing-{index}",
                )
            )
        for index in range(12):
            rows.append(
                (
                    "\u6210\u5c31\u7ea2\u8272" + right_contexts[index % len(right_contexts)],
                    f"embedded-red-{index}",
                )
            )
        for index in range(12):
            rows.append(
                (
                    left_contexts[index % len(left_contexts)]
                    + "\u4e0d\u597d\u5403"
                    + right_contexts[index % len(right_contexts)],
                    f"negative-tasty-{index}",
                )
            )
        for index in range(120):
            rows.append(
                (
                    left_contexts[index % len(left_contexts)]
                    + "\u4e0d\u4f7f\u7528"
                    + right_contexts[index % len(right_contexts)],
                    f"not-use-{index}",
                )
            )
        for index in range(7):
            rows.append(
                (
                    left_contexts[index % len(left_contexts)]
                    + "\u4e0d\u5b9e\u7528"
                    + right_contexts[index % len(right_contexts)],
                    f"not-practical-{index}",
                )
            )
        for index, sentence in enumerate(
            (
                "\u5e76\u4e0d\u5b9e\u7528\u3002",
                "\u80fd\u4e0d\u5b9e\u7528\u5417\u3002",
                "\u5c31\u4e0d\u5b9e\u7528\u4e86\u3002",
                "\u53c8\u5e76\u4e0d\u5b9e\u7528\u3002",
            )
        ):
            rows.append((sentence, f"not-practical-extension-{index}"))
        for index in range(4):
            rows.append(
                (
                    left_contexts[index] + "\u80fd\u9a8c\u8bc1" + right_contexts[index],
                    "repeated-single-source",
                )
            )
        for index in range(10):
            rows.append(
                (
                    left_contexts[index] + "\u4f26\u7406\u539f\u5219" + right_contexts[index],
                    f"ethics-{index}",
                )
            )
        for index in range(15):
            left = left_contexts[index % len(left_contexts)]
            right = right_contexts[(index + 1) % len(right_contexts)]
            rows.append((left + "\u5f88\u5feb\u6062\u590d" + right, f"recover-{index}"))
        for index in range(2):
            rows.append(
                (
                    right_contexts[index] + "\u5f88\u5feb\u56de\u590d" + left_contexts[index],
                    f"reply-{index}",
                )
            )
        for index in range(22):
            left = left_contexts[index % len(left_contexts)]
            right = right_contexts[(index + 2) % len(right_contexts)]
            rows.append((left + "\u63d0\u9ad8\u5f88\u591a" + right, f"improve-{index}"))

        # Five independent sources and twenty direct observations are enough
        # for completion, even when very common component marginals make PMI
        # too weak for the ordinary blue transition channel.
        for source_index in range(5):
            for occurrence_index in range(4):
                context_index = source_index + occurrence_index
                rows.append(
                    (
                        left_contexts[context_index % len(left_contexts)]
                        + "\u964d\u4f4e\u5f88\u591a"
                        + right_contexts[(context_index + 3) % len(right_contexts)],
                        f"lower-common-{source_index}",
                    )
                )
        for index in range(80):
            rows.append(("\u964d\u4f4e\u6548\u7387", f"lower-left-noise-{index}"))
            rows.append(("\u5927\u5bb6\u5f88\u591a", f"lower-right-noise-{index}"))

        completion_evidence = {}
        priors, stats = builder._collect_short_exact_pair_transition_priors(
            rows,
            entries,
            jieba_pos_map={
                "\u9a8c\u8bc1": "v",
                "\u5347\u7ea7": "v",
                "\u597d\u5403": "a",
                "\u4f7f\u7528": "v",
                "\u5b9e\u7528": "a",
                "\u5403\u996d": "v",
                "\u7ea2\u8272": "n",
                "\u671f\u95f4": "f",
                "\u6280\u672f": "n",
                "\u5317\u4eac": "ns",
            },
            completion_evidence_out=completion_evidence,
        )

        separator = builder.QUERY_PATH_FILE_SEPARATOR
        difference_key = ("chabushao", f"\u5dee{separator}\u4e0d\u5c11")
        self.assertIn(difference_key, priors)
        self.assertGreaterEqual(priors[difference_key], 390)
        self.assertLessEqual(priors[difference_key], 399)
        self.assertIn(
            ("keyanzheng", f"\u53ef{separator}\u9a8c\u8bc1"),
            priors,
        )
        self.assertNotIn(
            ("nengyanzheng", f"\u80fd{separator}\u9a8c\u8bc1"),
            priors,
        )
        self.assertIn(
            ("yaoshengji", f"\u8981{separator}\u5347\u7ea7"),
            priors,
        )
        self.assertIn(
            ("buhaochi", f"\u4e0d{separator}\u597d\u5403"),
            priors,
        )
        not_practical_key = (
            "bushiyong",
            f"\u4e0d{separator}\u5b9e\u7528",
        )
        self.assertIn(not_practical_key, priors)
        self.assertEqual(
            builder.LM_STRONG_PRODUCTIVE_RUNNER_UP_WEIGHT,
            priors[not_practical_key],
        )
        self.assertGreaterEqual(
            stats[
                "short_exact_pair_productive_prefix_strong_runner_up_emitted"
            ],
            1,
        )
        self.assertNotIn(
            ("kechifan", f"\u53ef{separator}\u5403\u996d"),
            priors,
        )
        self.assertNotIn(
            ("jiuhongse", f"\u5c31{separator}\u7ea2\u8272"),
            priors,
        )
        self.assertNotIn(
            ("huiqijian", f"\u4f1a{separator}\u671f\u95f4"),
            priors,
        )
        self.assertNotIn(
            ("nengjishu", f"\u80fd{separator}\u6280\u672f"),
            priors,
        )
        self.assertNotIn(
            ("doubeijing", f"\u90fd{separator}\u5317\u4eac"),
            priors,
        )
        self.assertGreaterEqual(
            stats["short_exact_pair_productive_prefix_nonpredicate_tail_skipped"],
            1,
        )
        self.assertGreaterEqual(
            stats["short_exact_pair_productive_prefix_named_tail_skipped"],
            1,
        )
        self.assertGreaterEqual(
            stats["short_exact_pair_productive_prefix_extension_bypassed"],
            1,
        )
        self.assertGreaterEqual(
            stats["short_exact_pair_productive_prefix_weak_skipped"],
            1,
        )
        self.assertIn(("tigaohenduo", f"\u63d0\u9ad8{separator}\u5f88\u591a"), priors)
        lower_common_key = (
            "jiangdihenduo",
            f"\u964d\u4f4e{separator}\u5f88\u591a",
        )
        self.assertNotIn(lower_common_key, priors)
        self.assertIn(lower_common_key, completion_evidence)
        self.assertIn(("lunliyuanze", f"\u4f26\u7406{separator}\u539f\u5219"), priors)
        self.assertNotIn(("henkuaihuifu", f"\u5f88\u5feb{separator}\u6062\u590d"), priors)

        not_use_key = (
            "bushiyong",
            f"\u4e0d{separator}\u4f7f\u7528",
        )
        selection_input = dict(priors)
        selection_input[not_use_key] = 480
        selected, selection_stats = builder._select_dedicated_lm_transitions(
            {},
            selection_input,
            stats_prefix="test",
        )
        self.assertIn(not_use_key, selected)
        self.assertIn(not_practical_key, selected)
        self.assertGreaterEqual(
            selection_stats[
                "test_lm_transition_selected_strong_productive_runner_up"
            ],
            1,
        )


if __name__ == "__main__":
    unittest.main()
