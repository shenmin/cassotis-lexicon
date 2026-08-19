#!/usr/bin/env python3
"""Build a bounded long-sentence continuation index from trained transitions.

The runtime must not enumerate word combinations or retain training sentences.
This builder therefore derives only local two- to four-word paths whose every
adjacent edge already passed the stricter multi-source transition-completion
gate.  The output stores an anchor of one to three exact words and a suffix of
one to three exact words (at most six syllables).
"""

from __future__ import annotations

import argparse
import collections
import dataclasses
import itertools
import json
import math
import pathlib
import re
from typing import Callable, Dict, Iterable, Iterator, List, Sequence, Tuple


PATH_SEPARATOR = "|"
MIN_PAIR_EVIDENCE = 560
MIN_TRIGRAM_EVIDENCE = 430
MIN_CORPUS_COUNT = 12
MIN_CORPUS_SOURCES = 5
MIN_CORPUS_DOMAINS = 2
MAX_SUFFIX_UNITS = 6
MAX_ROWS_PER_ANCHOR = 8
KNOWN_PAIR_SOURCE_FLOOR = 5


@dataclasses.dataclass(frozen=True)
class PairEvidence:
    left: str
    right: str
    left_pinyin: Tuple[str, ...]
    right_pinyin: Tuple[str, ...]
    evidence: int


@dataclasses.dataclass(frozen=True)
class PathEvidence:
    words: Tuple[str, ...]
    pinyin: Tuple[Tuple[str, ...], ...]
    evidence: int
    source_count: int


@dataclasses.dataclass(frozen=True)
class CompletionRow:
    anchor: Tuple[str, ...]
    suffix: Tuple[str, ...]
    suffix_pinyin: Tuple[str, ...]
    evidence: int
    source_count: int


class _AhoMatcher:
    def __init__(self) -> None:
        self._next: List[Dict[str, int]] = [{}]
        self._fail: List[int] = [0]
        self._output: List[List[int]] = [[]]

    def add(self, pattern: str, pattern_id: int) -> None:
        state = 0
        for char in pattern:
            next_state = self._next[state].get(char)
            if next_state is None:
                next_state = len(self._next)
                self._next[state][char] = next_state
                self._next.append({})
                self._fail.append(0)
                self._output.append([])
            state = next_state
        self._output[state].append(pattern_id)

    def build(self) -> None:
        queue: collections.deque[int] = collections.deque()
        for state in self._next[0].values():
            queue.append(state)
        while queue:
            state = queue.popleft()
            for char, next_state in self._next[state].items():
                queue.append(next_state)
                fallback = self._fail[state]
                while fallback and char not in self._next[fallback]:
                    fallback = self._fail[fallback]
                self._fail[next_state] = self._next[fallback].get(char, 0)
                self._output[next_state].extend(
                    self._output[self._fail[next_state]]
                )

    def scan(self, text: str) -> Iterator[int]:
        state = 0
        for char in text:
            while state and char not in self._next[state]:
                state = self._fail[state]
            state = self._next[state].get(char, 0)
            yield from self._output[state]


def _cjk_units(text: str) -> int:
    return len(text)


def _compact_pinyin(parts: Iterable[str]) -> str:
    return "".join(parts).replace("'", "").lower()


def _load_dictionary_readings(path: pathlib.Path) -> Dict[str, List[Tuple[str, ...]]]:
    # Import the same deterministic parser used by the lexicon training
    # pipeline instead of trusting an unrelated pinyin library.
    from build_external_cedict import _runtime_parse_compact_pinyin

    output: Dict[str, List[Tuple[str, ...]]] = collections.defaultdict(list)
    with path.open("r", encoding="utf-8-sig", errors="strict") as handle:
        for raw_line in handle:
            fields = raw_line.rstrip("\r\n").split("\t")
            if len(fields) < 3:
                continue
            pinyin, text, weight_text = fields[:3]
            try:
                weight = int(weight_text)
            except ValueError:
                continue
            if weight <= 0 or not text:
                continue
            syllables = tuple(_runtime_parse_compact_pinyin(_compact_pinyin((pinyin,))))
            if len(syllables) != _cjk_units(text):
                continue
            bucket = output[text]
            if syllables not in bucket and len(bucket) < 8:
                bucket.append(syllables)
    return dict(output)


def _iter_lm_paths(
    path: pathlib.Path,
    readings: Dict[str, List[Tuple[str, ...]]],
) -> Iterator[PathEvidence]:
    with path.open("r", encoding="utf-8-sig", errors="strict") as handle:
        for raw_line in handle:
            fields = raw_line.rstrip("\r\n").split("\t")
            if len(fields) < 3:
                continue
            query_pinyin, path_text, weight_text = fields[:3]
            words = tuple(part.strip() for part in path_text.split(PATH_SEPARATOR))
            if len(words) not in (2, 3) or not all(words):
                continue
            try:
                lm_weight = int(weight_text)
            except ValueError:
                continue
            if lm_weight < MIN_TRIGRAM_EVIDENCE:
                continue
            reading_options = [readings.get(word, ())[:4] for word in words]
            if any(not options for options in reading_options):
                continue
            compact_query = _compact_pinyin((query_pinyin,))
            for pinyin in itertools.product(*reading_options):
                if _compact_pinyin(
                    part for word_pinyin in pinyin for part in word_pinyin
                ) != compact_query:
                    continue
                yield PathEvidence(words, tuple(pinyin), lm_weight, 0)


_CJK_RUN_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+")


def _json_record_texts(record: object) -> Iterator[str]:
    if not isinstance(record, dict):
        return
    messages = record.get("messages")
    if isinstance(messages, list):
        for message in messages:
            if isinstance(message, dict) and isinstance(message.get("content"), str):
                yield message["content"]
        return
    for key in ("text", "content"):
        value = record.get(key)
        if isinstance(value, str):
            yield value
            return


def _iter_corpus_runs(
    corpus_dir: pathlib.Path,
    convert_text: Callable[[str], str],
) -> Iterator[Tuple[str, str, str]]:
    for path in sorted(corpus_dir.rglob("*.txt")):
        relative = path.relative_to(corpus_dir)
        domain = relative.parts[0] if len(relative.parts) > 1 else "novel"
        source = relative.as_posix()
        raw = path.read_text(encoding="utf-8-sig", errors="replace")
        for run in _CJK_RUN_RE.findall(raw):
            converted = convert_text(run)
            if converted:
                yield source, domain, converted

    holdout_names = {"dev.jsonl", "test.jsonl", "validation.jsonl"}
    for path in sorted(corpus_dir.rglob("*.jsonl")):
        if path.name.lower() in holdout_names:
            continue
        relative = path.relative_to(corpus_dir)
        domain = relative.parts[0] if len(relative.parts) > 1 else path.stem
        with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
            for line_number, raw_line in enumerate(handle, start=1):
                try:
                    record = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue
                record_source = ""
                if isinstance(record, dict):
                    for key in ("source", "id", "doc_id"):
                        value = record.get(key)
                        if isinstance(value, str) and value.strip():
                            record_source = value.strip()
                            break
                source = f"{relative.as_posix()}:{record_source or line_number}"
                for text in _json_record_texts(record):
                    for run in _CJK_RUN_RE.findall(text):
                        converted = convert_text(run)
                        if converted:
                            yield source, domain, converted


def _scan_corpus_support(
    paths: Sequence[PathEvidence],
    corpus_dir: pathlib.Path,
    convert_text: Callable[[str], str],
) -> Dict[str, Tuple[int, int, int]]:
    pattern_ids: Dict[str, int] = {}
    patterns: List[str] = []
    for item in paths:
        text = "".join(item.words)
        if text not in pattern_ids:
            pattern_ids[text] = len(patterns)
            patterns.append(text)

    matcher = _AhoMatcher()
    for pattern_id, pattern in enumerate(patterns):
        matcher.add(pattern, pattern_id)
    matcher.build()

    occurrences = [0] * len(patterns)
    source_counts = [0] * len(patterns)
    domain_masks = [0] * len(patterns)
    domain_bits: Dict[str, int] = {}
    current_source = ""
    current_domain_bit = 0
    source_matches: set[int] = set()

    def flush_source() -> None:
        for pattern_id in source_matches:
            source_counts[pattern_id] = min(255, source_counts[pattern_id] + 1)
            domain_masks[pattern_id] |= current_domain_bit
        source_matches.clear()

    for source, domain, text in _iter_corpus_runs(corpus_dir, convert_text):
        if source != current_source:
            if current_source:
                flush_source()
            current_source = source
            bit_index = domain_bits.setdefault(domain, len(domain_bits))
            current_domain_bit = 1 << bit_index
        for pattern_id in matcher.scan(text):
            occurrences[pattern_id] = min(1_000_000, occurrences[pattern_id] + 1)
            source_matches.add(pattern_id)
    if current_source:
        flush_source()

    return {
        pattern: (
            occurrences[pattern_id],
            source_counts[pattern_id],
            domain_masks[pattern_id].bit_count(),
        )
        for pattern_id, pattern in enumerate(patterns)
    }


def _parse_transition_completions(path: pathlib.Path) -> Dict[Tuple[str, str], List[PairEvidence]]:
    pairs: Dict[Tuple[str, str], Dict[Tuple[Tuple[str, ...], Tuple[str, ...]], PairEvidence]] = {}
    with path.open("r", encoding="utf-8-sig", errors="strict") as handle:
        for raw_line in handle:
            fields = raw_line.rstrip("\r\n").split("\t")
            if len(fields) != 5:
                continue
            _typed_prefix, full_pinyin, full_text, path_text, evidence_text = fields
            words = tuple(part.strip() for part in path_text.split(PATH_SEPARATOR))
            if len(words) != 2 or not all(words):
                continue
            try:
                evidence = int(evidence_text)
            except ValueError:
                continue
            if evidence < MIN_PAIR_EVIDENCE:
                continue
            syllables = tuple(part.strip().lower() for part in full_pinyin.split("'") if part.strip())
            left_units = _cjk_units(words[0])
            right_units = _cjk_units(words[1])
            if len(syllables) != left_units + right_units or "".join(words) != full_text:
                continue
            left_pinyin = syllables[:left_units]
            right_pinyin = syllables[left_units:]
            item = PairEvidence(words[0], words[1], left_pinyin, right_pinyin, evidence)
            bucket = pairs.setdefault((words[0], words[1]), {})
            key = (left_pinyin, right_pinyin)
            previous = bucket.get(key)
            if previous is None or item.evidence > previous.evidence:
                bucket[key] = item
    return {
        key: sorted(values.values(), key=lambda item: (-item.evidence, item.left_pinyin, item.right_pinyin))
        for key, values in pairs.items()
    }


def _parse_lm_trigrams(
    lm_paths: Iterable[PathEvidence],
    pairs: Dict[Tuple[str, str], List[PairEvidence]],
) -> List[PathEvidence]:
    output: Dict[Tuple[Tuple[str, ...], Tuple[Tuple[str, ...], ...]], PathEvidence] = {}
    for lm_item in lm_paths:
        words = lm_item.words
        lm_weight = lm_item.evidence
        if len(words) != 3:
            continue
        left_pairs = pairs.get((words[0], words[1]), ())
        right_pairs = pairs.get((words[1], words[2]), ())
        if not left_pairs or not right_pairs:
            continue
        for left in left_pairs[:4]:
            for right in right_pairs[:4]:
                if left.right_pinyin != right.left_pinyin:
                    continue
                pinyin = (left.left_pinyin, left.right_pinyin, right.right_pinyin)
                if pinyin != lm_item.pinyin:
                    continue
                evidence = min(left.evidence, right.evidence) + max(0, lm_weight - 360)
                item = PathEvidence(words, pinyin, evidence, KNOWN_PAIR_SOURCE_FLOOR)
                key = (words, pinyin)
                previous = output.get(key)
                if previous is None or item.evidence > previous.evidence:
                    output[key] = item
    return sorted(output.values(), key=lambda item: (item.words, -item.evidence, item.pinyin))


def _pair_paths(pairs: Dict[Tuple[str, str], List[PairEvidence]]) -> Iterator[PathEvidence]:
    for words in sorted(pairs):
        for pair in pairs[words]:
            yield PathEvidence(
                words,
                (pair.left_pinyin, pair.right_pinyin),
                pair.evidence,
                KNOWN_PAIR_SOURCE_FLOOR,
            )


def _join_four_word_paths(trigrams: Sequence[PathEvidence]) -> Iterator[PathEvidence]:
    by_head: Dict[Tuple[str, str], List[PathEvidence]] = collections.defaultdict(list)
    by_tail: Dict[Tuple[str, str], List[PathEvidence]] = collections.defaultdict(list)
    for item in trigrams:
        by_head[item.words[:2]].append(item)
        by_tail[item.words[1:]].append(item)
    for middle in sorted(set(by_tail).intersection(by_head)):
        left_rows = sorted(by_tail[middle], key=lambda item: -item.evidence)[:6]
        right_rows = sorted(by_head[middle], key=lambda item: -item.evidence)[:6]
        for left in left_rows:
            for right in right_rows:
                if left.pinyin[1:] != right.pinyin[:2]:
                    continue
                words = left.words + (right.words[2],)
                pinyin = left.pinyin + (right.pinyin[2],)
                evidence = min(left.evidence, right.evidence) - 36
                if evidence < MIN_PAIR_EVIDENCE:
                    continue
                yield PathEvidence(words, pinyin, evidence, KNOWN_PAIR_SOURCE_FLOOR)


def _completion_rows(paths: Iterable[PathEvidence]) -> List[CompletionRow]:
    best: Dict[Tuple[Tuple[str, ...], Tuple[str, ...], Tuple[str, ...]], CompletionRow] = {}
    for item in paths:
        word_count = len(item.words)
        for anchor_count in range(1, min(3, word_count - 1) + 1):
            anchor = item.words[:anchor_count]
            suffix = item.words[anchor_count:]
            if not suffix or len(suffix) > 3:
                continue
            suffix_pinyin = tuple(
                part
                for word_pinyin in item.pinyin[anchor_count:]
                for part in word_pinyin
            )
            if not suffix_pinyin or len(suffix_pinyin) > MAX_SUFFIX_UNITS:
                continue
            # Longer anchors are more specific; slightly prefer them without
            # changing the underlying transition confidence ordering.
            evidence = item.evidence + (anchor_count - 1) * 18 - (len(suffix) - 1) * 14
            row = CompletionRow(anchor, suffix, suffix_pinyin, evidence, item.source_count)
            key = (anchor, suffix, suffix_pinyin)
            previous = best.get(key)
            if previous is None or row.evidence > previous.evidence:
                best[key] = row

    by_anchor: Dict[Tuple[str, ...], List[CompletionRow]] = collections.defaultdict(list)
    for row in best.values():
        by_anchor[row.anchor].append(row)

    output: List[CompletionRow] = []
    for anchor in sorted(by_anchor):
        rows = sorted(
            by_anchor[anchor],
            key=lambda row: (
                -row.evidence,
                -row.source_count,
                len(row.suffix_pinyin),
                row.suffix,
                row.suffix_pinyin,
            ),
        )
        output.extend(rows[:MAX_ROWS_PER_ANCHOR])
    return output


def build_index(
    transition_completion_path: pathlib.Path,
    lm_transition_path: pathlib.Path,
    output_path: pathlib.Path,
    dictionary_path: pathlib.Path | None = None,
    corpus_dir: pathlib.Path | None = None,
    traditional: bool = False,
) -> dict[str, int]:
    pairs = _parse_transition_completions(transition_completion_path)
    corpus_paths: List[PathEvidence] = []
    corpus_accepted = 0
    if dictionary_path is not None and corpus_dir is not None:
        readings = _load_dictionary_readings(dictionary_path)
        raw_lm_paths = list(_iter_lm_paths(lm_transition_path, readings))
        unique_lm_paths = {
            (item.words, item.pinyin): item for item in raw_lm_paths
        }
        raw_lm_paths = list(unique_lm_paths.values())
        if traditional:
            from opencc import OpenCC

            converter = OpenCC("s2t")
            convert_text: Callable[[str], str] = converter.convert
        else:
            convert_text = lambda value: value
        support = _scan_corpus_support(raw_lm_paths, corpus_dir, convert_text)
        for item in raw_lm_paths:
            count, source_count, domain_count = support.get(
                "".join(item.words), (0, 0, 0)
            )
            if (
                count < MIN_CORPUS_COUNT
                or source_count < MIN_CORPUS_SOURCES
                or domain_count < MIN_CORPUS_DOMAINS
            ):
                continue
            evidence = item.evidence
            evidence += min(96, int(round(math.log2(count + 1) * 12)))
            evidence += min(60, source_count * 4)
            evidence += min(36, domain_count * 12)
            corpus_paths.append(
                PathEvidence(item.words, item.pinyin, evidence, source_count)
            )
        corpus_accepted = len(corpus_paths)

    pair_backed_trigrams = _parse_lm_trigrams(corpus_paths, pairs)
    accepted_by_key: Dict[
        Tuple[Tuple[str, ...], Tuple[Tuple[str, ...], ...]], PathEvidence
    ] = {
        (item.words, item.pinyin): item for item in corpus_paths
    }
    for item in pair_backed_trigrams:
        key = (item.words, item.pinyin)
        previous = accepted_by_key.get(key)
        if previous is None or item.evidence > previous.evidence:
            accepted_by_key[key] = item
    accepted_lm_paths = list(accepted_by_key.values())
    trigrams = [item for item in accepted_lm_paths if len(item.words) == 3]
    four_word_paths = list(_join_four_word_paths(trigrams))
    rows = _completion_rows(
        list(_pair_paths(pairs)) + accepted_lm_paths + four_word_paths
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(
                "\t".join(
                    (
                        PATH_SEPARATOR.join(row.anchor),
                        "'".join(row.suffix_pinyin),
                        "".join(row.suffix),
                        PATH_SEPARATOR.join(row.suffix),
                        str(row.evidence),
                        str(row.source_count),
                    )
                )
                + "\n"
            )
    return {
        "strong_pair_paths": sum(len(items) for items in pairs.values()),
        "corpus_validated_lm_paths": corpus_accepted,
        "strong_trigram_paths": len(trigrams),
        "strong_four_word_paths": len(four_word_paths),
        "anchors": len({row.anchor for row in rows}),
        "rows": len(rows),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--transition-completion", required=True, type=pathlib.Path)
    parser.add_argument("--lm-transition", required=True, type=pathlib.Path)
    parser.add_argument("--output", required=True, type=pathlib.Path)
    parser.add_argument("--dictionary", type=pathlib.Path)
    parser.add_argument("--corpus-dir", type=pathlib.Path)
    parser.add_argument("--traditional", action="store_true")
    args = parser.parse_args()
    if (args.dictionary is None) != (args.corpus_dir is None):
        parser.error("--dictionary and --corpus-dir must be provided together")
    stats = build_index(
        args.transition_completion,
        args.lm_transition,
        args.output,
        args.dictionary,
        args.corpus_dir,
        args.traditional,
    )
    for key, value in stats.items():
        print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
