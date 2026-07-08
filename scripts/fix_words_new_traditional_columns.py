#!/usr/bin/env python3
"""Fix Traditional Chinese columns in the 2026-07-07 imported word blocks.

The large words_new import was manually classified into manifest layers, but
many rows kept the simplified text in both SC and TC columns. This tool reuses
the build pipeline's OpenCC phrase and character hints to fill the TC column
for those imported blocks without touching unrelated curated rows.
"""

from __future__ import annotations

import argparse
import gzip
import pathlib
import sys
from typing import Iterable, Set


IMPORT_BEGIN = "# BEGIN words_new_import_2026_07_07"
IMPORT_END = "# END words_new_import_2026_07_07"


def _load_build_helpers(repo_root: pathlib.Path):
    sys.path.insert(0, str(repo_root / "scripts"))
    import build_external_cedict as build  # type: ignore

    opencc_payload = (repo_root / "data" / "cache" / "opencc_stphrases.txt").read_bytes()
    opencc_entries, _stats = build._parse_opencc_entries(  # pylint: disable=protected-access
        build._decode_text(opencc_payload),  # pylint: disable=protected-access
        1,
    )
    opencc_sc_to_tc = build._build_opencc_sc_to_tc_map(opencc_entries)  # pylint: disable=protected-access
    opencc_tc_to_sc = build._build_opencc_tc_to_sc_map(opencc_entries)  # pylint: disable=protected-access
    cedict_entries = _parse_cedict_pairs(repo_root / "data" / "cache" / "cedict.gz", build)
    cedict_sc_to_tc: dict[str, Set[str]] = {}
    cedict_tc_to_sc: dict[str, Set[str]] = {}
    for sc_word, tc_word in cedict_entries:
        if not sc_word or not tc_word or sc_word == tc_word:
            continue
        cedict_sc_to_tc.setdefault(sc_word, set()).add(tc_word)
        cedict_tc_to_sc.setdefault(tc_word, set()).add(sc_word)
    for sc_word, tc_words in cedict_sc_to_tc.items():
        opencc_sc_to_tc.setdefault(sc_word, set()).update(tc_words)
    for tc_word, sc_words in cedict_tc_to_sc.items():
        opencc_tc_to_sc.setdefault(tc_word, set()).update(sc_words)
    _trad_to_simp, simp_to_trad, _sc_chars, _tc_chars = build._build_char_variant_hints(  # pylint: disable=protected-access
        opencc_tc_to_sc,
        opencc_entries,
    )
    return build, opencc_sc_to_tc, simp_to_trad


def _parse_cedict_pairs(path: pathlib.Path, build) -> list[tuple[str, str]]:
    payload = path.read_bytes()
    if payload.startswith(b"\x1f\x8b"):
        payload = gzip.decompress(payload)
    text = payload.decode("utf-8", errors="ignore")
    pairs: list[tuple[str, str]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        matched = build.CEDICT_LINE_RE.match(line)
        if not matched:
            continue
        trad, simp, _pinyin_raw, _defs = matched.groups()
        pairs.append((simp, trad))
    return pairs


def _iter_manifest_files(repo_root: pathlib.Path) -> Iterable[pathlib.Path]:
    manifests_root = repo_root / "manifests"
    for path in sorted(manifests_root.rglob("*.tsv")):
        if path.is_file():
            yield path


def _fix_file(path: pathlib.Path, build, opencc_sc_to_tc, simp_to_trad, dry_run: bool) -> tuple[int, int]:
    original = path.read_text(encoding="utf-8")
    lines = original.splitlines(keepends=True)
    in_import_block = False
    changed = 0
    rows = 0
    output: list[str] = []

    for raw_line in lines:
        line_no_eol = raw_line.rstrip("\r\n")
        eol = raw_line[len(line_no_eol) :]

        if line_no_eol.strip() == IMPORT_BEGIN:
            in_import_block = True
            output.append(raw_line)
            continue
        if line_no_eol.strip() == IMPORT_END:
            in_import_block = False
            output.append(raw_line)
            continue
        if not in_import_block or not line_no_eol or line_no_eol.startswith("#"):
            output.append(raw_line)
            continue

        parts = line_no_eol.split("\t")
        if len(parts) < 3:
            output.append(raw_line)
            continue

        rows += 1
        sc_text = parts[0].strip()
        tc_text = parts[1].strip()
        if not sc_text or not tc_text:
            output.append(raw_line)
            continue

        converted_tc = build._convert_sc_text_to_tc_with_phrase_hints(  # pylint: disable=protected-access
            sc_text,
            opencc_sc_to_tc,
            simp_to_trad,
        )
        if converted_tc and tc_text == sc_text and converted_tc != tc_text:
            parts[1] = converted_tc
            changed += 1
            output.append("\t".join(parts) + eol)
            continue

        output.append(raw_line)

    if changed and not dry_run:
        path.write_text("".join(output), encoding="utf-8", newline="")
    return rows, changed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    repo_root = pathlib.Path(args.repo_root).resolve()
    build, opencc_sc_to_tc, simp_to_trad = _load_build_helpers(repo_root)

    total_rows = 0
    total_changed = 0
    for path in _iter_manifest_files(repo_root):
        rows, changed = _fix_file(path, build, opencc_sc_to_tc, simp_to_trad, args.dry_run)
        if rows or changed:
            rel = path.relative_to(repo_root)
            print(f"{rel}: rows={rows} changed={changed}")
        total_rows += rows
        total_changed += changed

    mode = "dry_run" if args.dry_run else "updated"
    print(f"{mode}: rows={total_rows} changed={total_changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
