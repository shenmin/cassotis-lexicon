#!/usr/bin/env python3

from __future__ import annotations

import pathlib
import tempfile
import unittest

import build_long_completion_index as builder


class LongCompletionIndexTests(unittest.TestCase):
    def test_completion_rows_keep_local_suffixes_and_bound_each_anchor(self) -> None:
        paths = [
            builder.PathEvidence(
                ("anchor", f"suffix{index}"),
                (("an",), (f"s{index}",)),
                800 - index,
                9,
            )
            for index in range(12)
        ]

        rows = builder._completion_rows(paths)

        self.assertEqual(builder.MAX_ROWS_PER_ANCHOR, len(rows))
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
            ]
        )

        self.assertEqual([], rows)

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
                "甲\tyi\t乙\t乙\t712\t5",
                output.read_text(encoding="utf-8").strip(),
            )


if __name__ == "__main__":
    unittest.main()
