"""Writes the generated traditional files in Taiwan's forms
(manifests/traditional_taiwan_forms.tsv: 爲 -> 為, 裏 -> 裡, 着 -> 著,
綫 -> 線, 説 -> 說). The sources and OpenCC's standard gave the dictionary
both (因為 beside 爲了, 這裡 beside 這裏, 喫飯 and 羣眾 beside 吃了 and 觀眾).

Every word of two characters or more, and every segment of a path, takes the
forms; a single character stays as it is, so that a variant can still be
typed on purpose. Where a word then meets its twin, the two rows become one:
the dictionaries keep the higher weight, the completion prior and lookup the
row with the higher popularity or weight, the paths the higher weight.

The character n-gram models were counted on text in OpenCC's forms (眼裏,
纔是): left as they were, Taiwan's words scored low there and the short
promotion put 嚴厲 above 眼裡 and 菜市 above 才是. Their n-grams take the
forms character by character, single ones too; where both forms were
counted, the probabilities add (scores are 1000 times the natural log) and
the backoff is the more probable one's.

A second run changes nothing. rebuild_all.ps1 runs it after the builds; it
can run on the generated files alone.
usage: normalize_traditional_forms.py [--root <lexicon root>]"""
import argparse
import collections
import math
from pathlib import Path

MANIFEST = "manifests/traditional_taiwan_forms.tsv"


def load_forms(path):
    forms = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        source, target, _ = line.split("\t")
        if len(source) != 1 or len(target) != 1 or source in forms:
            raise ValueError(f"Invalid Taiwan form row: {line}")
        forms[source] = target
    return forms


def normalize_text(text, forms):
    """A word of two characters or more in Taiwan's forms."""
    if len(text) < 2:
        return text
    return "".join(forms.get(ch, ch) for ch in text)


_FORMS = None


def taiwan_text(text):
    """normalize_text with the manifest's forms: what the generated
    traditional files hold for a text of the builder or a manifest."""
    global _FORMS
    if _FORMS is None:
        _FORMS = load_forms(Path(__file__).resolve().parents[1] / MANIFEST)
    return normalize_text(text, _FORMS)


def taiwan_path(path):
    """normalize_path with the manifest's forms."""
    taiwan_text("")
    return normalize_path(path, _FORMS)


def normalize_path(path, forms):
    """Every segment of a path of several characters."""
    if len(path.replace("|", "")) < 2:
        return path
    return "|".join("".join(forms.get(ch, ch) for ch in part) for part in path.split("|"))


def number(text):
    try:
        return int(text)
    except ValueError:
        return 0


class Table:
    """A generated file: comment lines kept in place, rows merged by key."""

    def __init__(self, path):
        self.path = path
        with open(path, encoding="utf-8", newline="") as stream:
            self.text = stream.read()
        self.newline = "\r\n" if "\r\n" in self.text else "\n"
        self.lines = self.text.split(self.newline)

    def rewrite(self, columns, convert, merge_key, better, stats):
        # Only a row that took a form merges with its twin; rows alike
        # before stay as they were.
        rows = {}
        slots = {}
        order = []
        for index, line in enumerate(self.lines):
            fields = line.split("\t")
            if line.startswith("#") or len(fields) < columns:
                order.append(("line", line))
                continue
            converted = convert(list(fields))
            changed = converted != fields
            if changed:
                stats[self.path.name + " rewritten"] += 1
            row_key = merge_key(converted)
            if row_key in slots and (changed or rows[slots[row_key]][1]):
                stats[self.path.name + " merged"] += 1
                slot = slots[row_key]
                if better(converted, rows[slot][0]):
                    rows[slot] = (converted, True)
                continue
            rows[index] = (converted, changed)
            slots.setdefault(row_key, index)
            order.append(("row", index))
        result = self.newline.join("\t".join(rows[item][0]) if kind == "row" else item for kind, item in order)
        if result != self.text:
            with open(self.path, "w", encoding="utf-8", newline="") as stream:
                stream.write(result)


def normalize_single_characters(paths, forms, stats):
    """A single character keeps its variant, but Taiwan's form comes first:
    the Unihan inventory held only 喫, 羣, 牀, 祕 (no 吃, 群, 床, 秘), and
    with the words and n-grams in Taiwan's forms a sentence built from the
    single character lost it (相當喫力 became 尺力). Taiwan's form gets the
    variant's reading and at least its weight, added beside it where it was
    missing; the variant goes one below."""
    tables = [Table(path) for path in paths]
    weights = {}
    for table in tables:
        for line in table.lines:
            fields = line.split("\t")
            if not line.startswith("#") and len(fields) >= 3 and len(fields[1]) == 1:
                weights[(fields[0], fields[1])] = max(weights.get((fields[0], fields[1]), 0), number(fields[2]))
    wanted = {}
    for (pinyin, text), weight in weights.items():
        if text in forms:
            target = (pinyin, forms[text])
            wanted[target] = max(wanted.get(target, 0), weight)
    present = {key for key in weights if key in wanted}
    for table in tables:
        out = []
        for line in table.lines:
            fields = line.split("\t")
            if line.startswith("#") or len(fields) < 3 or len(fields[1]) != 1:
                out.append(line)
                continue
            key_ = (fields[0], fields[1])
            if key_ in wanted and number(fields[2]) < wanted[key_]:
                fields[2] = str(wanted[key_])
                stats[table.path.name + " single raised"] += 1
            if fields[1] in forms:
                target = (fields[0], forms[fields[1]])
                ceiling = max(1, max(wanted[target], weights.get(target, 0)) - 1)
                if number(fields[2]) > ceiling:
                    fields[2] = str(ceiling)
                    stats[table.path.name + " single variant lowered"] += 1
                out.append("\t".join(fields))
                if target not in present:
                    present.add(target)
                    out.append("\t".join([target[0], target[1], str(wanted[target])] + fields[3:]))
                    stats[table.path.name + " single added"] += 1
                continue
            out.append("\t".join(fields))
        result = table.newline.join(out)
        if result != table.text:
            with open(table.path, "w", encoding="utf-8", newline="") as stream:
                stream.write(result)


def normalize_ngrams(path, forms, stats):
    """A character n-gram model (ngram, score, backoff): every character in
    Taiwan's form; two n-grams that become one add their probabilities."""
    table = Table(path)
    entries = {}
    order = []
    for index, line in enumerate(table.lines):
        fields = line.split("\t")
        if index == 0 or len(fields) < 3 or not fields[1].lstrip("-").isdigit():
            order.append(("line", line))
            continue
        gram = "".join(forms.get(ch, ch) for ch in fields[0])
        changed = gram != fields[0]
        if changed:
            stats[path.name + " rewritten"] += 1
        score, backoff = int(fields[1]), fields[2]
        if gram in entries and (changed or entries[gram][2]):
            stats[path.name + " merged"] += 1
            old_score, old_backoff, _ = entries[gram]
            high = max(score, old_score)
            total = high + round(1000 * math.log(math.exp((score - high) / 1000) +
                                                 math.exp((old_score - high) / 1000)))
            entries[gram] = (total, backoff if score > old_score else old_backoff, True)
            continue
        entries[gram] = (score, backoff, changed)
        order.append(("row", gram))
    result = table.newline.join(f"{item}\t{entries[item][0]}\t{entries[item][1]}" if kind == "row" else item
                                for kind, item in order)
    if result != table.text:
        with open(path, "w", encoding="utf-8", newline="") as stream:
            stream.write(result)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()
    root = Path(args.root)
    forms = load_forms(root / MANIFEST)
    generated = root / "data/generated"
    stats = collections.Counter()

    def text_columns(*cols):
        def convert(fields):
            for col in cols:
                fields[col] = normalize_text(fields[col], forms)
            return fields
        return convert

    def path_columns(text_cols, path_cols):
        def convert(fields):
            for col in text_cols:
                fields[col] = normalize_text(fields[col], forms)
            for col in path_cols:
                fields[col] = normalize_path(fields[col], forms)
            return fields
        return convert

    def heavier(col):
        return lambda new, old: number(new[col]) > number(old[col])

    for name in ("dict_clean_tc.txt", "dict_unihan_tc.txt"):
        Table(generated / name).rewrite(3, text_columns(1), lambda f: (f[0], f[1]), heavier(2), stats)
    Table(generated / "dict_completion_prior_tc.txt").rewrite(
        3, text_columns(1), lambda f: (f[0], f[1]), heavier(2), stats)
    Table(generated / "dict_completion_lookup_tc.txt").rewrite(
        4, text_columns(2), lambda f: (f[0], f[1], f[2]), heavier(3), stats)
    Table(generated / "dict_completion_competition_tc.txt").rewrite(
        5, text_columns(4), lambda f: tuple(f[:5]), lambda new, old: False, stats)
    Table(generated / "dict_completion_pair_audit_tc.txt").rewrite(
        7, text_columns(4, 6), lambda f: tuple(f[:7]), lambda new, old: False, stats)
    Table(generated / "dict_transition_completion_tc.txt").rewrite(
        5, path_columns([2], [3]), lambda f: tuple(f[:4]), heavier(4), stats)
    Table(generated / "dict_long_completion_tc.txt").rewrite(
        5, path_columns([0, 2], [3]), lambda f: tuple(f[:4]), heavier(4), stats)
    for name in ("dict_lm_transition_tc.txt", "dict_query_path_prior_tc.txt"):
        Table(generated / name).rewrite(3, path_columns([], [1]), lambda f: (f[0], f[1]), heavier(2), stats)

    def promotion(fields):
        fields[1] = normalize_text(fields[1], forms)
        fields[2] = normalize_text(fields[2], forms)
        fields[4] = "|".join(normalize_text(item.rpartition(":")[0], forms) + ":" + item.rpartition(":")[2]
                             if ":" in item else item for item in fields[4].split("|"))
        return fields
    Table(generated / "dict_short_promotion_tc.txt").rewrite(
        5, promotion, lambda f: tuple(f[:3]), lambda new, old: False, stats)
    normalize_single_characters([generated / "dict_unihan_tc.txt", generated / "dict_clean_tc.txt"],
                                forms, stats)
    for name in ("dict_char_lm_tc.txt", "dict_char_reverse_lm_tc.txt"):
        normalize_ngrams(generated / name, forms, stats)
    for item, count in sorted(stats.items()):
        print(f"{item}: {count}")


if __name__ == "__main__":
    main()
