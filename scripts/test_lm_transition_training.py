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

        for index in range(5):
            # Four sentence-final occurrences must not look like one lexical
            # embedding context.
            suffix = right_contexts[index] if index == 4 else ""
            rows.append(
                (
                    left_contexts[index] + "\u5dee\u4e0d\u5c11" + suffix,
                    f"difference-{index}",
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

        priors, _stats = builder._collect_short_exact_pair_transition_priors(
            rows,
            entries,
        )

        separator = builder.QUERY_PATH_FILE_SEPARATOR
        difference_key = ("chabushao", f"\u5dee{separator}\u4e0d\u5c11")
        self.assertIn(difference_key, priors)
        self.assertGreaterEqual(priors[difference_key], 390)
        self.assertIn(("tigaohenduo", f"\u63d0\u9ad8{separator}\u5f88\u591a"), priors)
        self.assertIn(("lunliyuanze", f"\u4f26\u7406{separator}\u539f\u5219"), priors)
        self.assertNotIn(("henkuaihuifu", f"\u5f88\u5feb{separator}\u6062\u590d"), priors)


if __name__ == "__main__":
    unittest.main()
