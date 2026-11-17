#!/usr/bin/env python3
"""Order the traditional single characters that share one simplified form by
how traditional text writes them.

build_single_char_frequency.py gives a traditional character the counts of its
simplified form, and the character LM reads the traditional variant through
its simplified characters as well (nc_char_lm_traditional). Where two
characters of one reading have one simplified form (里 and 裡 under li, 后 and
後 under hou, 于 and 於 under yu), neither tells them apart: the weights alone
decide, with a context as well, and they were the order the sources gave. 里
stood above 裡, 后 above 後, 証 above 證, and forms Taiwan does not write
(産, 説, 喫, 眞) second under their readings.

manifests/traditional_char_shares.tsv holds, for each such simplified
character, how the general text the LM was trained on writes it once converted
by OpenCC s2tw in its sentence (scripts/count_traditional_char_shares.py):
the occurrences inside a word and those standing alone. A character's share of
its simplified form's use is the geometric mean of its occurrences and of
those standing alone, as build_single_char_frequency.py weighs the general
text, over the sum of those of its form. A form the conversion never writes
has no share.

OpenCC writes a character alone by its first form, and for some forms that is
not how they stand alone (SHARED_FORM_KEEPS): a surname (范, 岳, 朴 alone
became 範, 嶽, 樸), the everyday sense (托着 became 託著, 签个字 籤個字), or
Taiwan's everyday form (台, which s2tw writes 臺 throughout). Their characters
keep their places.

Only the characters of such forms move, and only under their main reading
(the rule of build_single_char_frequency.py). Two characters have no main
reading by that rule and are ordered under one by hand (MAIN_READING_BY_HAND):
系 under xi, where 繫 had stood above it, and 辟 under pi, where it had stood
above 闢. Of the forms of one simplified character under a reading, the one
traditional text writes most takes the place of the one that stood highest;
each other goes below it, above the
first character it is used more than (its share of the form's use against the
other characters' use, as build_single_char_frequency.py estimates it), and a
form the conversion never writes goes below every character the text holds.
The reading's other characters keep their order and their weights: the counts
have moved since the single characters were ordered (2026-10-27), and this
step leaves that order as it is. The character written most takes the weight
of the one that stood highest, and each lowered one a weight between the
characters it now stands between (its own where that fits). Lowered forms go
by their use among themselves (乾 above 干 under gan). A lowered form may leave
the first 16 characters of its reading, which the engine's LM orders with a
context (隻 of zhi): kept among them, such forms took the places of characters
the LM tells apart (止, 致, 駐), and the converted character cases lost more
than the forms gained, since the LM reads them as their simplified form and
puts them behind it at best. The engine orders such a form with the 16 all
the same where one of them is the other Taiwan form of its simplified
character (order_single_chars_by_lm, since 2026-11-17); a form Taiwan does not
write (裏, 説) stays where this step put it. The audited order of
SINGLE_CHAR_RELATIVE_ORDER_OVERRIDES and the ranks of the regression samples
must still hold; the script stops where they would not.

usage: order_traditional_shared_chars.py --char-counts manifests/general_char_counts.tsv
           --word-counts manifests/general_word_counts.tsv --chat-counts <counts>
           --shares manifests/traditional_char_shares.tsv
           --samples manifests/regression_samples.tc.tsv
           --unihan data/generated/dict_unihan_tc.txt [--report report.tsv]
"""

from __future__ import annotations

import argparse
import collections
import pathlib
import sys

import opencc

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from build_external_cedict import SINGLE_CHAR_RELATIVE_ORDER_OVERRIDES  # noqa: E402
from build_single_char_frequency import MAIN_READING_LEAD, single_char_samples, use_rates  # noqa: E402

# Simplified forms whose characters keep their places: OpenCC's form of the
# character standing alone is not how traditional text writes it there.
SHARED_FORM_KEEPS = {
    "范": "a surname alone; s2tw writes 範",
    "岳": "a surname alone; s2tw writes 嶽",
    "朴": "a surname alone; s2tw writes 樸",
    "台": "Taiwan writes 台 (舞台, 台灣); s2tw writes 臺 throughout",
    "托": "the verb alone is 托 (托著); s2tw writes 託",
    "签": "the verb alone is 簽 (簽個字); s2tw writes 籤",
}

# Characters whose readings weigh too nearly alike for a main reading, ordered
# under this one as if it were theirs (the user, 2026-11-17).
MAIN_READING_BY_HAND = {
    ("xi", "系"): "ji 473 as xi 473; xi in 系統, 系列, 體系, ji only in 系鞋帶, which traditional text writes 繫",
    ("pi", "辟"): "pi 374 against bi 365; under pi traditional text writes 開闢, 精闢, 闢謠",
}


def read_shares(path: pathlib.Path) -> dict[str, dict[str, float]]:
    """The use of each traditional form of a simplified character, as a share of the form's."""
    rates: dict[str, dict[str, float]] = collections.defaultdict(dict)
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#") or line.startswith("simplified\t"):
            continue
        simplified, traditional, inside, alone = line.split("\t")
        rates[simplified][traditional] = ((int(inside) + int(alone)) * int(alone)) ** 0.5
    shares = {}
    for simplified, forms in rates.items():
        total = sum(forms.values())
        if total > 0:
            shares[simplified] = {char: rate / total for char, rate in forms.items()}
    return shares


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--char-counts", required=True, type=pathlib.Path)
    parser.add_argument("--word-counts", required=True, type=pathlib.Path)
    parser.add_argument("--chat-counts", type=pathlib.Path)
    parser.add_argument("--chat-weight", type=float, default=3.0)
    parser.add_argument("--shares", required=True, type=pathlib.Path)
    parser.add_argument("--samples", type=pathlib.Path)
    parser.add_argument("--unihan", required=True, type=pathlib.Path)
    parser.add_argument("--report", type=pathlib.Path)
    args = parser.parse_args()

    usage = use_rates(args.char_counts, args.word_counts, args.chat_counts, args.chat_weight)
    shares = read_shares(args.shares)
    to_simplified = opencc.OpenCC("tw2s")
    lines = args.unihan.read_text(encoding="utf-8").splitlines()
    rows = []  # (line index, pinyin, char, weight)
    for index, line in enumerate(lines):
        fields = line.split("\t")
        if not line or line.startswith("#") or len(fields) < 3 or len(fields[1]) != 1:
            continue
        rows.append((index, fields[0], fields[1], int(fields[2])))
    source = {char: to_simplified.convert(char) for _index, _pinyin, char, _weight in rows}
    forms: dict[str, set[str]] = collections.defaultdict(set)
    for char, simplified in source.items():
        forms[simplified].add(char)
    shared = {simplified for simplified, chars in forms.items()
              if len(chars) > 1 and simplified in shares and simplified not in SHARED_FORM_KEEPS}
    main_form = {simplified: max(sorted(shares[simplified]), key=lambda char: shares[simplified][char])
                 for simplified in shared}

    by_char: dict[str, list[tuple[int, str]]] = collections.defaultdict(list)
    for _index, pinyin, char, weight in rows:
        by_char[char].append((weight, pinyin))
    moving: set[tuple[str, str]] = set()
    for char, weighted in by_char.items():
        weighted.sort(reverse=True)
        if len(weighted) == 1 or weighted[1][0] <= weighted[0][0] - MAIN_READING_LEAD:
            moving.add((weighted[0][1], char))
    moving.update(MAIN_READING_BY_HAND)

    def estimate(char: str) -> float:
        simplified = source[char]
        use = usage.get(simplified, 0.0)
        return use * shares[simplified].get(char, 0.0) if simplified in shared else use

    weights = {(pinyin, char): weight for _index, pinyin, char, weight in rows}
    readings: dict[str, list[str]] = collections.defaultdict(list)
    for _index, pinyin, char, _weight in rows:
        readings[pinyin].append(char)
    report = []
    ties: list[str] = []  # lowered characters left with no room between their neighbours' weights
    for pinyin, chars in readings.items():
        movers = sorted((char for char in chars if (pinyin, char) in moving),
                        key=lambda char: (-weights[(pinyin, char)], char))
        groups: dict[str, list[str]] = collections.defaultdict(list)
        for char in movers:
            if source[char] in shared:
                groups[source[char]].append(char)
        if not groups:
            continue
        # The form traditional text writes most takes the place of the form
        # that stood highest; the reading's other characters keep theirs.
        leaders = {}  # the form's highest character -> the form's character traditional text writes most
        for simplified, members in groups.items():
            if len(members) > 1:
                leaders[members[0]] = max(members, key=lambda char: (shares[simplified].get(char, 0.0),
                                                                     -movers.index(char)))
        leader_of = {source[top]: leader for top, leader in leaders.items()}
        # Alone under the reading, the form's main character stays where it is.
        lowered = [char for char in movers if source[char] in shared and
                   leader_of.get(source[char], main_form[source[char]]) != char]
        placed = set(leaders.values())
        order = [leaders.get(char, char) for char in movers
                 if char in leaders or (char not in lowered and char not in placed)]
        # Every other character of such a form only goes down: from where it
        # stood (and below its form's leader), above the first character it is
        # used more than; one the text never writes below every character the
        # text holds.
        lowered_set = set(lowered)
        for char in sorted(lowered, key=movers.index):
            value = estimate(char)
            # Lowered characters go by their use among themselves (乾 above 干).
            above = [other for other in movers[:movers.index(char)] if other in order and other not in lowered_set]
            start = order.index(above[-1]) + 1 if above else 0
            if source[char] in leader_of:
                start = max(start, order.index(leader_of[source[char]]) + 1)
            if value > 0.0:
                at = next((i for i in range(start, len(order)) if estimate(order[i]) < value), len(order))
            else:
                at = max([start] + [i + 1 for i in range(start, len(order)) if estimate(order[i]) > 0.0])
            order.insert(at, char)
        # Only the forms' characters take new weights: the leader the weight of
        # the form's highest character, and each lowered one a weight between
        # the characters it now stands between (its own where that fits).
        # Every other character keeps its weight, so nothing else crosses a
        # character that does not move (伺 of si, placed by hand).
        new = {leader: weights[(pinyin, top)] for top, leader in leaders.items() if leader != top}
        i = 0
        while i < len(order):
            if order[i] not in lowered_set:
                i += 1
                continue
            j = i
            while j < len(order) and order[j] in lowered_set:
                j += 1
            run = order[i:j]
            old = [weights[(pinyin, char)] for char in run]
            upper = new.get(order[i - 1], weights[(pinyin, order[i - 1])]) if i > 0 else None
            lower = new.get(order[j], weights[(pinyin, order[j])]) if j < len(order) else 0
            sequence = ([upper] if upper is not None else []) + old + [lower]
            if all(a > b for a, b in zip(sequence, sequence[1:])):
                values = old
            else:
                high = upper if upper is not None else max(old[0], lower + len(run)) + 1
                if high - lower - 1 >= len(run):
                    values = [high - round((n + 1) * (high - lower) / (len(run) + 1)) for n in range(len(run))]
                else:
                    values = [max(lower, high - 1 - n, 1) for n in range(len(run))]
                    ties.extend(f"{pinyin} {char}" for char, value in zip(run, values) if value <= lower)
            new.update(zip(run, values))
            i = j
        for char, value in new.items():
            if weights[(pinyin, char)] != value:
                report.append((pinyin, char, weights[(pinyin, char)], value, round(estimate(char), 3)))
                weights[(pinyin, char)] = value

    def order_of(pinyin: str) -> list[str]:
        return sorted(readings[pinyin], key=lambda char: (-weights[(pinyin, char)], char))

    broken = []
    for (pinyin, char), (other_pinyin, other), _margin in SINGLE_CHAR_RELATIVE_ORDER_OVERRIDES:
        if pinyin == other_pinyin and (pinyin, char) in weights and (pinyin, other) in weights and \
                weights[(pinyin, char)] <= weights[(pinyin, other)]:
            broken.append(f"{pinyin} {char} under {other}")
    for pinyin, wanted in single_char_samples(args.samples).items():
        if pinyin in readings:
            order = order_of(pinyin)
            for char, max_rank in wanted:
                if char in order and order.index(char) >= max_rank:
                    broken.append(f"{pinyin} {char} {order.index(char) + 1} > {max_rank}")
    if broken:
        raise SystemExit("the order would break: " + ", ".join(broken))
    for index, pinyin, char, _old in rows:
        fields = lines[index].split("\t")
        fields[2] = str(weights[(pinyin, char)])
        lines[index] = "\t".join(fields)
    args.unihan.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    if args.report:
        with args.report.open("w", encoding="utf-8", newline="\n") as out:
            out.write("pinyin\tchar\told\tnew\testimate\n")
            for row in report:
                out.write("\t".join(map(str, row)) + "\n")
    print(f"{args.unihan.name}: {len(report)} of {len(rows)} single-character weights changed, "
          f"{len(shared)} shared forms ordered, {len(SHARED_FORM_KEEPS)} kept, "
          f"{len(ties)} tied with the character below")


if __name__ == "__main__":
    main()
