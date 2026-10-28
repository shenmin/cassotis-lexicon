#!/usr/bin/env python3
"""Order the single characters of each reading by how often modern text uses
them, and types them on their own.

The weights of dict_unihan_{sc,tc}.txt come from Unihan's readings and
frequencies, the Xiandai Hanyu Pinlu counts of the 1980s and school grades:
under zhen, 甄, 贞, 榛, 斟, 臻, 砧, 祯 and 桢 stood above 帧, which video and
games write far more often today. This step keeps the weights each reading
has and gives them to its characters again, the largest to the character
used most:

- The general text of the Cassotis character LM: the geometric mean of a
  character's occurrences (manifests/general_char_counts.tsv) and of its
  occurrences on its own, those less the occurrences inside the dictionary
  words the word counts found it in (manifests/general_word_counts.tsv:
  occurrences as a word, longest match first, so the two add up). Either
  alone misleads: 镇 stands alone in town names more often than 真 (390,586
  against 256,449), and 失 occurs a million times, nearly all inside 失去
  and 失败.
- Written text has few of the characters people type on their own in
  messages (啊, 吗, 没, 啦, 啥): before such counts, 阿 went above 啊 and 马
  above 吗. --chat-counts adds, --chat-weight times (3), the geometric mean
  of a character's general rate and its rate standing alone in typed chat
  messages (per hundred million characters). The mean lifts what both kinds
  of text use and keeps one person's topics down: added as they were, the
  messages' 涨 went above 张. The messages are private: the counts stay
  outside this repository, and only the weights they ordered come here.
- The counts do not say which reading a character had. A character moves
  only under its main reading, the one the sources weigh highest, and only
  where its other readings lie 100 or more below it; under its other readings
  it keeps its weight, which the sources gave by the reading's own frequency
  (和 under hu, 什 under shi), and a character of two common readings (长,
  地, 行) keeps its weights under both. Sharing the counts out by the weights
  instead fed on itself when repeated (a reading that lost weight lost its
  share: 和 went to the 145th place of hu), and pypinyin's reading of a
  character alone is not its common one (zhang for 长).
- A traditional character takes the counts of its simplified form; where two
  forms share them, the present order stays (Taiwan's form first). Run
  normalize_traditional_forms.py after it, as rebuild_all.ps1 does after the
  builds: it puts Taiwan's form first where variants of one reading took other
  counts (麼 above 麽 under mo; 23 rows on 2026-10-27).
- Characters the text never holds keep their present order below the others,
  and so do radicals that web text writes as separators (丨 under gun). The
  audited order of SINGLE_CHAR_RELATIVE_ORDER_OVERRIDES holds (the build
  applies it again after keeping these weights, so it must find it kept), and
  so do the ranks the regression samples give single characters (--samples:
  见 first under jian, 难 under nan).

The multiset of the weights of the moving characters of a reading does not
change: only which character has which. The step orders the weights the
sources gave once (2026-10-27; run on its own output it changes nothing);
the build keeps them (it preserves the previous Unihan weights) and finds the
audited order kept. Judged on text none of the counts saw (the characters
standing alone in it, read in their sentences by pypinyin), the first
character of the reading went from 72.5 to 75.3% of them in held-out chat
messages, from 55.3 to 58.9% in the general text's validation split and from
61.2 to 62.5% in a held-out novel; the first page from 96.6, 91.4 and 92.9%
to 98.5, 94.4 and 95.2%.

usage: build_single_char_frequency.py --char-counts manifests/general_char_counts.tsv
           --word-counts manifests/general_word_counts.tsv --chat-counts <counts>
           --samples manifests/regression_samples.sc.tsv
           --unihan data/generated/dict_unihan_sc.txt [--traditional] [--report report.tsv]
"""

from __future__ import annotations

import argparse
import collections
import pathlib
import sys

import opencc

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from build_external_cedict import (  # noqa: E402
    SINGLE_CHAR_RELATIVE_ORDER_OVERRIDES, _enforce_single_char_relative_order_overrides)

# Characters of the general corpora (9.0 GB of UTF-8, three bytes a character).
GENERAL_CHARS = 9011904782 / 3
# How far a character's other readings lie below its main one for its use to
# count as the main reading's (the weights are logarithmic in the sources'
# frequencies: 100 is a tenth).
MAIN_READING_LEAD = 100
# Radicals that web text writes as separators and marks ("标题丨作者").
SEPARATOR_RADICALS = frozenset("丨丶丿乀乁亅冂冖冫凵勹匚匸卩厶廴廾彐彡彳忄扌氵灬爫犭癶礻罒衤讠阝钅饣纟")


def read_counts(path: pathlib.Path) -> dict[str, int]:
    counts = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            text, count = line.split("\t")
            counts[text] = int(count)
    return counts


def standalone_counts(char_counts: dict[str, int], word_counts: dict[str, int]) -> dict[str, int]:
    inside: collections.Counter[str] = collections.Counter()
    for word, count in word_counts.items():
        for char in word:
            inside[char] += count
    return {char: max(0, count - inside[char]) for char, count in char_counts.items()}


def use_rates(char_counts: pathlib.Path, word_counts: pathlib.Path, chat_counts: pathlib.Path | None,
              chat_weight: float) -> dict[str, float]:
    """Per hundred million characters: the general text's geometric mean, and
    chat_weight times the chat messages' characters standing alone."""
    total = read_counts(char_counts)
    alone = standalone_counts(total, read_counts(word_counts))
    rates = {char: (count * alone[char]) ** 0.5 / GENERAL_CHARS * 1e8 for char, count in total.items()}
    if chat_counts is not None:
        lines = chat_counts.read_text(encoding="utf-8").splitlines()
        chat_chars = int(lines[0].split("\t")[1])
        for char, count in read_counts(chat_counts).items():
            general = rates.get(char, 0.0)
            rates[char] = general + chat_weight * (general * count / chat_chars * 1e8) ** 0.5
    for char in SEPARATOR_RADICALS:
        rates.pop(char, None)
    return rates


def single_char_samples(path: pathlib.Path | None) -> dict[str, list[tuple[str, int]]]:
    """The regression samples of single characters: (character, max rank) by reading."""
    samples: dict[str, list[tuple[str, int]]] = collections.defaultdict(list)
    if path is None:
        return samples
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split("\t")
        if not line or line.startswith("#") or len(fields) < 2 or fields[1].startswith("!"):
            continue
        if len(fields[1]) == 1:
            samples[fields[0]].append((fields[1], int(fields[2]) if len(fields) > 2 and fields[2] else 10))
    return samples


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--char-counts", required=True, type=pathlib.Path)
    parser.add_argument("--word-counts", required=True, type=pathlib.Path)
    parser.add_argument("--chat-counts", type=pathlib.Path)
    parser.add_argument("--chat-weight", type=float, default=3.0)
    parser.add_argument("--samples", type=pathlib.Path)
    parser.add_argument("--unihan", required=True, type=pathlib.Path)
    parser.add_argument("--traditional", action="store_true")
    parser.add_argument("--report", type=pathlib.Path)
    args = parser.parse_args()

    usage = use_rates(args.char_counts, args.word_counts, args.chat_counts, args.chat_weight)
    samples = single_char_samples(args.samples)
    to_simplified = opencc.OpenCC("tw2s") if args.traditional else None
    lines = args.unihan.read_text(encoding="utf-8").splitlines()
    rows = []  # (line index, pinyin, char, weight)
    for index, line in enumerate(lines):
        fields = line.split("\t")
        if not line or line.startswith("#") or len(fields) < 3 or len(fields[1]) != 1:
            continue
        rows.append((index, fields[0], fields[1], int(fields[2])))
    readings: dict[str, list[tuple[int, str]]] = collections.defaultdict(list)
    char_readings: dict[str, set[str]] = collections.defaultdict(set)
    for index, pinyin, char, _weight in rows:
        readings[pinyin].append((index, char))
        char_readings[char].add(pinyin)
    # A character moves only under its main reading, the one the sources
    # weigh highest, and only where its other readings lie 100 or more below
    # it (a tenth of its use or less): 长 (chang, zhang), 地 (di, de) and 行
    # (xing, hang) stay where they are under every reading.
    moving: set[tuple[str, str]] = set()
    by_char: dict[str, list[tuple[int, str]]] = collections.defaultdict(list)
    for _index, pinyin, char, weight in rows:
        by_char[char].append((weight, pinyin))
    for char, weighted in by_char.items():
        weighted.sort(reverse=True)
        if len(weighted) == 1 or weighted[1][0] <= weighted[0][0] - MAIN_READING_LEAD:
            moving.add((weighted[0][1], char))
    estimates = {}
    for pinyin, items in readings.items():
        for _index, char in items:
            source = to_simplified.convert(char) if to_simplified else char
            estimates[(pinyin, char)] = usage.get(source, 0.0)
    for (pinyin, char), (other_pinyin, other), _margin in SINGLE_CHAR_RELATIVE_ORDER_OVERRIDES:
        if pinyin == other_pinyin and (pinyin, char) in estimates and (pinyin, other) in estimates and \
                estimates[(pinyin, char)] <= estimates[(pinyin, other)]:
            estimates[(pinyin, char)] = estimates[(pinyin, other)] * 1.000001 + 1e-9
    weights_now = {(pinyin, char): weight for _index, pinyin, char, weight in rows}

    def order_of(pinyin: str) -> list[str]:
        # The validator's order, and the dictionary's: weight, then text.
        return sorted((char for _index, char in readings[pinyin]),
                      key=lambda char: (-weights_now[(pinyin, char)], char))

    # The audited order raises a character to 16 above its competitor, which
    # changes the weights a reading has, and a sampled rank lifts a character's
    # estimate to that of the moving character at its place: order, raise and
    # lift again until nothing changes, so that a rebuild that keeps these
    # weights and raises again finds nothing to do.
    unmet = []
    for _round in range(100):
        before = dict(weights_now)
        for pinyin, items in readings.items():
            movers = [(index, char) for index, char in items if (pinyin, char) in moving]
            if len(movers) < 2:
                continue
            # Equal estimates (none at all, or a shared simplified form) keep
            # the present order.
            order = sorted(movers, key=lambda item: (-estimates[(pinyin, item[1])],
                                                      -weights_now[(pinyin, item[1])], item[0]))
            values = sorted((weights_now[(pinyin, char)] for _index, char in movers), reverse=True)
            for (_index, char), value in zip(order, values):
                weights_now[(pinyin, char)] = value
        _enforce_single_char_relative_order_overrides(weights_now, "single_char_frequency")
        lifted = False
        unmet = []
        for pinyin, wanted in samples.items():
            if pinyin not in readings:
                continue
            order = order_of(pinyin)
            for char, max_rank in wanted:
                if char not in order or order.index(char) < max_rank:
                    continue
                # Above the lowest moving character within the rank that
                # weighs more: one of equal weight stays above it by its text.
                above = [other for other in order[:max_rank] if (pinyin, other) in moving
                         and weights_now[(pinyin, other)] > weights_now[(pinyin, char)]]
                if (pinyin, char) not in moving or not above:
                    unmet.append(f"{pinyin} {char} {order.index(char) + 1} > {max_rank}")
                    continue
                estimates[(pinyin, char)] = estimates[(pinyin, above[-1])] * 1.000001 + 1e-9
                lifted = True
        if weights_now == before and not lifted:
            break
    else:
        raise SystemExit("the order did not settle")
    changed = 0
    report = []
    for index, pinyin, char, old in rows:
        new = weights_now[(pinyin, char)]
        if new != old:
            fields = lines[index].split("\t")
            fields[2] = str(new)
            lines[index] = "\t".join(fields)
            changed += 1
        report.append((pinyin, char, old, new, round(estimates[(pinyin, char)], 3), int((pinyin, char) in moving)))
    args.unihan.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    if args.report:
        with args.report.open("w", encoding="utf-8", newline="\n") as out:
            out.write("pinyin\tchar\told\tnew\tuse\tmoving\n")
            for row in report:
                out.write("\t".join(map(str, row)) + "\n")
    print(f"{args.unihan.name}: {changed} of {len(rows)} single-character weights changed"
          + (f"; samples not met: {', '.join(unmet)}" if unmet else ""))


if __name__ == "__main__":
    main()
