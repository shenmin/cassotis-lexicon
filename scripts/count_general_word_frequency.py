#!/usr/bin/env python3
"""Count how often each dictionary word occurs as a word in general Chinese text.

The input is plain UTF-8 text, a file or a member of a zip archive written
archive.zip!member: Cassotis IME uses the general text its character LM was
trained on (the three general corpora, not its fiction). The words are every
simplified word of two characters or more and the simplified form of every
traditional word.

A word counts where the segmentation of the text into dictionary words uses
it. Each stretch of characters that some word holds is cut into the fewest
words (a character no word covers is one of its own), and between cuts of as
many words the most probable one wins, by the counts of the pass before: the
first pass takes the longest match first, each later pass segments with the
counts of the one before it, six in all (the counts no longer move after the
fifth). So a word inside a longer dictionary word is no occurrence (化为 does
not count inside 转化为), and the most probable cut keeps the occurrences of
the common words: 才|知道 is far more probable than 才知|道, 和|服务 than
和服|务, 十月|中旬 than 十月中|旬. The longest match alone gave every such
overlap to the word that begins first: a new word took the occurrences of
the common words after it (才知 took 知道 out of 才知道), and 和服 was
credited with 和服务, 月中 with 月中旬. A new word can still give a stretch
another cut of as many words that is more probable (就懂|了 for 就|懂了:
counted again with the words of 2026-11-01, 懂了 went from 5,022 to 4,395),
so the words of a batch are counted on their own and the other words keep
their counts (the header of general_word_counts.tsv names such batches).

Only counts leave the text. The output lists the words that occur at least
once: word<TAB>count.

usage: count_general_word_frequency.py --dictionary dict_clean_sc.txt
           --dictionary-tc dict_clean_tc.txt --input <text | archive.zip!member> [...]
           --output manifests/general_word_counts.tsv [--workers N]
"""

from __future__ import annotations

import argparse
import collections
import math
import multiprocessing
import os
import pathlib
import zipfile

import opencc

PASSES = 6
# A cut of fewer words always wins: each word costs this many nats on top of
# its log probability, far more than probabilities ever differ.
WORD_COST = 1000.0
SMOOTHING = 0.5

_worker: dict = {}


def dictionary_words(path: pathlib.Path) -> set[str]:
    words = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) >= 3 and len(fields[1]) >= 2:
            words.add(fields[1])
    return words


def start_worker(words: set[str], counts: tuple[dict, dict] | None) -> None:
    _worker["words"] = words
    _worker["prefixes"] = {word[:size] for word in words for size in range(2, len(word) + 1)}
    _worker["chars"] = set("".join(words))
    _worker["costs"] = None
    if counts is not None:
        word_counts, char_counts = counts
        log_total = math.log(sum(word_counts.values()) + sum(char_counts.values()))
        _worker["costs"] = (
            {word: math.log(word_counts.get(word, 0) + SMOOTHING) - log_total - WORD_COST for word in words},
            {char: math.log(count + SMOOTHING) - log_total - WORD_COST for char, count in char_counts.items()},
            math.log(SMOOTHING) - log_total - WORD_COST)


def stretches(text: str, chars: set[str]):
    start = None
    for index, char in enumerate(text):
        if char in chars:
            if start is None:
                start = index
        elif start is not None:
            yield text[start:index]
            start = None
    if start is not None:
        yield text[start:]


def count_longest_first(text: str, words, prefixes, word_counts, char_counts) -> None:
    index, size = 0, len(text)
    while index < size:
        end, probe = 0, index + 2
        while probe <= size and text[index:probe] in prefixes:
            if text[index:probe] in words:
                end = probe
            probe += 1
        if end:
            word_counts[text[index:end]] += 1
            index = end
        else:
            char_counts[text[index]] += 1
            index += 1


def count_segmented(text: str, prefixes, costs, word_counts, char_counts) -> None:
    word_cost, char_cost, unknown_cost = costs
    size = len(text)
    best = [-math.inf] * (size + 1)
    back = [0] * (size + 1)
    best[0] = 0.0
    for start in range(size):
        base = best[start]
        value = base + char_cost.get(text[start], unknown_cost)
        if value > best[start + 1]:
            best[start + 1] = value
            back[start + 1] = start
        end = start + 2
        while end <= size:
            piece = text[start:end]
            if piece not in prefixes:
                break
            cost = word_cost.get(piece)
            if cost is not None and base + cost > best[end]:
                best[end] = base + cost
                back[end] = start
            end += 1
    end = size
    while end > 0:
        start = back[end]
        if end - start == 1:
            char_counts[text[start]] += 1
        else:
            word_counts[text[start:end]] += 1
        end = start


def count_piece(text: str) -> tuple[collections.Counter, collections.Counter]:
    word_counts: collections.Counter[str] = collections.Counter()
    char_counts: collections.Counter[str] = collections.Counter()
    for stretch in stretches(text, _worker["chars"]):
        if _worker["costs"] is None:
            count_longest_first(stretch, _worker["words"], _worker["prefixes"], word_counts, char_counts)
        else:
            count_segmented(stretch, _worker["prefixes"], _worker["costs"], word_counts, char_counts)
    return word_counts, char_counts


def pieces(source_name: str, size: int = 1 << 21):
    """The text of a file, or of a member of a zip archive, in pieces of whole lines."""
    if "!" in source_name:
        archive_path, member = source_name.split("!", 1)
        source = zipfile.ZipFile(archive_path).open(member)
    else:
        source = open(source_name, "rb")
    rest = b""
    with source:
        while chunk := source.read(size):
            chunk = rest + chunk
            cut = chunk.rfind(b"\n") + 1
            if cut == 0:
                rest = chunk
                continue
            rest = chunk[cut:]
            yield chunk[:cut].decode("utf-8", errors="replace")
    if rest:
        yield rest.decode("utf-8", errors="replace")


def count_pass(words: set[str], counts, inputs: list[str], workers: int):
    word_counts: collections.Counter[str] = collections.Counter()
    char_counts: collections.Counter[str] = collections.Counter()
    with multiprocessing.Pool(workers, initializer=start_worker, initargs=(words, counts)) as pool:
        for path in inputs:
            for piece_words, piece_chars in pool.imap_unordered(count_piece, pieces(path)):
                word_counts.update(piece_words)
                char_counts.update(piece_chars)
    return word_counts, char_counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dictionary", required=True, type=pathlib.Path)
    parser.add_argument("--dictionary-tc", required=True, type=pathlib.Path)
    parser.add_argument("--input", action="append", required=True)
    parser.add_argument("--output", required=True, type=pathlib.Path)
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    args = parser.parse_args()

    to_simplified = opencc.OpenCC("tw2s")
    words = dictionary_words(args.dictionary)
    words |= {to_simplified.convert(word) for word in dictionary_words(args.dictionary_tc)}
    print(f"{len(words)} words", flush=True)
    counts = None
    for number in range(1, PASSES + 1):
        counts = count_pass(words, counts, args.input, args.workers)
        print(f"pass {number} of {PASSES}: {sum(counts[0].values())} words, "
              f"{sum(counts[1].values())} characters alone", flush=True)
    word_counts = counts[0]
    with args.output.open("w", encoding="utf-8", newline="\n") as out:
        out.write("# word\tcount\n")
        out.write("# Occurrences as a word in the general text of the Cassotis character LM:\n")
        sources = ", ".join(pathlib.PurePath(name.split("!")[-1]).name for name in args.input)
        out.write("# " + sources + ".\n")
        out.write("# A word counts where the fewest dictionary words cover the text, the most probable\n")
        out.write("# such cut by the counts of the pass before (six passes from the longest match first).\n")
        out.write("# Generated by scripts/count_general_word_frequency.py; counts only.\n")
        for word in sorted(w for w in words if word_counts[w]):
            out.write(f"{word}\t{word_counts[word]}\n")


if __name__ == "__main__":
    main()
