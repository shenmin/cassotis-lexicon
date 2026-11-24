#!/usr/bin/env python3
"""Write the Wubi 86 code table of the IME's Wubi/pinyin mixed scheme.

The table is Haifeng's (SUN Haifeng's Wubi 86 tables as packaged by
ibus-table-chinese, BSD-3-Clause; attribution/WUBI-HAIFENG-LICENSE.txt). It is
kept apart from the pinyin dictionary: the IME opens it only in the mixed
scheme, and nothing of the pinyin build reads it.

- Characters (GBK.tab): each character under its 86 full code and its level
  1 to 3 short codes. Haifeng's rank 1 characters (common GB2312 characters)
  stand before the words of their code, the others after them, each group by
  the table's character frequency.
- Words (Word.tab): under their 86 code, by the table's word frequency; rows
  the table marks for deletion are left out.
- A code Haifeng leaves empty takes, in this order: the characters whose 86
  tolerant code it is (GBK.tab's tolerant column; a tolerant code that lands
  on a code with entries is left out, so no entry moves), and then the
  dictionary's words that Haifeng lacks, coded by the word-code rule from
  Haifeng's full codes, at least --min-count occurrences in the general text
  (manifests/general_word_counts.tsv), most frequent first. The IME never lets
  such a word commit itself on a unique code of four keys.

Each row is code, text, kind, rank (1 for the code's first entry) and, for a
word, its score in the general text (100 * log10(1 + occurrences), as
build_word_frequency.py writes it; 0 for a character), which ranks the words a
code prefix begins for the IME's Wubi completion. The
source files are downloaded at a fixed commit into data/cache/wubi_haifeng86
and checked against their SHA-256. --cross-check reads fcitx's wbx table
(libime data, table.tar.zst) and reports how many full codes it shares.

usage: build_wubi86_table.py --counts manifests/general_word_counts.tsv
           --dictionary data/generated/dict_clean_sc.txt
           --output data/generated/wubi86_table.txt [--min-count 100]
           [--cache data/cache/wubi_haifeng86] [--cross-check wbx.txt]
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import math
import pathlib
import time
import urllib.request

COMMIT = "e0dd8bfdff9e0d2194c8e57f1ded606fb53e29c1"
BASE_URL = f"https://raw.githubusercontent.com/mike-fabian/ibus-table-chinese/{COMMIT}/tables/wubi-haifeng/"
SOURCES = {
    "GBK.tab": "c3e06bdadd0c540285a345f07d7a79bdafd2778eb6546514421ae393acdca153",
    "Word.tab": "b3c268864ba2eaf513c7e307ae2349dd0dedcc06588684ab8b1e0996e0eb92d1",
    "COPYING": "a37e41f7092e7669123fbe010b30d502ad89306e120ecc23a77b3a89f7502bf4",
}
KIND_FIRST_CHAR = 1
KIND_WORD = 2
KIND_CHAR = 3
KIND_TOLERANT = 4
KIND_LEXICON_WORD = 5
LETTERS = set("abcdefghijklmnopqrstuvwxy")


def fetch(cache: pathlib.Path) -> None:
    cache.mkdir(parents=True, exist_ok=True)
    for name, digest in SOURCES.items():
        path = cache / name
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            for attempt in range(5):
                try:
                    with urllib.request.urlopen(BASE_URL + name, timeout=60) as response:
                        data = response.read()
                    if hashlib.sha256(data).hexdigest() == digest:
                        path.write_bytes(data)
                        break
                except OSError:
                    pass
                time.sleep(2 + 3 * attempt)
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise SystemExit(f"{name}: SHA-256 does not match {digest}")


def valid_code(code: str) -> bool:
    return 1 <= len(code) <= 4 and set(code) <= LETTERS


def rule_code(word: str, full: dict[str, str]) -> str | None:
    codes = [full.get(ch) for ch in word]
    if len(word) < 2 or None in codes:
        return None
    if len(word) == 2:
        return codes[0][:2] + codes[1][:2]
    if len(word) == 3:
        return codes[0][:1] + codes[1][:1] + codes[2][:2]
    return codes[0][:1] + codes[1][:1] + codes[2][:1] + codes[-1][:1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--counts", required=True, type=pathlib.Path)
    parser.add_argument("--dictionary", required=True, type=pathlib.Path)
    parser.add_argument("--output", required=True, type=pathlib.Path)
    parser.add_argument("--min-count", type=int, default=100)
    parser.add_argument("--cache", type=pathlib.Path,
                        default=pathlib.Path(__file__).resolve().parent.parent / "data/cache/wubi_haifeng86")
    parser.add_argument("--cross-check", type=pathlib.Path)
    args = parser.parse_args()
    fetch(args.cache)

    # (code, text) -> (kind, -frequency); a text keeps its best kind under a code.
    rows: dict[tuple[str, str], tuple[int, float]] = {}
    full: dict[str, str] = {}
    tolerant: list[tuple[str, str, float]] = []
    for line in (args.cache / "GBK.tab").read_text(encoding="utf-8").splitlines():
        f = line.split("\t")
        if len(f) < 18 or not f[0].isdigit() or len(f[2]) != 1:
            continue
        ch = f[2]
        if ch in full or not valid_code(f[3]):
            continue
        full[ch] = f[3]
        try:
            freq = float(f[17].strip() or 0)
        except ValueError:
            freq = 0.0
        kind = KIND_FIRST_CHAR if f[4].strip() == "1" else KIND_CHAR
        for code in {f[3], *(s for s in f[5:8] if s != ".")}:
            if valid_code(code):
                rows[(code, ch)] = min(rows.get((code, ch), (9, 0.0)), (kind, -freq))
        if valid_code(f[8]) and f[8] != f[3]:
            tolerant.append((f[8], ch, freq))
    haifeng_words = set()
    for line in (args.cache / "Word.tab").read_text(encoding="utf-8").splitlines()[1:]:
        f = line.split("\t")
        if len(f) < 10 or f[7].strip() or len(f[0]) < 2 or not valid_code(f[2]):
            continue
        try:
            freq = float(f[5] or 0)
        except ValueError:
            freq = 0.0
        haifeng_words.add(f[0])
        rows[(f[2], f[0])] = min(rows.get((f[2], f[0]), (9, 0.0)), (KIND_WORD, -freq))

    taken = {code for code, _ in rows}
    added_tolerant = 0
    for code, ch, freq in tolerant:
        if code not in taken and (code, ch) not in rows:
            rows[(code, ch)] = (KIND_TOLERANT, -freq)
            added_tolerant += 1
    taken_with_tolerant = {code for code, _ in rows}

    counts = {}
    for line in args.counts.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            word, count = line.split("\t")
            counts[word] = int(count)
    dictionary_words = set()
    for line in args.dictionary.read_text(encoding="utf-8").splitlines():
        fields = line.split("\t")
        if len(fields) >= 3 and not line.startswith("#"):
            dictionary_words.add(fields[1])
    added_lexicon = 0
    for word in sorted(dictionary_words):
        count = counts.get(word, 0)
        if count < args.min_count or word in haifeng_words:
            continue
        code = rule_code(word, full)
        if code is None or code in taken_with_tolerant:
            continue
        rows[(code, word)] = (KIND_LEXICON_WORD, -float(count))
        added_lexicon += 1

    by_code: dict[str, list[tuple[tuple[int, float], str]]] = collections.defaultdict(list)
    for (code, text), key in rows.items():
        by_code[code].append((key, text))
    kinds = collections.Counter(k for k, _ in rows.values())
    with args.output.open("w", encoding="utf-8", newline="\n") as out:
        out.write("# code\ttext\tkind\trank\tscore\n")
        out.write(f"# Wubi 86 from SUN Haifeng's tables (ibus-table-chinese {COMMIT[:7]}, BSD-3-Clause; "
                  "attribution/WUBI-HAIFENG-LICENSE.txt), built by scripts/build_wubi86_table.py\n")
        out.write("# kind: 1 common character (before the words of its code), 2 word, 3 other character, "
                  "4 86 tolerant code on an empty code, 5 dictionary word by the word-code rule on an empty code "
                  f"(at least {args.min_count} occurrences in the general text); score: a word's "
                  "round(100 * log10(1 + occurrences as a word in the general text)), from "
                  "manifests/general_word_counts.tsv, 0 for a character\n")
        for code in sorted(by_code):
            for rank, (key, text) in enumerate(sorted(by_code[code], key=lambda x: (x[0], x[1])), 1):
                score = round(100.0 * math.log10(1 + counts.get(text, 0))) if len(text) >= 2 else 0
                out.write(f"{code}\t{text}\t{key[0]}\t{rank}\t{score}\n")
    print(f"{args.output}: {len(rows)} rows on {len(by_code)} codes; " +
          ", ".join(f"kind {k} {kinds[k]}" for k in sorted(kinds)) +
          f"; tolerant codes on empty codes {added_tolerant}, dictionary words on empty codes {added_lexicon}")

    if args.cross_check:
        wbx: dict[str, set[str]] = collections.defaultdict(set)
        data = False
        for line in args.cross_check.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("[数据]"):
                data = True
                continue
            if data and " " in line:
                code, text = line.split(" ", 1)
                if code.isalpha():
                    wbx[text].add(code)
        shared = [ch for ch in full if ch in wbx]
        same = [ch for ch in shared if full[ch] in wbx[ch]]
        print(f"cross-check: {len(shared)} characters in both, full code also in wbx for {len(same)}; "
              f"differing: {' '.join(ch for ch in shared if full[ch] not in wbx[ch] and ch < chr(0x9fa6))[:400]}")
        word_rows = [(code, text) for (code, text), key in rows.items() if key[0] == KIND_WORD and text in wbx]
        word_same = sum(code in wbx[text] for code, text in word_rows)
        print(f"cross-check: {len(word_rows)} words in both, same code {word_same}")


if __name__ == "__main__":
    main()
