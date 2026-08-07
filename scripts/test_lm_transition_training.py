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
            "\u5f88\u591a": [entry("henduo", "\u5f88\u591a", 700)],
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
