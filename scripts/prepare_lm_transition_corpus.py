#!/usr/bin/env python3
"""Prepare a bounded, reproducible Chinese transition-training corpus.

The output contains only short CJK fragments and document-level source IDs.
Large JSONL/Zstandard inputs are streamed and stopped at an explicit fragment
budget, so preparing a sample cannot consume memory proportional to the source.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import pathlib
import re
from typing import Iterator, TextIO, Tuple


CJK_RE = re.compile("[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U0002A6DF]")
CJK_FULL_RE = re.compile(
    "^[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U0002A6DF]+$"
)
CJK_RUN_RE = re.compile(
    "[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U0002A6DF]+"
)
SENTENCE_SPLIT_RE = re.compile(
    r"[\s\u3000\u3001\u3002\uff0c\uff01\uff1f\uff1b\uff1a,.!?;:"
    r"\uff08\uff09()\[\]\u3010\u3011\u300a\u300b"
    r"\u201c\u201d\u2018\u2019\u2026\u2014\-/\\|]+"
)
CHUNK_OVERLAP = 4


def _open_text(path: pathlib.Path) -> Tuple[TextIO, object | None]:
    if path.name.lower().endswith(".zst"):
        try:
            import zstandard  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "Reading .zst inputs requires the 'zstandard' package"
            ) from exc
        raw = path.open("rb")
        reader = zstandard.ZstdDecompressor().stream_reader(raw)
        return io.TextIOWrapper(reader, encoding="utf-8", errors="replace"), raw
    return path.open("r", encoding="utf-8-sig", errors="replace"), None


def _record_text(record: object) -> Tuple[str, str]:
    if not isinstance(record, dict):
        return "", ""
    text = record.get("text")
    if not isinstance(text, str):
        content = record.get("content")
        text = content if isinstance(content, str) else ""
    source = ""
    for key in ("source", "dataset", "id", "doc_id"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            source = value.strip()
            break
    return text, source


def _iter_documents(path: pathlib.Path) -> Iterator[Tuple[str, str]]:
    handle, raw = _open_text(path)
    try:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            text, source = _record_text(record)
            if not text:
                continue
            record_id = ""
            if isinstance(record, dict):
                for key in ("id", "doc_id", "doc_hash"):
                    value = record.get(key)
                    if isinstance(value, str) and value.strip():
                        record_id = value.strip()
                        break
            if not record_id:
                record_id = str(line_number)
            yield text, f"{source or path.stem}:{record_id}"
    finally:
        handle.close()
        if raw is not None:
            raw.close()


def _iter_fragments(text: str, min_units: int, max_units: int) -> Iterator[str]:
    for raw_fragment in SENTENCE_SPLIT_RE.split(text):
        fragment = raw_fragment.strip()
        if not fragment:
            continue
        for cjk_run in CJK_RUN_RE.findall(fragment):
            units = len(CJK_RE.findall(cjk_run))
            if units < min_units:
                continue
            if units <= max_units:
                chunk_starts: Iterator[int] | tuple[int, ...] = (0,)
            else:
                step = max(1, max_units - CHUNK_OVERLAP)
                chunk_starts = (
                    start
                    for start in range(0, units, step)
                    if units - start >= min_units
                )
            for start in chunk_starts:
                chunk = cjk_run[start : start + max_units]
                most_common = max(
                    (chunk.count(ch) for ch in set(chunk)),
                    default=0,
                )
                if len(chunk) >= 8 and most_common * 100 >= len(chunk) * 55:
                    continue
                yield chunk


def _safe_output_name(path: pathlib.Path) -> str:
    name = path.name
    for suffix in (".jsonl.zst", ".jsonl", ".zst"):
        if name.lower().endswith(suffix):
            name = name[: -len(suffix)]
            break
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_") or "corpus"


def prepare_input(
    input_path: pathlib.Path,
    output_path: pathlib.Path,
    *,
    min_units: int,
    max_units: int,
    max_documents: int,
    max_fragments: int,
) -> dict[str, int | str]:
    seen: set[bytes] = set()
    documents = 0
    fragments = 0
    duplicates = 0
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as output:
        for text, source in _iter_documents(input_path):
            documents += 1
            if max_documents > 0 and documents > max_documents:
                documents -= 1
                break
            for fragment in _iter_fragments(text, min_units, max_units):
                digest = hashlib.blake2b(
                    fragment.encode("utf-8"), digest_size=12
                ).digest()
                if digest in seen:
                    duplicates += 1
                    continue
                seen.add(digest)
                output.write(
                    json.dumps(
                        {"source": source, "text": fragment},
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                    + "\n"
                )
                fragments += 1
                if max_fragments > 0 and fragments >= max_fragments:
                    break
            if max_fragments > 0 and fragments >= max_fragments:
                break
    return {
        "input": str(input_path),
        "output": str(output_path),
        "documents": documents,
        "fragments": fragments,
        "duplicates": duplicates,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", action="append", required=True, type=pathlib.Path)
    parser.add_argument("--output-dir", required=True, type=pathlib.Path)
    parser.add_argument("--min-units", type=int, default=4)
    parser.add_argument("--max-units", type=int, default=40)
    parser.add_argument("--max-documents-per-input", type=int, default=50000)
    parser.add_argument("--max-fragments-per-input", type=int, default=300000)
    args = parser.parse_args()

    if args.min_units < 1 or args.max_units < args.min_units:
        parser.error("invalid unit range")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    reports = []
    for input_path in args.input:
        input_path = input_path.resolve()
        if not input_path.is_file():
            parser.error(f"input not found: {input_path}")
        output_path = args.output_dir / f"{_safe_output_name(input_path)}.jsonl"
        report = prepare_input(
            input_path,
            output_path,
            min_units=args.min_units,
            max_units=args.max_units,
            max_documents=args.max_documents_per_input,
            max_fragments=args.max_fragments_per_input,
        )
        reports.append(report)
        print(
            f"prepared={input_path.name} documents={report['documents']} "
            f"fragments={report['fragments']} duplicates={report['duplicates']}"
        )
    manifest = {
        "min_units": args.min_units,
        "max_units": args.max_units,
        "max_documents_per_input": args.max_documents_per_input,
        "max_fragments_per_input": args.max_fragments_per_input,
        "inputs": reports,
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
