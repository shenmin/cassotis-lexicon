#!/usr/bin/env python3
"""Count how traditional text writes each simplified character that stands for
two or more traditional single characters of the traditional dictionary
(OpenCC tw2s gives them one form: 里 for 里, 裡 and 裏; 后 for 后 and 後).

The general text the character LM was trained on is simplified. Each line
holding such a character is converted by OpenCC s2tw, which picks the form by
its phrases in the sentence, and each occurrence is counted under the form it
became: inside a word of the simplified dictionary (any word of two to eight
characters covering it) or standing alone. Reads the first --chars characters
of each input. Writes manifests/traditional_char_shares.tsv (counts only),
which order_traditional_shared_chars.py reads.

Made on 2026-11-16 from the first 30,000,000 characters of each of the three
general corpora (fineweb_edu_chinese_v21, ultra_fineweb_zh, wikipedia_zh).

usage: count_traditional_char_shares.py --dictionary-sc data/generated/dict_clean_sc.txt
           --unihan-tc data/generated/dict_unihan_tc.txt
           --input <text | archive.zip!member> [--input ...] [--chars 30000000]
           [--output manifests/traditional_char_shares.tsv]
"""

from __future__ import annotations

import argparse
import collections
import io
import pathlib
import zipfile

import opencc

MAX_WORD = 8


def open_input(spec: str):
    if "!" in spec:
        archive, member = spec.split("!", 1)
        return io.TextIOWrapper(zipfile.ZipFile(archive).open(member), encoding="utf-8", errors="replace")
    return open(spec, encoding="utf-8", errors="replace")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dictionary-sc", required=True, type=pathlib.Path)
    parser.add_argument("--unihan-tc", required=True, type=pathlib.Path)
    parser.add_argument("--input", required=True, action="append")
    parser.add_argument("--chars", type=int, default=30_000_000)
    parser.add_argument("--output", type=pathlib.Path, default=pathlib.Path("manifests/traditional_char_shares.tsv"))
    args = parser.parse_args()

    tw2s = opencc.OpenCC("tw2s")
    s2tw = opencc.OpenCC("s2tw")
    forms: dict[str, set[str]] = collections.defaultdict(set)
    for line in args.unihan_tc.read_text(encoding="utf-8").splitlines():
        fields = line.split("\t")
        if line and not line.startswith("#") and len(fields) >= 3 and len(fields[1]) == 1:
            forms[tw2s.convert(fields[1])].add(fields[1])
    targets = {simplified for simplified, chars in forms.items() if len(chars) > 1}
    words = set()
    for line in args.dictionary_sc.read_text(encoding="utf-8").splitlines():
        fields = line.split("\t")
        if len(fields) >= 2 and 2 <= len(fields[1]) <= MAX_WORD:
            words.add(fields[1])

    inside: collections.Counter[tuple[str, str]] = collections.Counter()
    alone: collections.Counter[tuple[str, str]] = collections.Counter()
    for spec in args.input:
        read = 0
        with open_input(spec) as text:
            for line in text:
                line = line.rstrip("\n")
                read += len(line)
                if read > args.chars:
                    break
                positions = [i for i, char in enumerate(line) if char in targets]
                if not positions:
                    continue
                converted = s2tw.convert(line)
                if len(converted) != len(line):
                    continue
                for i in positions:
                    covered = any(line[begin:begin + length] in words
                                  for length in range(2, MAX_WORD + 1)
                                  for begin in range(max(0, i - length + 1), min(i, len(line) - length) + 1))
                    (inside if covered else alone)[(line[i], converted[i])] += 1
        print(f"{spec}: {min(read, args.chars)} characters")

    with args.output.open("w", encoding="utf-8", newline="\n") as out:
        out.write("# How the general text writes each simplified character of two or more traditional single\n"
                  "# characters, converted by OpenCC s2tw in its sentence (scripts/count_traditional_char_shares.py):\n"
                  "# occurrences inside a word of the simplified dictionary and standing alone. Counts only.\n")
        out.write("simplified\ttraditional\tinside\talone\n")
        for key in sorted(set(inside) | set(alone)):
            out.write(f"{key[0]}\t{key[1]}\t{inside[key]}\t{alone[key]}\n")
    print(f"{args.output}: {len(set(inside) | set(alone))} rows, {len(targets)} simplified characters")


if __name__ == "__main__":
    main()
