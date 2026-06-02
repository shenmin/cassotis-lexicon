#!/usr/bin/env python3
"""Update or validate README dictionary snapshot counts.

The published dictionary size is the number of rows in generated dictionary
files, not the intermediate map size printed by the builder.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import re
import sys
from pathlib import Path


SNAPSHOT_FILES = (
    "data/generated/dict_clean_sc.txt",
    "data/generated/dict_clean_tc.txt",
    "data/generated/dict_unihan_sc.txt",
    "data/generated/dict_unihan_tc.txt",
)

README_FILES = ("README.md", "README.CN.md")


def count_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8") as f:
        return sum(1 for _ in f)


def replace_snapshot_date(text: str, build_date: str) -> str:
    lines = []
    for line in text.splitlines(keepends=True):
        if "Current dictionary snapshot" in line or "\u5f53\u524d\u8bcd\u5e93\u5feb\u7167" in line:
            line = re.sub(r"\d{4}-\d{2}-\d{2}", build_date, line, count=1)
        lines.append(line)
    return "".join(lines)


def replace_row_count(text: str, rel_path: str, count_text: str) -> str:
    escaped_path = re.escape(f"`{rel_path}`")
    pattern = re.compile(rf"^(\|\s*{escaped_path}\s*\|[^|]*\|[ \t]*)[\d,]+([ \t]*\|)[ \t]*$", re.MULTILINE)
    updated, replacements = pattern.subn(rf"\g<1>{count_text}\g<2>", text)
    if replacements != 1:
        raise ValueError(f"snapshot row not found or duplicated: {rel_path}")
    return updated


def update_readme(path: Path, counts: dict[str, int], build_date: str) -> bool:
    original = path.read_text(encoding="utf-8")
    updated = replace_snapshot_date(original, build_date)
    for rel_path, count in counts.items():
        updated = replace_row_count(updated, rel_path, f"{count:,}")
    if updated == original:
        return False
    path.write_text(updated, encoding="utf-8", newline="\n")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Update README dictionary snapshot counts.")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--date", default=_dt.date.today().isoformat(), help="snapshot build date")
    parser.add_argument("--check", action="store_true", help="fail if README files are not up to date")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    counts: dict[str, int] = {}
    for rel_path in SNAPSHOT_FILES:
        path = root / rel_path
        if not path.exists():
            raise FileNotFoundError(path)
        counts[rel_path] = count_rows(path)

    changed = []
    for rel_path in README_FILES:
        path = root / rel_path
        if not path.exists():
            raise FileNotFoundError(path)
        original = path.read_text(encoding="utf-8")
        updated = replace_snapshot_date(original, args.date)
        for dict_rel_path, count in counts.items():
            updated = replace_row_count(updated, dict_rel_path, f"{count:,}")
        if updated != original:
            changed.append(rel_path)
            if not args.check:
                path.write_text(updated, encoding="utf-8", newline="\n")

    if args.check and changed:
        print("README dictionary snapshot is stale:", ", ".join(changed), file=sys.stderr)
        for rel_path, count in counts.items():
            print(f"{rel_path}: {count:,}", file=sys.stderr)
        return 1

    for rel_path, count in counts.items():
        print(f"{rel_path}: {count:,}")
    if changed:
        print("Updated:", ", ".join(changed))
    else:
        print("README dictionary snapshot already up to date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
