#!/usr/bin/env python3
"""
Validate regression samples against generated dictionary files.

Dictionary format:
  pinyin<TAB>text<TAB>weight

Sample format:
  pinyin<TAB>expected_text<TAB>max_rank(optional, default=10)
"""

from __future__ import annotations

import argparse
import pathlib
from typing import Dict, List, Tuple


def load_dict(path: pathlib.Path) -> Dict[str, List[Tuple[str, int]]]:
    bucket: Dict[str, Dict[str, int]] = {}
    with path.open("r", encoding="utf-8") as f:
        for line_no, raw_line in enumerate(f, start=1):
            line = raw_line.strip()
            if not line:
                continue

            parts = line.split("\t")
            if len(parts) != 3:
                raise ValueError(f"{path}:{line_no} invalid column count")

            pinyin = parts[0].strip()
            text = parts[1].strip()
            try:
                weight = int(parts[2].strip())
            except ValueError as exc:
                raise ValueError(f"{path}:{line_no} invalid weight") from exc

            if not pinyin or not text:
                raise ValueError(f"{path}:{line_no} empty pinyin/text")

            if pinyin not in bucket:
                bucket[pinyin] = {}
            prev = bucket[pinyin].get(text, -10**9)
            if weight > prev:
                bucket[pinyin][text] = weight

    finalized: Dict[str, List[Tuple[str, int]]] = {}
    for pinyin, mapping in bucket.items():
        finalized[pinyin] = sorted(mapping.items(), key=lambda kv: (-kv[1], kv[0]))
    return finalized


def load_samples(path: pathlib.Path, default_rank: int) -> List[Tuple[str, str, int]]:
    samples: List[Tuple[str, str, int]] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, raw_line in enumerate(f, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split("\t")
            if len(parts) < 2:
                raise ValueError(f"{path}:{line_no} invalid sample row")

            pinyin = parts[0].strip()
            expected_text = parts[1].strip()
            max_rank = default_rank
            if len(parts) >= 3 and parts[2].strip():
                try:
                    max_rank = int(parts[2].strip())
                except ValueError as exc:
                    raise ValueError(f"{path}:{line_no} invalid max_rank") from exc
            if max_rank <= 0:
                raise ValueError(f"{path}:{line_no} max_rank must be positive")

            samples.append((pinyin, expected_text, max_rank))
    return samples


def validate(
    mapping: Dict[str, List[Tuple[str, int]]],
    samples: List[Tuple[str, str, int]],
    preview_n: int,
) -> List[str]:
    errors: List[str] = []

    for pinyin, expected_text, max_rank in samples:
        candidates = mapping.get(pinyin, [])
        if not candidates:
            errors.append(f"{pinyin}: no candidates, expected '{expected_text}'")
            continue

        rank = -1
        for idx, (text, _weight) in enumerate(candidates, start=1):
            if text == expected_text:
                rank = idx
                break

        if rank <= 0:
            preview = ", ".join(text for text, _ in candidates[:preview_n])
            errors.append(
                f"{pinyin}: missing '{expected_text}' (top{preview_n}: {preview})"
            )
            continue

        if rank > max_rank:
            preview = ", ".join(text for text, _ in candidates[:preview_n])
            errors.append(
                f"{pinyin}: '{expected_text}' rank={rank} exceeds max_rank={max_rank} "
                f"(top{preview_n}: {preview})"
            )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate lexicon regression samples.")
    parser.add_argument("--dict", required=True, dest="dict_path")
    parser.add_argument("--samples", required=True, dest="samples_path")
    parser.add_argument("--default-rank", type=int, default=10)
    parser.add_argument("--preview-top", type=int, default=8)
    args = parser.parse_args()

    dict_path = pathlib.Path(args.dict_path).resolve()
    samples_path = pathlib.Path(args.samples_path).resolve()
    if not dict_path.exists():
        raise FileNotFoundError(f"dict file not found: {dict_path}")
    if not samples_path.exists():
        raise FileNotFoundError(f"samples file not found: {samples_path}")

    mapping = load_dict(dict_path)
    samples = load_samples(samples_path, args.default_rank)
    errors = validate(mapping, samples, args.preview_top)

    if errors:
        print("Regression sample validation failed:")
        for item in errors:
            print(f"- {item}")
        return 1

    print(
        f"Regression sample validation passed: samples={len(samples)} "
        f"dict={dict_path.name}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
