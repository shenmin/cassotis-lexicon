#!/usr/bin/env python3
"""Prepare conservative, add-only professional coverage from a pinned THUOCL.

This is an offline admission tool, not frequency training. Normal dictionary
builds consume its checked-in TSV and need neither network nor these packages.
Dependencies: pypinyin==0.51.0, opencc-python-reimplemented==0.1.7.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import importlib.metadata
import io
import json
from pathlib import Path
import re
import urllib.request
import zipfile

import build_external_cedict as builder

COMMIT = "a30ce79d895d01ab5132a5c74c29703ff7efb4cc"
ARCHIVE_SHA256 = "0c710aeaf9b75b345c944c3c4f625bb4c8135ee97518dc5be5f444bf5ed1f89b"
URL = "https://codeload.github.com/thunlp/THUOCL/zip/" + COMMIT
CATEGORIES = ("IT", "animal", "caijing", "car", "food", "law", "medical")
OUTPUT = "manifests/vertical/thuocl_specialist_admissions.tsv"
FRAGMENT_PREFIXES = (
    "我们", "你们", "他们", "这些", "那些", "对于", "由于", "如何", "关于",
    "按照", "根据", "本公司", "可以通过", "主要用于", "经研究", "例如", "所谓的",
    "各种", "这些", "这个", "那个", "那些",
)
FRAGMENT_ENDINGS = tuple("的了着及与或和但则而这那其把将")
ANIMAL_ENDINGS = tuple(
    "牛羊猪鸡鸭鹅犬猫马驴虾蟹贝蛙鱼鹿蜂蚕蛾龟鸟鸽虎狮豹狼象鲸豚鲨鼠兔猴猿"
    "鲵蚌螺虫蚊蝇蚁蝉蝶蝠鹿熊獾貂狸狐獭驼驯鲟鳗鳝鲷鲈鲤鳅鲫鲶鳊鳙鳜"
    "鹤鸥鹭鸬鹚鹎鸫莺鹀雀雁鹰隼鹞鸮鹮鹳鹇鹑鸵鸸鸨鸊鷉鸠鸦鹊啄木鸟"
    "螈蜥蟒蛇鳄鼬鼩鼹螨虱蜱蠊蝎蜈蚣蜘蛛螽蟋蟀蝗螂蜻蜓蝽螟蝤蛸魟鮰鳐"
) + ("动物", "昆虫", "金龟", "叶甲", "步甲", "天牛", "长臂猿", "大猩猩", "海参", "海星", "水母", "珊瑚", "梗", "科", "亚科", "属", "亚属", "亚种")
FICTION_MARKERS = ("魔法", "恶魔", "地狱", "精灵", "女妖", "神龙", "史莱姆", "哥布林", "宝可梦", "数码宝贝", "皮卡丘", "奥特曼", "海贼", "火影", "魔兽", "圣斗士")
FINANCE_MARKERS = tuple("税财股贷债券资金汇款账帐价费率购售险产付") + (
    "银行", "证券", "期货", "风险", "商业", "市场", "结算", "信托", "贴现",
    "经济", "通胀", "预算", "会计", "成本", "收益", "利润", "亏损", "清盘", "审计",
)
# Audited source errors, not benchmark-dependent exclusions. Keep the upstream
# source intact; corrections must be admitted separately with verified spelling.
SOURCE_ERRORS = {"操作体统", "地盘测功机", "纳米比亚沙漠测行蛇", "工作使用"}


def rejection_reason(text: str, category: str) -> str:
    if not re.fullmatch(r"[\u4e00-\u9fff]{3,10}", text):
        return "length_or_script"
    if builder._is_explicit_multi_char_drop_text(text):
        return "lexical_exclusion"
    if text in SOURCE_ERRORS:
        return "source_error"
    if text.startswith(FRAGMENT_PREFIXES) or text.endswith(FRAGMENT_ENDINGS):
        return "fragment"
    if text.endswith(("有限公司", "集团公司", "公司网站", "官方网站")) and text not in {
        "有限责任公司", "股份有限公司", "一人有限公司", "国有独资公司",
    }:
        return "organization_label"
    if category == "caijing" and not any(marker in text for marker in FINANCE_MARKERS):
        return "finance_domain_mismatch"
    if category == "law" and text.endswith(("新编", "全书", "指南", "解答", "面面观", "研究", "辞典", "手册", "教程", "选编", "杂志", "学刊")):
        return "publication_title"
    if category == "animal":
        if any(marker in text for marker in FICTION_MARKERS):
            return "fiction_label"
        if not text.endswith(ANIMAL_ENDINGS):
            return "animal_domain_mismatch"
    return ""


def load_rows(path: Path):
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip() and not line.startswith("#"):
                yield line.rstrip("\r\n").split("\t")


def prepare(root: Path, archive: bytes):
    import pypinyin
    from pypinyin import Style, pinyin
    from opencc import OpenCC
    if pypinyin.__version__ != "0.51.0":
        raise RuntimeError("Use pypinyin==0.51.0 for reproducible phrase readings")
    if importlib.metadata.version("opencc-python-reimplemented") != "0.1.7":
        raise RuntimeError("Use opencc-python-reimplemented==0.1.7 for reproducible conversion")
    if hashlib.sha256(archive).hexdigest() != ARCHIVE_SHA256:
        raise ValueError("THUOCL archive checksum mismatch")
    converter = OpenCC("s2t")
    existing = {row[1] for row in load_rows(root / "data/generated/dict_clean_sc.txt")}
    output = root / OUTPUT
    # Permit regeneration after the previously admitted delta was built.
    if output.exists():
        existing.difference_update(row[0] for row in load_rows(output))
    reviewed = {row[0] for row in load_rows(root / "manifests/vertical/thuocl_reviewed_animals.tsv")}
    readings = []
    for variant in ("sc", "tc"):
        table = defaultdict(set)
        for row in load_rows(root / f"data/generated/dict_unihan_{variant}.txt"):
            table[row[1]].add(row[0])
        readings.append(table)
    counts = {category: Counter() for category in CATEGORIES}
    raw = defaultdict(dict)
    rejected = []
    with zipfile.ZipFile(io.BytesIO(archive)) as source:
        for category in CATEGORIES:
            member = next(n for n in source.namelist() if n.endswith(f"/data/THUOCL_{category}.txt"))
            for line in source.read(member).decode("utf-8-sig").splitlines():
                counts[category]["input"] += 1
                match = re.fullmatch(r"(.+?)\s+(\d+)", line.strip())
                if not match:
                    counts[category]["malformed"] += 1
                    continue
                word, df = match[1], int(match[2])
                reason = rejection_reason(word, category)
                if reason:
                    counts[category][reason] += 1
                    rejected.append((category, word, reason))
                elif word in existing or word in reviewed:
                    counts[category]["already_covered"] += 1
                else:
                    raw[word][category] = max(raw[word].get(category, 0), df)
    admitted = []
    for word, evidence in sorted(raw.items()):
        tc = converter.convert(word)
        syllables = [row[0] for row in pinyin(word, style=Style.NORMAL, heteronym=False, errors=lambda _: [""])]
        compact = "".join(syllables)
        reason = ""
        if len(tc) != len(word) or len(syllables) != len(word):
            reason = "script_or_reading_length"
        elif any(py not in readings[i].get(ch, ()) for i, text in enumerate((word, tc)) for ch, py in zip(text, syllables)):
            reason = "unverified_character_reading"
        elif builder._runtime_parse_compact_pinyin(compact) != syllables:
            # Do not guess around an ambiguous boundary or create an untested
            # compact alias. These rows remain in the review report.
            reason = "ambiguous_pinyin_boundary"
        if reason:
            for category in evidence:
                counts[category][reason] += 1
                rejected.append((category, word, reason))
            continue
        for category in evidence:
            counts[category]["admitted"] += 1
        # Deliberately independent of DF: a technical catalogue is not a
        # general corpus. Long terms receive less predictive influence.
        weight = 40 if len(word) <= 4 else 20
        admitted.append((word, tc, weight / 1000, compact, evidence))
    entries = [(sc, tc, usage, py, "specialist_terms", "thuocl-specialist-admissions")
               for sc, tc, usage, py, _ in admitted]
    builder._inject_specialist_exact_entries({}, {}, entries)
    return admitted, counts, rejected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    cache = root / "data/cache" / f"THUOCL-{COMMIT}.zip"
    if not cache.exists():
        if not args.download:
            raise FileNotFoundError("Pinned archive missing; rerun with --download")
        archive = urllib.request.urlopen(URL, timeout=60).read()
        if hashlib.sha256(archive).hexdigest() != ARCHIVE_SHA256:
            raise ValueError("Downloaded archive checksum mismatch")
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(archive)
    admitted, counts, rejected = prepare(root, cache.read_bytes())
    lines = ["# sc\ttc\tusage_score\tpinyin\tcategory:upstream_DF",
             f"# Generated by scripts/prepare_thuocl_specialists.py; THUOCL {COMMIT}.",
             "# Copyright (c) 2018 THUNLP. MIT: attribution/THUOCL-LICENSE.txt",
             "# Source membership is admission evidence, NOT general frequency or a transition."]
    lines.extend(f"{sc}\t{tc}\t{usage:.3f}\t{py}\t" + ";".join(f"{c}:{df}" for c, df in sorted(evidence.items()))
                 for sc, tc, usage, py, evidence in admitted)
    (root / OUTPUT).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    report = {"source_commit": COMMIT, "archive_sha256": ARCHIVE_SHA256,
              "pypinyin_version": "0.51.0", "opencc_version": "0.1.7",
              "entries": len(admitted), "categories": counts}
    (root / "reports/thuocl_specialist_admissions.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    review = root / "data/cache/thuocl_specialist_review.tsv"
    review.write_text("category\ttext\treason\n" + "\n".join("\t".join(r) for r in rejected) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
