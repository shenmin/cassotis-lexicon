#!/usr/bin/env python3

from __future__ import annotations

import pathlib
import tempfile
import unittest

import build_long_completion_index as builder


class LongCompletionIndexTests(unittest.TestCase):
    def test_corpus_scoring_keeps_broad_rows_below_prompt_threshold(self) -> None:
        source = builder.PathEvidence(
            ("anchor", "suffix"), (("an",), ("su",)), 430, 0
        )

        broad, strict = builder._score_corpus_path(source, 4, 2, 1)

        self.assertIsNotNone(broad)
        self.assertFalse(strict)
        assert broad is not None
        self.assertLess(broad.evidence, builder.MIN_PAIR_EVIDENCE)
        self.assertEqual(2, broad.source_count)

    def test_corpus_scoring_preserves_strict_rows(self) -> None:
        source = builder.PathEvidence(
            ("anchor", "suffix"), (("an",), ("su",)), 520, 0
        )

        strict_row, strict = builder._score_corpus_path(source, 20, 7, 2)

        self.assertIsNotNone(strict_row)
        self.assertTrue(strict)
        assert strict_row is not None
        self.assertGreaterEqual(strict_row.evidence, builder.MIN_PAIR_EVIDENCE)

    def test_completion_rows_keep_local_suffixes_and_bound_each_anchor(self) -> None:
        paths = [
            builder.PathEvidence(
                ("anchor", f"suffix{index}"),
                (("an",), (f"s{index}",)),
                800 - index,
                9,
            )
            for index in range(32)
        ]

        rows = builder._completion_rows(
            paths, builder.MAX_RECALL_ROWS_PER_ANCHOR
        )

        self.assertEqual(builder.MAX_RECALL_ROWS_PER_ANCHOR, len(rows))
        self.assertTrue(all(row.anchor == ("anchor",) for row in rows))
        self.assertEqual(
            sorted((row.evidence for row in rows), reverse=True),
            [row.evidence for row in rows],
        )

    def test_completion_rows_reject_suffixes_over_six_syllables(self) -> None:
        rows = builder._completion_rows(
            [
                builder.PathEvidence(
                    ("anchor", "longsuffix"),
                    (("an",), tuple(f"s{index}" for index in range(7))),
                    900,
                    12,
                )
            ],
            builder.MAX_RECALL_ROWS_PER_ANCHOR,
        )

        self.assertEqual([], rows)

    def test_completion_rows_keep_strongest_suffix_segmentation(self) -> None:
        rows = builder._completion_rows(
            [
                builder.PathEvidence(
                    ("anchor", "suffix"), (("an",), ("su", "fix")), 720, 8
                ),
                builder.PathEvidence(
                    ("anchor", "suf", "fix"),
                    (("an",), ("su",), ("fix",)),
                    640,
                    7,
                ),
            ],
            builder.MAX_RECALL_ROWS_PER_ANCHOR,
        )

        anchor_rows = [row for row in rows if row.anchor == ("anchor",)]
        self.assertEqual(1, len(anchor_rows))
        self.assertEqual(("suffix",), anchor_rows[0].suffix)
        self.assertEqual(720, anchor_rows[0].evidence)

    def test_pair_only_build_writes_local_paths_without_sentence_data(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            transitions = root / "transition.txt"
            lm_paths = root / "lm.txt"
            output = root / "output.txt"
            transitions.write_text(
                "typed\tjia'yi\t甲乙\t甲|乙\t712\n"
                "typed\tjia'bing\t甲丙\t甲|丙\t559\n",
                encoding="utf-8",
            )
            lm_paths.write_text("", encoding="utf-8")

            stats = builder.build_index(transitions, lm_paths, output)

            self.assertEqual(1, stats["rows"])
            self.assertEqual(
                "甲\tyi\t乙\t乙\t712\t5\t1",
                output.read_text(encoding="utf-8").strip(),
            )


if __name__ == "__main__":
    unittest.main()
