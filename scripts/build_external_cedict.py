#!/usr/bin/env python3
"""
Build public lexicon seed files from external sources.

Output format:
  pinyin<TAB>text<TAB>weight
"""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import io
import json
import math
import pathlib
import re
import sys
import unicodedata
import urllib.request
import zipfile
from typing import Dict, List, Set, Tuple


CEDICT_DEFAULT_URL = (
    "https://www.mdbg.net/chinese/export/cedict/cedict_1_0_ts_utf-8_mdbg.txt.gz"
)
CEDICT_HOMEPAGE = "https://www.mdbg.net/chinese/dictionary?page=cc-cedict"

OPENCC_STPHRASES_URL = (
    "https://raw.githubusercontent.com/BYVoid/OpenCC/master/data/dictionary/STPhrases.txt"
)
OPENCC_HOMEPAGE = "https://github.com/BYVoid/OpenCC"

UNICODE_UNIHAN_URL = "https://www.unicode.org/Public/UCD/latest/ucd/Unihan.zip"
UNICODE_HOMEPAGE = "https://www.unicode.org/ucd/"
THUOCL_ZIP_URL = "https://github.com/thunlp/THUOCL/archive/refs/heads/master.zip"
THUOCL_HOMEPAGE = "https://github.com/thunlp/THUOCL"
JIEBA_DICT_URL = "https://raw.githubusercontent.com/fxsjy/jieba/master/jieba/dict.txt"
JIEBA_HOMEPAGE = "https://github.com/fxsjy/jieba"
ZHWIKI_TITLES_URL = "https://dumps.wikimedia.org/zhwiki/latest/zhwiki-latest-all-titles-in-ns0.gz"
ZHWIKI_HOMEPAGE = "https://dumps.wikimedia.org/zhwiki/latest/"
WIKIMEDIA_PAGEVIEWS_TOP_URL = "https://wikimedia.org/api/rest_v1/metrics/pageviews/top/zh.wikipedia/all-access"
WIKIMEDIA_PAGEVIEWS_TOP_HOMEPAGE = "https://wikitech.wikimedia.org/wiki/Analytics/AQS/Pageviews"
DEFAULT_PERMISSIVE_OVERRIDES = "manifests/pinyin_overrides.clean_permissive.tsv"
DEFAULT_HTTP_USER_AGENT = "cassotis-lexicon/1.0 (+https://github.com/shenmin/cassotis-lexicon)"

CEDICT_LINE_RE = re.compile(r"^(\S+)\s+(\S+)\s+\[([^\]]+)\]\s+/(.*)/$")
CJK_RE = re.compile("[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U0002A6DF]")
CJK_FULL_RE = re.compile(
    "^[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U0002A6DF]+$"
)
CJK_WINDOWS_FULL_RE = re.compile("^[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+$")
PINYIN_RE = re.compile(r"^[a-z]+$")
UNIHAN_SOURCE_HANYU_EXTRA = 1
UNIHAN_SOURCE_MANDARIN = 2
UNIHAN_SOURCE_PINLU = 3
UNIHAN_HANYU_EXTRA_WEIGHT_CAP = 160

COPYLEFT_LICENSE_TOKENS = (
    "by-sa",
    "gpl",
    "lgpl",
    "agpl",
    "gfdl",
    "copyleft",
)

PROFILE_DEFAULTS: Dict[str, Dict[str, object]] = {
    "external_cedict": {
        "parser": "cedict",
        "sources": [
            {
                "id": "cc-cedict",
                "name": "CC-CEDICT",
                "download_url": CEDICT_DEFAULT_URL,
                "homepage": CEDICT_HOMEPAGE,
                "license": "CC BY-SA 4.0",
                "risk_level": "medium",
                "redistribution_class": "copyleft_sharealike",
                "attribution_required": True,
                "raw_committed": False,
                "notes": "Parsed to pinyin<TAB>text<TAB>weight format.",
            }
        ],
    },
    "external_broad": {
        "parser": "cedict_thuocl_jieba_opencc_unihan_wiki",
        "sources": [
            {
                "id": "cc-cedict",
                "name": "CC-CEDICT",
                "download_url": CEDICT_DEFAULT_URL,
                "homepage": CEDICT_HOMEPAGE,
                "license": "CC BY-SA 4.0",
                "risk_level": "medium",
                "redistribution_class": "copyleft_sharealike",
                "attribution_required": True,
                "raw_committed": False,
                "notes": "Core dictionary entries with word-level pinyin.",
            },
            {
                "id": "thuocl",
                "name": "THUOCL (Tsinghua Open Chinese Lexicon)",
                "download_url": THUOCL_ZIP_URL,
                "homepage": THUOCL_HOMEPAGE,
                "license": "THUOCL custom open terms",
                "risk_level": "medium",
                "redistribution_class": "attribution_required",
                "attribution_required": True,
                "raw_committed": False,
                "notes": "Domain/common words with DF statistics, used for broad coverage.",
            },
            {
                "id": "opencc-stphrases",
                "name": "OpenCC STPhrases",
                "download_url": OPENCC_STPHRASES_URL,
                "homepage": OPENCC_HOMEPAGE,
                "license": "Apache-2.0",
                "risk_level": "low",
                "redistribution_class": "permissive",
                "attribution_required": True,
                "raw_committed": False,
                "notes": "SC->TC phrase mapping for broad-profile TC expansion.",
            },
            {
                "id": "jieba-dict",
                "name": "jieba dict.txt",
                "download_url": JIEBA_DICT_URL,
                "homepage": JIEBA_HOMEPAGE,
                "license": "MIT",
                "risk_level": "low",
                "redistribution_class": "permissive",
                "attribution_required": True,
                "raw_committed": False,
                "notes": "Word-frequency dictionary used as ranking signal.",
            },
            {
                "id": "unicode-unihan-readings",
                "name": "Unicode Unihan_Readings",
                "download_url": UNICODE_UNIHAN_URL,
                "homepage": UNICODE_HOMEPAGE,
                "license": "Unicode-3.0",
                "risk_level": "low",
                "redistribution_class": "permissive",
                "attribution_required": True,
                "raw_committed": False,
                "notes": "Character-level Mandarin readings for pinyin fallback.",
            },
            {
                "id": "zhwiki-titles-ns0",
                "name": "Wikipedia zh titles (ns0)",
                "download_url": ZHWIKI_TITLES_URL,
                "homepage": ZHWIKI_HOMEPAGE,
                "license": "CC BY-SA 4.0",
                "risk_level": "medium",
                "redistribution_class": "copyleft_sharealike",
                "attribution_required": True,
                "raw_committed": False,
                "notes": "Used as broad coverage and ranking signal for common named terms.",
            },
            {
                "id": "wikimedia-pageviews-top",
                "name": "Wikimedia Pageviews Top (zh.wikipedia)",
                "download_url": WIKIMEDIA_PAGEVIEWS_TOP_URL,
                "homepage": WIKIMEDIA_PAGEVIEWS_TOP_HOMEPAGE,
                "license": "CC BY-SA 4.0",
                "risk_level": "medium",
                "redistribution_class": "copyleft_sharealike",
                "attribution_required": True,
                "raw_committed": False,
                "notes": "Monthly top pageviews are aggregated as real-world usage heat signal.",
            },
        ],
    },
    "clean_permissive": {
        "parser": "opencc_unihan",
        "sources": [
            {
                "id": "opencc-stphrases",
                "name": "OpenCC STPhrases",
                "download_url": OPENCC_STPHRASES_URL,
                "homepage": OPENCC_HOMEPAGE,
                "license": "Apache-2.0",
                "risk_level": "low",
                "redistribution_class": "permissive",
                "attribution_required": True,
                "raw_committed": False,
                "notes": "Simplified/Traditional phrase mapping source.",
            },
            {
                "id": "unicode-unihan-readings",
                "name": "Unicode Unihan_Readings",
                "download_url": UNICODE_UNIHAN_URL,
                "homepage": UNICODE_HOMEPAGE,
                "license": "Unicode-3.0",
                "risk_level": "low",
                "redistribution_class": "permissive",
                "attribution_required": True,
                "raw_committed": False,
                "notes": "Character-level Mandarin readings for pinyin generation.",
            },
        ],
    },
    "unihan_single": {
        "parser": "unihan_only",
        "sources": [
            {
                "id": "opencc-stphrases",
                "name": "OpenCC STPhrases",
                "download_url": OPENCC_STPHRASES_URL,
                "homepage": OPENCC_HOMEPAGE,
                "license": "Apache-2.0",
                "risk_level": "low",
                "redistribution_class": "permissive",
                "attribution_required": True,
                "raw_committed": False,
                "notes": "Used for script split hints (SC/TC) in Unihan-only generation.",
            },
            {
                "id": "unicode-unihan-readings",
                "name": "Unicode Unihan_Readings",
                "download_url": UNICODE_UNIHAN_URL,
                "homepage": UNICODE_HOMEPAGE,
                "license": "Unicode-3.0",
                "risk_level": "low",
                "redistribution_class": "permissive",
                "attribution_required": True,
                "raw_committed": False,
                "notes": "Single-character Mandarin readings with frequency/rank metadata.",
            },
        ],
    },
}


def _parse_bool(text: str) -> bool:
    value = text.strip().lower()
    if value in {"true", "1", "yes", "y"}:
        return True
    if value in {"false", "0", "no", "n"}:
        return False
    raise ValueError(f"invalid boolean text: {text}")


def _to_yaml_bool(value: bool) -> str:
    return "true" if value else "false"


def _yaml_single_quote(value: object) -> str:
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\n", "\\n")
    return "'" + text.replace("'", "''") + "'"


def _normalize_pinyin_token(token: str) -> str:
    value = token.strip().lower()
    value = value.replace("u:", "v").replace("v:", "v")
    for ch in ("ü", "ǖ", "ǘ", "ǚ", "ǜ"):
        value = value.replace(ch, "v")
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[1-5]", "", value)
    value = re.sub(r"[^a-zv]", "", value)
    return value


def _normalize_pinyin(raw: str) -> str:
    tokens = raw.strip().split()
    normalized: List[str] = []
    for token in tokens:
        value = _normalize_pinyin_token(token)
        if value:
            normalized.append(value)

    if not normalized:
        return ""

    merged = "".join(normalized)
    if not PINYIN_RE.fullmatch(merged):
        return ""
    return merged


def _cjk_len(text: str) -> int:
    return len(CJK_RE.findall(text))


def _is_windows_renderable_cjk_text(text: str) -> bool:
    return bool(CJK_WINDOWS_FULL_RE.fullmatch(text))


def _compute_weight(text: str) -> int:
    # Stable seed mapping: longer CJK terms get slightly larger base weight.
    length = _cjk_len(text)
    if length <= 0:
        return 0
    return min(1000, 180 + min(length, 8) * 40)


def _compute_weight_with_signals(
    text: str,
    usage_score: float = 0.0,
    source_hits: int = 0,
    pageview_score: float = 0.0,
    wiki_hit: bool = False,
    core_entry: bool = False,
    jieba_direct_score: float = 0.0,
    pos_tag: str = "",
    char_score: float = 0.0,
) -> int:
    """
    Weight model for broad profile.

    Signals:
    - cjk length (base readability/usefulness prior)
    - aggregated cross-source usage score (strong ranking signal)
    - cross-source agreement count
    - pageview popularity score
    - wiki title hit (named/common term prior)
    - core entry bonus (keep core dictionary terms generally ahead)
    - POS / term-class shaping (daily words vs. named entities / rare tails)
    - single-character commonness prior
    """
    def _compute_term_class_bias() -> float:
        bias = 0.0

        if length == 1:
            if char_score >= 0.94:
                bias += 0.44
            elif char_score >= 0.84:
                bias += 0.30
            elif char_score >= 0.74:
                bias += 0.16
            elif (
                char_score <= 0.06
                and bounded_usage < 0.04
                and jieba_direct_score < 0.03
                and source_hits <= 1
                and bounded_pageviews < 0.02
            ):
                bias -= 0.48
            elif (
                char_score <= 0.12
                and bounded_usage < 0.06
                and jieba_direct_score < 0.05
                and source_hits <= 1
                and bounded_pageviews < 0.03
            ):
                bias -= 0.28

        if _is_named_entity_pos(pos_tag):
            if source_hits <= 1 and bounded_pageviews < 0.08 and jieba_direct_score < 0.10:
                bias -= 0.34 if length <= 3 else 0.22
            elif source_hits <= 2 and bounded_pageviews < 0.18 and jieba_direct_score < 0.16:
                bias -= 0.16
            elif (
                length <= 3
                and source_hits <= 1
                and bounded_pageviews < 0.04
                and bounded_usage < 0.20
                and jieba_direct_score < 0.10
            ):
                bias -= 0.10
        elif _is_conversational_pos(pos_tag):
            if length <= 4 and (bounded_usage >= 0.05 or jieba_direct_score >= 0.08):
                bias += 0.22
            elif length <= 4:
                bias += 0.10
        elif _is_noun_pos(pos_tag):
            if length <= 2 and (
                bounded_usage >= 0.14
                or jieba_direct_score >= 0.14
                or source_hits >= 2
                or char_score >= 0.70
            ):
                bias += 0.14
            elif length <= 2 and (
                bounded_usage >= 0.08
                or jieba_direct_score >= 0.08
                or char_score >= 0.58
            ):
                bias += 0.08
            elif length <= 3 and (bounded_usage >= 0.12 or jieba_direct_score >= 0.12 or source_hits >= 2):
                bias += 0.10
            elif length <= 4 and bounded_usage >= 0.06 and jieba_direct_score >= 0.06:
                bias += 0.06

        if length <= 3 and not _is_named_entity_pos(pos_tag):
            if bounded_usage >= 0.22 or jieba_direct_score >= 0.20:
                bias += 0.10
            elif length <= 2 and char_score >= 0.62 and (
                bounded_usage >= 0.08 or jieba_direct_score >= 0.08 or source_hits >= 2
            ):
                bias += 0.06

        if (
            length <= 4
            and bounded_usage < 0.03
            and jieba_direct_score < 0.03
            and source_hits <= 0
            and bounded_pageviews <= 0.0
            and char_score < 0.10
            and not wiki_hit
        ):
            bias -= 0.22

        if (
            length <= 2
            and bounded_usage < 0.06
            and jieba_direct_score < 0.06
            and source_hits <= 1
            and bounded_pageviews < 0.02
            and char_score < 0.18
            and not wiki_hit
        ):
            bias -= 0.12

        if length <= 2 and char_score >= 0.74 and not _is_named_entity_pos(pos_tag):
            bias += 0.10

        return max(-0.65, min(0.52, bias))

    length = max(1, _cjk_len(text))
    base = 120 + min(length, 8) * 30
    bounded_usage = min(1.0, max(0.0, usage_score))
    bounded_pageviews = min(1.0, max(0.0, pageview_score))
    usage_bonus = int(round(520.0 * math.sqrt(bounded_usage)))
    consensus_bonus = 0
    if source_hits >= 2:
        consensus_bonus = 24 + 14 * min(source_hits - 2, 4)
    pageview_bonus = int(round(92.0 * math.sqrt(bounded_pageviews))) if bounded_pageviews > 0 else 0
    wiki_bonus = 20 if wiki_hit else 0
    core_bonus = 18 if core_entry else 0
    class_bonus = int(round(_compute_term_class_bias() * 180.0))
    # Keep a global cap for compatibility with downstream consumers.
    # The current formula generally peaks below 1000 for realistic inputs.
    return min(
        1000,
        max(
            1,
            base + usage_bonus + consensus_bonus + pageview_bonus + wiki_bonus + core_bonus + class_bonus,
        ),
    )


def _build_single_char_weight_prior(mapping: Dict[Tuple[str, str], int]) -> Dict[str, float]:
    """
    Build a normalized single-character prior from current weights.
    This gives common characters a stronger prior than rare ones.
    """
    raw: Dict[str, int] = {}
    for (_pinyin, text), weight in mapping.items():
        if _cjk_len(text) != 1:
            continue
        if not CJK_FULL_RE.fullmatch(text):
            continue
        previous = raw.get(text, 0)
        if weight > previous:
            raw[text] = weight

    if not raw:
        return {}

    min_weight = min(raw.values())
    max_weight = max(raw.values())
    if max_weight <= min_weight:
        return {ch: 0.5 for ch in raw.keys()}

    spread = float(max_weight - min_weight)
    return {ch: (weight - min_weight) / spread for ch, weight in raw.items()}


def _compute_text_single_char_prior(text: str, char_prior: Dict[str, float]) -> float:
    if not text:
        return 0.0

    total = 0.0
    count = 0
    for ch in text:
        if not CJK_FULL_RE.fullmatch(ch):
            continue
        total += char_prior.get(ch, 0.0)
        count += 1

    if count <= 0:
        return 0.0
    return total / float(count)


def _normalize_jieba_pos_tag(tag: str) -> str:
    value = tag.strip().lower()
    if not value:
        return ""
    value = re.sub(r"[^a-z]", "", value)
    return value


def _compute_jieba_pos_bias(pos_tag: str, text_len: int) -> float:
    """
    Estimate IME-priority bias from jieba POS tags.

    The goal is to slightly prefer daily input词类 (verb/adverb/adj/pronoun)
    and slightly damp proper-name heavy categories in short homophone buckets.
    """
    if not pos_tag:
        return 0.0

    length = max(1, text_len)
    if length <= 2:
        length_scale = 1.0
    elif length <= 4:
        length_scale = 0.55
    else:
        length_scale = 0.30

    # Named-entity categories are often over-represented in web/wiki sources.
    if pos_tag.startswith(("nr", "ns", "nt", "nz", "nw")):
        return -0.36 * length_scale

    # Conversationally frequent classes: verb/adverb/adj/pronoun/preposition.
    if pos_tag.startswith(("v", "d", "a", "r", "p", "u", "c")):
        return 0.24 * length_scale

    # Generic noun categories stay neutral.
    if pos_tag.startswith("n"):
        return 0.0

    # Light positive prior for uncategorized non-noun tags.
    return 0.08 * length_scale


def _is_conversational_pos(pos_tag: str) -> bool:
    return pos_tag.startswith(("v", "d", "a", "r", "p", "u", "c"))


def _is_noun_pos(pos_tag: str) -> bool:
    return pos_tag.startswith("n")


def _is_named_entity_pos(pos_tag: str) -> bool:
    return pos_tag.startswith(("nr", "ns", "nt", "nz", "nw"))


def _has_effective_wiki_support(
    text: str,
    wiki_titles: Set[str],
    pageview_score: float,
    source_hits: int,
) -> bool:
    if text not in wiki_titles:
        return False
    # Full zhwiki title dump includes a large long tail. Treat wiki as an
    # effective positive signal only when real popularity or multi-source
    # consensus exists.
    return pageview_score >= 0.08 or source_hits >= 2


def _compute_effective_pos_bias(
    pos_tag: str,
    text_len: int,
    usage_score: float,
    jieba_direct_score: float,
    source_hits: int,
    pageview_score: float,
    char_score: float,
) -> float:
    """
    Scale POS bias by signal confidence.

    jieba POS can mislabel common words (for example tagging regular words as 'nr').
    Use multi-signal confidence so POS is a tiebreaker, not a hard override.
    """
    base_bias = _compute_jieba_pos_bias(pos_tag, text_len)
    if abs(base_bias) <= 1e-9:
        return 0.0

    confidence = max(
        0.0,
        min(1.0, usage_score),
        min(1.0, jieba_direct_score),
        min(1.0, pageview_score * 1.3),
    )

    if source_hits >= 2:
        confidence = max(confidence, 0.42)
    elif source_hits == 1:
        confidence = max(confidence, 0.24)

    if text_len <= 2:
        confidence = max(confidence, min(1.0, char_score * 0.45))

    # Keep a small floor to preserve deterministic ordering, while avoiding over-penalization.
    confidence = min(1.0, max(0.08, confidence))
    return base_bias * confidence


def _build_effective_char_prior(
    mapping: Dict[Tuple[str, str], int],
    char_frequency_prior: Dict[str, float] | None,
) -> Dict[str, float]:
    char_frequency_prior = char_frequency_prior or {}
    mapping_char_prior = _build_single_char_weight_prior(mapping)
    if not char_frequency_prior:
        return mapping_char_prior

    char_prior: Dict[str, float] = {}
    for ch in set(mapping_char_prior.keys()) | set(char_frequency_prior.keys()):
        char_prior[ch] = (
            0.22 * mapping_char_prior.get(ch, 0.0)
            + 0.78 * char_frequency_prior.get(ch, 0.0)
        )
    return char_prior


def _rerank_homophone_buckets(
    mapping: Dict[Tuple[str, str], int],
    usage_score_map: Dict[str, float],
    source_hits_map: Dict[str, int],
    pageviews_signal_map: Dict[str, float],
    wiki_titles: Set[str],
    jieba_direct_signal_map: Dict[str, float] | None,
    jieba_pos_map: Dict[str, str] | None,
    char_frequency_prior: Dict[str, float] | None,
    stats_prefix: str,
) -> Dict[str, int]:
    """
    Re-rank entries within each same-pinyin bucket to suppress rare/noisy
    homophone candidates and promote commonly used terms.

    The score mixes:
    - term usage/pageview/source-hit signals
    - normalized single-character prior from the same mapping
    - a small original-weight prior for stability
    """
    c_max_delta = 320
    c_sparse_penalty = 132
    c_weak_signal_penalty = 78
    c_named_entity_penalty = 108
    c_rare_form_penalty = 168

    stats = {
        f"{stats_prefix}_homophone_buckets": 0,
        f"{stats_prefix}_homophone_entries_adjusted": 0,
        f"{stats_prefix}_homophone_entries_boosted": 0,
        f"{stats_prefix}_homophone_entries_damped": 0,
        f"{stats_prefix}_homophone_sparse_penalized": 0,
        f"{stats_prefix}_homophone_rare_form_penalized": 0,
    }
    if not mapping:
        return stats
    if (
        not usage_score_map
        and not source_hits_map
        and not pageviews_signal_map
        and not wiki_titles
    ):
        # No robust usage signals available (e.g. external_cedict profile):
        # skip bucket reranking to avoid overfitting to shape-based priors only.
        return stats

    jieba_direct_signal_map = jieba_direct_signal_map or {}
    jieba_pos_map = jieba_pos_map or {}
    char_prior = _build_effective_char_prior(mapping, char_frequency_prior)
    buckets: Dict[str, List[Tuple[str, int]]] = {}
    for (pinyin, text), weight in mapping.items():
        buckets.setdefault(pinyin, []).append((text, weight))

    for pinyin, items in buckets.items():
        if len(items) < 2:
            continue
        stats[f"{stats_prefix}_homophone_buckets"] += 1

        raw_scores: Dict[str, float] = {}
        bucket_has_strong_term = False
        bucket_has_conversational_short_term = False
        for text, weight in items:
            text_len = _cjk_len(text)
            usage_score = min(1.0, max(0.0, usage_score_map.get(text, 0.0)))
            source_hits = max(0, source_hits_map.get(text, 0))
            pageview_score = min(1.0, max(0.0, pageviews_signal_map.get(text, 0.0)))
            wiki_hit = 1.0 if _has_effective_wiki_support(
                text,
                wiki_titles,
                pageview_score=pageview_score,
                source_hits=source_hits,
            ) else 0.0
            jieba_direct_score = min(1.0, max(0.0, jieba_direct_signal_map.get(text, 0.0)))
            char_score = _compute_text_single_char_prior(text, char_prior)
            pos_tag = jieba_pos_map.get(text, "")
            pos_bias = _compute_effective_pos_bias(
                pos_tag=pos_tag,
                text_len=text_len,
                usage_score=usage_score,
                jieba_direct_score=jieba_direct_score,
                source_hits=source_hits,
                pageview_score=pageview_score,
                char_score=char_score,
            )
            min_char_prior = 1.0
            has_cjk_char = False
            for ch in text:
                if not CJK_FULL_RE.fullmatch(ch):
                    continue
                has_cjk_char = True
                value = min(1.0, max(0.0, char_prior.get(ch, 0.0)))
                if value < min_char_prior:
                    min_char_prior = value
            if not has_cjk_char:
                min_char_prior = 0.0
            if text_len <= 2:
                char_weight = 220.0
            elif text_len <= 4:
                char_weight = 72.0
            else:
                char_weight = 28.0
            if text_len <= 2 and _is_conversational_pos(pos_tag):
                bucket_has_conversational_short_term = True

            if (
                usage_score >= 0.28
                or jieba_direct_score >= 0.42
                or source_hits >= 2
                or pageview_score >= 0.22
                or wiki_hit > 0.0
                or (pos_bias >= 0.08 and jieba_direct_score >= 0.16)
            ):
                bucket_has_strong_term = True

            raw_scores[text] = (
                usage_score * 220.0
                + jieba_direct_score * 220.0
                + min(source_hits, 4) * 22.0
                + pageview_score * 40.0
                + wiki_hit * 12.0
                + char_score * char_weight
                + pos_bias * 190.0
                + (weight / 1000.0) * 14.0
            )

        raw_values = list(raw_scores.values())
        min_raw = min(raw_values)
        max_raw = max(raw_values)
        spread = max_raw - min_raw
        if spread <= 1e-6:
            continue

        spread_factor = min(1.0, spread / 240.0)

        for text, weight in items:
            text_len = _cjk_len(text)
            usage_score = min(1.0, max(0.0, usage_score_map.get(text, 0.0)))
            source_hits = max(0, source_hits_map.get(text, 0))
            pageview_score = min(1.0, max(0.0, pageviews_signal_map.get(text, 0.0)))
            jieba_direct_score = min(1.0, max(0.0, jieba_direct_signal_map.get(text, 0.0)))
            wiki_support = _has_effective_wiki_support(
                text,
                wiki_titles,
                pageview_score=pageview_score,
                source_hits=source_hits,
            )
            char_score = _compute_text_single_char_prior(text, char_prior)
            pos_tag = jieba_pos_map.get(text, "")
            pos_bias = _compute_effective_pos_bias(
                pos_tag=pos_tag,
                text_len=text_len,
                usage_score=usage_score,
                jieba_direct_score=jieba_direct_score,
                source_hits=source_hits,
                pageview_score=pageview_score,
                char_score=char_score,
            )
            normalized = (raw_scores[text] - min_raw) / spread
            delta_cap = c_max_delta
            delta = int(round((normalized - 0.5) * (2 * delta_cap) * spread_factor))

            if (
                bucket_has_strong_term
                and usage_score < 0.05
                and jieba_direct_score < 0.04
                and source_hits <= 0
                and pageview_score <= 0.0
                and not wiki_support
            ):
                delta -= c_sparse_penalty
                stats[f"{stats_prefix}_homophone_sparse_penalized"] += 1
            elif (
                bucket_has_strong_term
                and usage_score < 0.10
                and jieba_direct_score < 0.10
                and source_hits <= 1
                and pageview_score <= 0.02
                and not wiki_support
            ):
                delta -= c_weak_signal_penalty

            if (
                bucket_has_strong_term
                and text_len <= 3
                and usage_score < 0.08
                and jieba_direct_score < 0.02
                and source_hits <= 1
                and pageview_score <= 0.01
                and not wiki_support
                and min_char_prior < 0.16
            ):
                delta -= c_rare_form_penalty
                stats[f"{stats_prefix}_homophone_rare_form_penalized"] += 1

            if (
                bucket_has_strong_term
                and text_len <= 2
                and pos_bias <= -0.12
                and usage_score < 0.30
                and jieba_direct_score < 0.32
                and source_hits <= 1
            ):
                delta -= c_named_entity_penalty
            elif (
                bucket_has_strong_term
                and text_len <= 3
                and _is_named_entity_pos(pos_tag)
                and source_hits <= 2
                and pageview_score < 0.08
                and jieba_direct_score < 0.10
                and usage_score < 0.48
            ):
                # Suppress low-traffic short names/places in homophone buckets.
                delta -= 96
            elif (
                bucket_has_strong_term
                and text_len <= 2
                and pos_bias >= 0.10
                and (usage_score >= 0.10 or jieba_direct_score >= 0.14 or char_score >= 0.62)
            ):
                delta += 34
            elif (
                bucket_has_strong_term
                and text_len <= 2
                and not _is_named_entity_pos(pos_tag)
                and char_score >= 0.56
                and (usage_score >= 0.08 or jieba_direct_score >= 0.10 or source_hits >= 2)
            ):
                delta += 30

            if (
                bucket_has_strong_term
                and text_len <= 3
                and pos_bias <= -0.20
                and usage_score < 0.18
                and jieba_direct_score < 0.12
                and source_hits <= 1
                and pageview_score <= 0.04
                and not wiki_support
            ):
                delta -= 42

            if (
                bucket_has_strong_term
                and text_len <= 2
                and not _is_named_entity_pos(pos_tag)
                and _is_conversational_pos(pos_tag)
                and char_score >= 0.38
                and (usage_score >= 0.06 or jieba_direct_score >= 0.08 or source_hits >= 2)
            ):
                # Favor short modern verb/adj/functional terms over literary or
                # low-signal homophones when the bucket already has a strong term.
                delta += 28
            elif (
                bucket_has_strong_term
                and text_len <= 2
                and _is_noun_pos(pos_tag)
                and not _is_named_entity_pos(pos_tag)
                and char_score < 0.46
                and usage_score < 0.10
                and jieba_direct_score < 0.08
                and source_hits <= 1
                and pageview_score <= 0.02
                and not wiki_support
            ):
                delta -= 24

            if bucket_has_conversational_short_term and text_len <= 2:
                # Keep conversational preference as a mild tiebreaker only.
                # The old ±300~400 forcing was too aggressive and could demote
                # common nouns (for example "世界") below rare conversational forms.
                if _is_conversational_pos(pos_tag):
                    if usage_score >= 0.10 or jieba_direct_score >= 0.14 or source_hits >= 2:
                        delta += 48
                    elif usage_score >= 0.04 or jieba_direct_score >= 0.06:
                        delta += 24
                elif _is_noun_pos(pos_tag):
                    if (
                        usage_score < 0.06
                        and jieba_direct_score < 0.08
                        and source_hits <= 1
                        and pageview_score <= 0.02
                        and not wiki_support
                    ):
                        delta -= 44
                    elif (
                        usage_score < 0.28
                        and jieba_direct_score < 0.65
                        and source_hits <= 1
                        and pageview_score <= 0.02
                        and not wiki_support
                    ):
                        delta -= 56
                    elif (
                        char_score >= 0.58
                        and (usage_score >= 0.08 or jieba_direct_score >= 0.10 or source_hits >= 2)
                    ):
                        delta += 20

            if (
                text_len <= 2
                and _is_conversational_pos(pos_tag)
                and text
                and text[0] in ("不", "没", "无", "非", "未")
                and (usage_score >= 0.12 or jieba_direct_score >= 0.10 or char_score >= 0.75)
            ):
                delta += 90

            if bucket_has_strong_term:
                if jieba_direct_score >= 0.70 and usage_score >= 0.16:
                    delta += 32
                elif jieba_direct_score >= 0.50 and usage_score >= 0.12:
                    delta += 16

            if delta > delta_cap:
                delta = delta_cap
            elif delta < -delta_cap:
                delta = -delta_cap

            if delta == 0:
                continue

            new_weight = max(1, min(1000, weight + delta))
            if new_weight == weight:
                continue

            mapping[(pinyin, text)] = new_weight
            stats[f"{stats_prefix}_homophone_entries_adjusted"] += 1
            if new_weight > weight:
                stats[f"{stats_prefix}_homophone_entries_boosted"] += 1
            else:
                stats[f"{stats_prefix}_homophone_entries_damped"] += 1

    return stats


def _filter_low_signal_rare_entries(
    mapping: Dict[Tuple[str, str], int],
    usage_score_map: Dict[str, float],
    source_hits_map: Dict[str, int],
    pageviews_signal_map: Dict[str, float],
    wiki_titles: Set[str],
    jieba_direct_signal_map: Dict[str, float] | None,
    jieba_pos_map: Dict[str, str] | None,
    char_frequency_prior: Dict[str, float] | None,
    stats_prefix: str,
) -> Dict[str, int]:
    """
    Remove extremely low-signal rare forms when the same pinyin bucket already
    has stronger mainstream candidates.
    """
    stats = {
        f"{stats_prefix}_low_signal_rare_buckets": 0,
        f"{stats_prefix}_low_signal_rare_removed": 0,
        f"{stats_prefix}_low_signal_named_removed": 0,
    }
    if not mapping:
        return stats
    if (
        not usage_score_map
        and not source_hits_map
        and not pageviews_signal_map
        and not wiki_titles
    ):
        return stats

    jieba_direct_signal_map = jieba_direct_signal_map or {}
    jieba_pos_map = jieba_pos_map or {}
    char_prior = _build_effective_char_prior(mapping, char_frequency_prior)

    buckets: Dict[str, List[str]] = {}
    for (pinyin, text) in mapping.keys():
        buckets.setdefault(pinyin, []).append(text)

    for pinyin, texts in buckets.items():
        if len(texts) < 2:
            continue

        bucket_has_strong = False
        for text in texts:
            usage_score = min(1.0, max(0.0, usage_score_map.get(text, 0.0)))
            source_hits = max(0, source_hits_map.get(text, 0))
            pageview_score = min(1.0, max(0.0, pageviews_signal_map.get(text, 0.0)))
            jieba_direct_score = min(1.0, max(0.0, jieba_direct_signal_map.get(text, 0.0)))
            if (
                usage_score >= 0.12
                or jieba_direct_score >= 0.08
                or source_hits >= 2
                or pageview_score >= 0.08
                or _has_effective_wiki_support(
                    text,
                    wiki_titles,
                    pageview_score=pageview_score,
                    source_hits=source_hits,
                )
            ):
                bucket_has_strong = True
                break
        if not bucket_has_strong:
            continue
        stats[f"{stats_prefix}_low_signal_rare_buckets"] += 1

        to_drop: List[Tuple[str, str]] = []
        for text in texts:
            text_len = _cjk_len(text)
            usage_score = min(1.0, max(0.0, usage_score_map.get(text, 0.0)))
            source_hits = max(0, source_hits_map.get(text, 0))
            pageview_score = min(1.0, max(0.0, pageviews_signal_map.get(text, 0.0)))
            jieba_direct_score = min(1.0, max(0.0, jieba_direct_signal_map.get(text, 0.0)))
            pos_tag = jieba_pos_map.get(text, "")
            wiki_support = _has_effective_wiki_support(
                text,
                wiki_titles,
                pageview_score=pageview_score,
                source_hits=source_hits,
            )

            min_char_prior = 1.0
            has_cjk_char = False
            for ch in text:
                if not CJK_FULL_RE.fullmatch(ch):
                    continue
                has_cjk_char = True
                value = min(1.0, max(0.0, char_prior.get(ch, 0.0)))
                if value < min_char_prior:
                    min_char_prior = value
            if not has_cjk_char:
                min_char_prior = 0.0

            char_score = _compute_text_single_char_prior(text, char_prior)
            # Protect common modern 2-char words even when cross-source signals
            # are incomplete (notably in TC conversion paths).
            if text_len <= 2 and char_score >= 0.58:
                continue
            if (
                text_len <= 2
                and not _is_named_entity_pos(pos_tag)
                and (
                    (
                        _is_conversational_pos(pos_tag)
                        and char_score >= 0.36
                        and (usage_score >= 0.05 or jieba_direct_score >= 0.07 or source_hits >= 2)
                    )
                    or (
                        _is_noun_pos(pos_tag)
                        and char_score >= 0.48
                        and (usage_score >= 0.06 or jieba_direct_score >= 0.08 or source_hits >= 2)
                    )
                )
            ):
                continue

            if (
                usage_score < 0.10
                and jieba_direct_score < 0.04
                and source_hits <= 1
                and pageview_score <= 0.02
                and not wiki_support
                and min_char_prior < 0.08
            ):
                to_drop.append((pinyin, text))
                continue

            if (
                _is_named_entity_pos(pos_tag)
                and usage_score < 0.38
                and jieba_direct_score < 0.12
                and source_hits <= 2
                and pageview_score < 0.08
                and not wiki_support
            ):
                to_drop.append((pinyin, text))
                stats[f"{stats_prefix}_low_signal_named_removed"] += 1

        for key in to_drop:
            if key in mapping:
                del mapping[key]
                stats[f"{stats_prefix}_low_signal_rare_removed"] += 1

    return stats


def _filter_global_tail_entries(
    mapping: Dict[Tuple[str, str], int],
    usage_score_map: Dict[str, float],
    source_hits_map: Dict[str, int],
    pageviews_signal_map: Dict[str, float],
    wiki_titles: Set[str],
    jieba_direct_signal_map: Dict[str, float] | None,
    jieba_pos_map: Dict[str, str] | None,
    char_frequency_prior: Dict[str, float] | None,
    stats_prefix: str,
) -> Dict[str, int]:
    """
    Global tail trimming (independent of homophone buckets).

    This catches low-signal singleton entries that bucket-based filtering
    cannot see, especially weak named entities and rare-form leftovers.
    """
    stats = {
        f"{stats_prefix}_global_tail_removed": 0,
        f"{stats_prefix}_global_tail_named_removed": 0,
        f"{stats_prefix}_global_tail_rare_char_removed": 0,
    }
    if not mapping:
        return stats
    if (
        not usage_score_map
        and not source_hits_map
        and not pageviews_signal_map
        and not wiki_titles
    ):
        return stats

    jieba_direct_signal_map = jieba_direct_signal_map or {}
    jieba_pos_map = jieba_pos_map or {}
    char_prior = _build_effective_char_prior(mapping, char_frequency_prior)
    to_drop: List[Tuple[str, str]] = []
    bucket_counts: Dict[str, int] = {}
    for pinyin, _text in mapping.keys():
        bucket_counts[pinyin] = bucket_counts.get(pinyin, 0) + 1
    remaining_bucket_counts: Dict[str, int] = dict(bucket_counts)
    bucket_keepers: Dict[str, Tuple[str, str]] = {}
    bucket_keeper_scores: Dict[str, Tuple[float, float, float, float, float, float, int, str]] = {}

    def build_bucket_keeper_score(entry_key: Tuple[str, str]) -> Tuple[float, float, float, float, float, float, int, str]:
        _entry_pinyin, entry_text = entry_key
        entry_usage_score = min(1.0, max(0.0, usage_score_map.get(entry_text, 0.0)))
        entry_source_hits = float(max(0, source_hits_map.get(entry_text, 0)))
        entry_pageview_score = min(1.0, max(0.0, pageviews_signal_map.get(entry_text, 0.0)))
        entry_jieba_direct_score = min(1.0, max(0.0, jieba_direct_signal_map.get(entry_text, 0.0)))
        entry_char_score = _compute_text_single_char_prior(entry_text, char_prior)
        return (
            float(mapping.get(entry_key, 0)),
            entry_usage_score,
            entry_jieba_direct_score,
            entry_pageview_score,
            entry_source_hits,
            entry_char_score,
            -_cjk_len(entry_text),
            entry_text,
        )

    # When trimming a low-signal tail, preserve the strongest remaining
    # candidate in each pinyin bucket instead of whichever entry happens to be
    # visited last in dict order.
    for key in mapping.keys():
        entry_pinyin, _entry_text = key
        keeper_score = build_bucket_keeper_score(key)
        if (
            entry_pinyin not in bucket_keeper_scores
            or keeper_score > bucket_keeper_scores[entry_pinyin]
        ):
            bucket_keeper_scores[entry_pinyin] = keeper_score
            bucket_keepers[entry_pinyin] = key

    def schedule_drop(entry_key: Tuple[str, str]) -> bool:
        entry_pinyin, _ = entry_key
        if bucket_keepers.get(entry_pinyin) == entry_key:
            return False
        remaining = remaining_bucket_counts.get(entry_pinyin, 0)
        if remaining <= 1:
            return False
        to_drop.append(entry_key)
        remaining_bucket_counts[entry_pinyin] = remaining - 1
        return True

    for key in list(mapping.keys()):
        pinyin, text = key
        text_len = _cjk_len(text)
        if text_len < 2:
            continue

        usage_score = min(1.0, max(0.0, usage_score_map.get(text, 0.0)))
        source_hits = max(0, source_hits_map.get(text, 0))
        pageview_score = min(1.0, max(0.0, pageviews_signal_map.get(text, 0.0)))
        jieba_direct_score = min(1.0, max(0.0, jieba_direct_signal_map.get(text, 0.0)))
        pos_tag = jieba_pos_map.get(text, "")
        wiki_support = _has_effective_wiki_support(
            text,
            wiki_titles,
            pageview_score=pageview_score,
            source_hits=source_hits,
        )

        # Keep at least one candidate per pinyin bucket to avoid hard holes.
        if bucket_counts.get(pinyin, 0) < 2:
            continue

        min_char_prior = 1.0
        has_cjk_char = False
        for ch in text:
            if not CJK_FULL_RE.fullmatch(ch):
                continue
            has_cjk_char = True
            value = min(1.0, max(0.0, char_prior.get(ch, 0.0)))
            if value < min_char_prior:
                min_char_prior = value
        if not has_cjk_char:
            min_char_prior = 0.0

        char_score = _compute_text_single_char_prior(text, char_prior)
        # Protect common modern 2-char words even when TC-side signal mapping
        # misses some entries.
        if text_len <= 2 and char_score >= 0.58:
            continue
        if (
            text_len <= 2
            and not _is_named_entity_pos(pos_tag)
            and (
                (
                    _is_conversational_pos(pos_tag)
                    and char_score >= 0.36
                    and (usage_score >= 0.05 or jieba_direct_score >= 0.07 or source_hits >= 2)
                )
                or (
                    _is_noun_pos(pos_tag)
                    and char_score >= 0.48
                    and (usage_score >= 0.06 or jieba_direct_score >= 0.08 or source_hits >= 2)
                )
            )
        ):
            continue

        if (
            _is_named_entity_pos(pos_tag)
            and text_len <= 4
            and not wiki_support
            and source_hits <= 2
            and pageview_score < 0.10
            and jieba_direct_score < 0.14
            and usage_score < 0.38
        ):
            if schedule_drop(key):
                stats[f"{stats_prefix}_global_tail_named_removed"] += 1
            continue

        if (
            text_len <= 4
            and usage_score < 0.06
            and jieba_direct_score < 0.02
            and source_hits <= 1
            and pageview_score <= 0.01
            and not wiki_support
            and min_char_prior < 0.04
        ):
            if schedule_drop(key):
                stats[f"{stats_prefix}_global_tail_rare_char_removed"] += 1
            continue

    for key in to_drop:
        if key in mapping:
            del mapping[key]
            stats[f"{stats_prefix}_global_tail_removed"] += 1

    return stats


def _collect_suspicious_high_weight_entries(
    mapping: Dict[Tuple[str, str], int],
    usage_score_map: Dict[str, float],
    source_hits_map: Dict[str, int],
    pageviews_signal_map: Dict[str, float],
    wiki_titles: Set[str],
    jieba_direct_signal_map: Dict[str, float] | None,
    jieba_pos_map: Dict[str, str] | None,
    char_frequency_prior: Dict[str, float] | None,
    limit: int = 25,
) -> List[Dict[str, object]]:
    if not mapping:
        return []

    jieba_direct_signal_map = jieba_direct_signal_map or {}
    jieba_pos_map = jieba_pos_map or {}
    char_prior = _build_effective_char_prior(mapping, char_frequency_prior)
    suspicious: List[Dict[str, object]] = []

    for (pinyin, text), weight in mapping.items():
        text_len = _cjk_len(text)
        if text_len <= 0 or text_len > 3 or weight < 420:
            continue

        usage_score = min(1.0, max(0.0, usage_score_map.get(text, 0.0)))
        source_hits = max(0, source_hits_map.get(text, 0))
        pageview_score = min(1.0, max(0.0, pageviews_signal_map.get(text, 0.0)))
        jieba_direct_score = min(1.0, max(0.0, jieba_direct_signal_map.get(text, 0.0)))
        pos_tag = jieba_pos_map.get(text, "")
        char_score = _compute_text_single_char_prior(text, char_prior)
        wiki_support = _has_effective_wiki_support(
            text,
            wiki_titles,
            pageview_score=pageview_score,
            source_hits=source_hits,
        )

        reasons: List[str] = []
        if (
            _is_named_entity_pos(pos_tag)
            and source_hits <= 2
            and pageview_score < 0.10
            and jieba_direct_score < 0.14
            and usage_score < 0.38
            and not wiki_support
        ):
            reasons.append("low-signal-named")
        if (
            text_len <= 2
            and char_score < 0.20
            and usage_score < 0.08
            and jieba_direct_score < 0.08
            and source_hits <= 1
            and pageview_score < 0.02
            and not wiki_support
        ):
            reasons.append("rare-char")
        if (
            usage_score < 0.04
            and jieba_direct_score < 0.04
            and source_hits <= 1
            and pageview_score < 0.02
            and not wiki_support
        ):
            reasons.append("weak-usage")

        if not reasons:
            continue

        risk_score = weight - int(
            round(
                usage_score * 220.0
                + jieba_direct_score * 220.0
                + pageview_score * 80.0
                + source_hits * 28.0
                + char_score * 140.0
                + (40.0 if wiki_support else 0.0)
            )
        )
        suspicious.append(
            {
                "pinyin": pinyin,
                "text": text,
                "weight": weight,
                "usage": usage_score,
                "jieba": jieba_direct_score,
                "pageviews": pageview_score,
                "source_hits": source_hits,
                "char_score": char_score,
                "pos": pos_tag or "-",
                "reasons": ",".join(reasons),
                "risk_score": risk_score,
            }
        )

    suspicious.sort(
        key=lambda item: (
            int(item["risk_score"]),
            int(item["weight"]),
            -_cjk_len(str(item["text"])),
            str(item["text"]),
        ),
        reverse=True,
    )
    return suspicious[:limit]


def _download_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": DEFAULT_HTTP_USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def _read_source_bytes(url: str, cache_file: pathlib.Path | None) -> bytes:
    if cache_file and cache_file.exists():
        return cache_file.read_bytes()

    payload = _download_bytes(url)
    if cache_file:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_bytes(payload)
    return payload


def _decode_text(payload: bytes) -> str:
    if payload.startswith(b"\x1f\x8b"):
        payload = gzip.decompress(payload)
    return payload.decode("utf-8", errors="ignore")


def _parse_cedict_entries(
    source_text: str,
    min_hanzi: int,
) -> Tuple[Dict[Tuple[str, str], int], Dict[Tuple[str, str], int], Dict[str, int]]:
    sc: Dict[Tuple[str, str], int] = {}
    tc: Dict[Tuple[str, str], int] = {}
    stats = {
        "total_lines": 0,
        "parsed_lines": 0,
        "invalid_format": 0,
        "invalid_pinyin": 0,
        "filtered_short": 0,
    }

    for raw_line in source_text.splitlines():
        stats["total_lines"] += 1
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        match = CEDICT_LINE_RE.match(line)
        if not match:
            stats["invalid_format"] += 1
            continue

        trad, simp, pinyin_raw, _defs = match.groups()
        pinyin = _normalize_pinyin(pinyin_raw)
        if not pinyin:
            stats["invalid_pinyin"] += 1
            continue

        stats["parsed_lines"] += 1

        for text, bucket in ((simp, sc), (trad, tc)):
            if _cjk_len(text) < min_hanzi:
                stats["filtered_short"] += 1
                continue
            key = (pinyin, text)
            weight = _compute_weight(text)
            previous = bucket.get(key, 0)
            if weight > previous:
                bucket[key] = weight

    return sc, tc, stats


def _parse_opencc_entries(source_text: str, min_hanzi: int) -> Tuple[List[Tuple[str, str]], Dict[str, int]]:
    entries: List[Tuple[str, str]] = []
    stats = {
        "total_lines": 0,
        "parsed_lines": 0,
        "invalid_format": 0,
        "filtered_short": 0,
    }

    for raw_line in source_text.splitlines():
        stats["total_lines"] += 1
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        parts = line.split("\t")
        if len(parts) < 1:
            stats["invalid_format"] += 1
            continue

        sc = parts[0].strip()
        tc = parts[1].strip() if len(parts) >= 2 else sc
        if not sc:
            stats["invalid_format"] += 1
            continue

        if (_cjk_len(sc) < min_hanzi) and (_cjk_len(tc) < min_hanzi):
            stats["filtered_short"] += 1
            continue

        entries.append((sc, tc))
        stats["parsed_lines"] += 1

    return entries, stats


def _parse_thuocl_entries(
    payload: bytes,
) -> Tuple[Dict[str, int], Dict[str, int], Dict[str, int]]:
    stats = {
        "thuocl_total_files": 0,
        "thuocl_total_lines": 0,
        "thuocl_parsed_lines": 0,
        "thuocl_invalid_format": 0,
    }
    entries_max_df: Dict[str, int] = {}
    entries_coverage: Dict[str, int] = {}

    if not payload.startswith(b"PK"):
        stats["thuocl_invalid_format"] += 1
        return entries_max_df, entries_coverage, stats

    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        file_names = [
            name
            for name in zf.namelist()
            if name.endswith(".txt") and "/data/THUOCL_" in name
        ]
        stats["thuocl_total_files"] = len(file_names)

        for name in file_names:
            text = zf.read(name).decode("utf-8", errors="ignore")
            file_seen: Set[str] = set()
            for raw_line in text.splitlines():
                stats["thuocl_total_lines"] += 1
                line = raw_line.strip()
                if not line:
                    continue
                matched = re.match(r"^(.+?)\s+(\d+)\s*$", line)
                if not matched:
                    stats["thuocl_invalid_format"] += 1
                    continue

                word = matched.group(1).strip()
                try:
                    df_value = int(matched.group(2))
                except ValueError:
                    stats["thuocl_invalid_format"] += 1
                    continue

                if not word:
                    stats["thuocl_invalid_format"] += 1
                    continue

                previous = entries_max_df.get(word, 0)
                if df_value > previous:
                    entries_max_df[word] = df_value
                if word not in file_seen:
                    entries_coverage[word] = entries_coverage.get(word, 0) + 1
                    file_seen.add(word)
                stats["thuocl_parsed_lines"] += 1

    stats["thuocl_unique_terms"] = len(entries_max_df)
    return entries_max_df, entries_coverage, stats


def _normalize_wiki_title_with_reason(
    raw_title: str,
    min_hanzi: int,
    max_hanzi: int = 8,
) -> Tuple[str, str]:
    title = raw_title.strip()
    if not title:
        return "", "empty"

    title = title.replace("_", "").replace(" ", "").strip()
    # Remove trailing disambiguation suffixes: (xxx) / （xxx）
    title = re.sub(r"[\uFF08(][^\uFF08\uFF09()]{0,24}[\uFF09)]$", "", title).strip()
    if not title:
        return "", "empty"
    if (":" in title) or ("\uFF1A" in title):
        return "", "colon"
    if not CJK_FULL_RE.fullmatch(title):
        return "", "non_cjk"

    hanzi_len = _cjk_len(title)
    if hanzi_len < min_hanzi:
        return "", "short"
    if hanzi_len > max_hanzi:
        return "", "long"
    return title, ""


def _normalize_wiki_title(raw_title: str, min_hanzi: int, max_hanzi: int = 8) -> str:
    normalized, _reason = _normalize_wiki_title_with_reason(
        raw_title,
        min_hanzi=min_hanzi,
        max_hanzi=max_hanzi,
    )
    return normalized


def _parse_wiki_titles_entries(
    payload: bytes,
    min_hanzi: int,
    max_hanzi: int = 8,
) -> Tuple[Set[str], Dict[str, int]]:
    stats = {
        "wiki_total_lines": 0,
        "wiki_kept_titles": 0,
        "wiki_skipped_empty": 0,
        "wiki_skipped_colon": 0,
        "wiki_skipped_non_cjk": 0,
        "wiki_skipped_short": 0,
        "wiki_skipped_long": 0,
        "wiki_deduplicated": 0,
    }
    titles: Set[str] = set()
    text = _decode_text(payload)

    for raw_line in text.splitlines():
        stats["wiki_total_lines"] += 1
        normalized, reason = _normalize_wiki_title_with_reason(
            raw_line,
            min_hanzi=min_hanzi,
            max_hanzi=max_hanzi,
        )
        if not normalized:
            if reason == "empty":
                stats["wiki_skipped_empty"] += 1
            elif reason == "colon":
                stats["wiki_skipped_colon"] += 1
            elif reason == "non_cjk":
                stats["wiki_skipped_non_cjk"] += 1
            elif reason == "short":
                stats["wiki_skipped_short"] += 1
            elif reason == "long":
                stats["wiki_skipped_long"] += 1
            else:
                stats["wiki_skipped_empty"] += 1
            continue

        before = len(titles)
        titles.add(normalized)
        if len(titles) == before:
            stats["wiki_deduplicated"] += 1
        else:
            stats["wiki_kept_titles"] += 1

    return titles, stats


def _iter_recent_complete_months(month_count: int) -> List[Tuple[int, int]]:
    if month_count <= 0:
        return []

    cursor = dt.date.today().replace(day=1)
    months: List[Tuple[int, int]] = []
    for _ in range(month_count):
        cursor = (cursor - dt.timedelta(days=1)).replace(day=1)
        months.append((cursor.year, cursor.month))
    return months


def _parse_wikimedia_pageviews_payload(
    payload: bytes,
    min_hanzi: int,
    max_rank: int,
    max_hanzi: int = 8,
) -> Tuple[Dict[str, int], Dict[str, int]]:
    stats = {
        "pageviews_articles_total": 0,
        "pageviews_articles_rank_filtered": 0,
        "pageviews_articles_title_filtered": 0,
        "pageviews_articles_kept": 0,
    }
    entries: Dict[str, int] = {}
    data = json.loads(payload.decode("utf-8", errors="ignore"))
    for item in data.get("items", []):
        for article in item.get("articles", []):
            stats["pageviews_articles_total"] += 1
            rank = int(article.get("rank", 0) or 0)
            if rank <= 0 or rank > max_rank:
                stats["pageviews_articles_rank_filtered"] += 1
                continue
            title = str(article.get("article", ""))
            normalized = _normalize_wiki_title(
                title,
                min_hanzi=min_hanzi,
                max_hanzi=max_hanzi,
            )
            if not normalized:
                stats["pageviews_articles_title_filtered"] += 1
                continue
            views = int(article.get("views", 0) or 0)
            if views <= 0:
                continue

            stats["pageviews_articles_kept"] += 1
            entries[normalized] = entries.get(normalized, 0) + views
    stats["pageviews_unique_terms"] = len(entries)
    return entries, stats


def _load_wikimedia_pageviews_entries(
    repo_root: pathlib.Path,
    source_url: str,
    min_hanzi: int,
    months: int,
    max_rank: int,
) -> Tuple[Dict[str, int], Dict[str, int]]:
    stats = {
        "pageviews_months_requested": months,
        "pageviews_months_loaded": 0,
        "pageviews_cache_hits": 0,
        "pageviews_http_fetches": 0,
        "pageviews_http_failures": 0,
        "pageviews_articles_total": 0,
        "pageviews_articles_rank_filtered": 0,
        "pageviews_articles_title_filtered": 0,
        "pageviews_articles_kept": 0,
    }
    aggregate: Dict[str, int] = {}
    cache_dir = repo_root / "data" / "cache" / "wikimedia_pageviews"
    base_url = source_url.rstrip("/")

    for year, month in _iter_recent_complete_months(months):
        cache_file = cache_dir / f"zhwiki_top_{year:04d}{month:02d}.json"
        payload: bytes
        if cache_file.exists():
            payload = cache_file.read_bytes()
            stats["pageviews_cache_hits"] += 1
        else:
            try:
                month_url = f"{base_url}/{year:04d}/{month:02d}/all-days"
                request = urllib.request.Request(
                    month_url,
                    headers={"User-Agent": DEFAULT_HTTP_USER_AGENT},
                )
                with urllib.request.urlopen(request, timeout=60) as response:
                    payload = response.read()
                cache_file.parent.mkdir(parents=True, exist_ok=True)
                cache_file.write_bytes(payload)
                stats["pageviews_http_fetches"] += 1
            except Exception:
                stats["pageviews_http_failures"] += 1
                continue

        month_entries, month_stats = _parse_wikimedia_pageviews_payload(
            payload,
            min_hanzi=min_hanzi,
            max_rank=max_rank,
        )
        if month_entries:
            stats["pageviews_months_loaded"] += 1
        for key in (
            "pageviews_articles_total",
            "pageviews_articles_rank_filtered",
            "pageviews_articles_title_filtered",
            "pageviews_articles_kept",
        ):
            stats[key] += int(month_stats.get(key, 0))
        for title, views in month_entries.items():
            aggregate[title] = aggregate.get(title, 0) + views

    stats["pageviews_unique_terms"] = len(aggregate)
    if months > 0 and stats["pageviews_months_loaded"] == 0:
        raise ValueError(
            "failed to load Wikimedia pageviews data for all requested months; "
            "check network connectivity or reduce --pageviews-months"
        )
    return aggregate, stats


def _parse_jieba_frequency_entries(
    payload: bytes,
    min_hanzi: int,
) -> Tuple[Dict[str, int], Dict[str, str], Dict[str, int]]:
    stats = {
        "jieba_total_lines": 0,
        "jieba_parsed_lines": 0,
        "jieba_invalid_format": 0,
        "jieba_filtered_non_cjk": 0,
        "jieba_filtered_short": 0,
    }
    entries: Dict[str, int] = {}
    pos_tags: Dict[str, str] = {}
    text = _decode_text(payload)

    for raw_line in text.splitlines():
        stats["jieba_total_lines"] += 1
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 2:
            stats["jieba_invalid_format"] += 1
            continue

        word = parts[0].strip()
        if not CJK_FULL_RE.fullmatch(word):
            stats["jieba_filtered_non_cjk"] += 1
            continue
        if _cjk_len(word) < min_hanzi:
            stats["jieba_filtered_short"] += 1
            continue

        try:
            freq = int(parts[1].strip())
        except ValueError:
            stats["jieba_invalid_format"] += 1
            continue

        if freq <= 0:
            continue

        previous = entries.get(word, 0)
        if freq > previous:
            entries[word] = freq
        if len(parts) >= 3:
            pos_tag = _normalize_jieba_pos_tag(parts[2])
            if pos_tag and (word not in pos_tags or freq >= previous):
                pos_tags[word] = pos_tag
        stats["jieba_parsed_lines"] += 1

    stats["jieba_unique_terms"] = len(entries)
    stats["jieba_pos_terms"] = len(pos_tags)
    return entries, pos_tags, stats


def _read_unihan_readings_text(payload: bytes) -> str:
    if not payload.startswith(b"PK"):
        return ""

    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        target_name = ""
        for name in zf.namelist():
            if name.endswith("Unihan_Readings.txt"):
                target_name = name
                break
        if not target_name:
            return ""
        return zf.read(target_name).decode("utf-8", errors="ignore")


def _add_unihan_reading(
    readings_map: Dict[str, Set[str]],
    source_rank_map: Dict[Tuple[str, str], int],
    ch: str,
    pinyin: str,
    source_rank: int,
) -> None:
    if not pinyin:
        return
    readings_map.setdefault(ch, set()).add(pinyin)
    key = (ch, pinyin)
    previous = source_rank_map.get(key, 0)
    if source_rank > previous:
        source_rank_map[key] = source_rank


def _parse_unihan_pinlu_token(token: str) -> Tuple[str, int]:
    value = token.strip()
    if not value:
        return "", 0

    left = value.find("(")
    right = value.find(")")
    if left > 0 and right > left:
        pinyin_raw = value[:left]
        try:
            count = int(value[left + 1 : right])
        except ValueError:
            count = 0
    else:
        pinyin_raw = value
        count = 0

    return _normalize_pinyin_token(pinyin_raw), count


def _load_unihan_readings_detail(
    payload: bytes,
) -> Tuple[Dict[str, str], Dict[str, Set[str]], Dict[Tuple[str, str], int], Dict[str, int]]:
    mandarin_map: Dict[str, str] = {}
    readings_map: Dict[str, Set[str]] = {}
    source_rank_map: Dict[Tuple[str, str], int] = {}
    pinlu_map: Dict[str, int] = {}
    text = _read_unihan_readings_text(payload)
    if not text:
        return mandarin_map, readings_map, source_rank_map, pinlu_map

    pinlu_seen_chars: Set[str] = set()
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        parts = line.split("\t")
        if len(parts) < 3:
            continue
        codepoint, field_name, value = parts[0], parts[1], parts[2]
        if field_name not in {"kMandarin", "kHanyuPinyin", "kHanyuPinlu"}:
            continue
        if not codepoint.startswith("U+"):
            continue

        try:
            ch = chr(int(codepoint[2:], 16))
        except ValueError:
            continue
        if not _is_windows_renderable_cjk_text(ch):
            continue

        if field_name == "kMandarin":
            if ch in pinlu_seen_chars:
                continue
            for part in value.split():
                normalized = _normalize_pinyin_token(part)
                if not normalized:
                    continue
                _add_unihan_reading(
                    readings_map,
                    source_rank_map,
                    ch,
                    normalized,
                    UNIHAN_SOURCE_MANDARIN,
                )
                if ch not in mandarin_map:
                    mandarin_map[ch] = normalized
            continue

        if field_name == "kHanyuPinyin":
            for part in value.replace(";", " ").split():
                rest = part.rsplit(":", 1)[-1]
                if not rest:
                    continue
                for pinyin_raw in rest.split(","):
                    normalized = _normalize_pinyin_token(pinyin_raw)
                    if not normalized:
                        continue
                    _add_unihan_reading(
                        readings_map,
                        source_rank_map,
                        ch,
                        normalized,
                        UNIHAN_SOURCE_HANYU_EXTRA,
                    )
                    if ch not in mandarin_map:
                        mandarin_map[ch] = normalized
            continue

        pinlu_seen_chars.add(ch)
        for part in value.split():
            normalized, pinlu_count = _parse_unihan_pinlu_token(part)
            if not normalized:
                continue
            _add_unihan_reading(
                readings_map,
                source_rank_map,
                ch,
                normalized,
                UNIHAN_SOURCE_PINLU,
            )
            if ch not in mandarin_map:
                mandarin_map[ch] = normalized
            if pinlu_count > 0:
                previous = pinlu_map.get(ch, 0)
                if pinlu_count > previous:
                    pinlu_map[ch] = pinlu_count

    # Keep pragmatic override from historical Unihan import behavior.
    _add_unihan_reading(
        readings_map,
        source_rank_map,
        "嗯",
        "en",
        UNIHAN_SOURCE_PINLU,
    )
    if "嗯" not in mandarin_map:
        mandarin_map["嗯"] = "en"

    return mandarin_map, readings_map, source_rank_map, pinlu_map


def _load_unihan_mandarin_map(payload: bytes) -> Dict[str, str]:
    mandarin_map, _readings_map, _source_rank_map, _pinlu_map = _load_unihan_readings_detail(
        payload
    )
    return mandarin_map


def _parse_unihan_pinlu_count(value: str) -> int:
    max_count = 0
    for matched in re.finditer(r"\((\d+)\)", value):
        try:
            count = int(matched.group(1))
        except ValueError:
            continue
        if count > max_count:
            max_count = count
    return max_count


def _load_unihan_pinlu_map(payload: bytes) -> Dict[str, int]:
    _mandarin_map, _readings_map, _source_rank_map, pinlu_map = _load_unihan_readings_detail(
        payload
    )
    return pinlu_map


def _load_unihan_dictlike_maps(
    payload: bytes,
) -> Tuple[Dict[str, int], Dict[str, int], Dict[str, int]]:
    freq_map: Dict[str, int] = {}
    grade_map: Dict[str, int] = {}
    core_map: Dict[str, int] = {}
    if not payload.startswith(b"PK"):
        return freq_map, grade_map, core_map

    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        target_name = ""
        for name in zf.namelist():
            if name.endswith("Unihan_DictionaryLikeData.txt"):
                target_name = name
                break
        if not target_name:
            return freq_map, grade_map, core_map

        text = zf.read(target_name).decode("utf-8", errors="ignore")

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        codepoint, field_name, value = parts[0], parts[1], parts[2]
        if not codepoint.startswith("U+"):
            continue

        try:
            ch = chr(int(codepoint[2:], 16))
        except ValueError:
            continue
        if not _is_windows_renderable_cjk_text(ch):
            continue

        if field_name == "kFrequency":
            try:
                freq = int(value.strip())
            except ValueError:
                continue
            if freq > 0:
                freq_map[ch] = freq
        elif field_name == "kGradeLevel":
            try:
                grade = int(value.strip())
            except ValueError:
                continue
            if grade > 0:
                grade_map[ch] = grade
        elif field_name == "kUnihanCore2020":
            coverage = 0
            for ch_value in value:
                if ("A" <= ch_value <= "Z") or ("a" <= ch_value <= "z"):
                    coverage += 1
            if coverage > 0:
                core_map[ch] = coverage

    return freq_map, grade_map, core_map


def _load_unihan_simplified_variant_map(payload: bytes) -> Dict[str, str]:
    variant_map: Dict[str, str] = {}
    if not payload.startswith(b"PK"):
        return variant_map

    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        target_name = ""
        for name in zf.namelist():
            if name.endswith("Unihan_Variants.txt"):
                target_name = name
                break
        if not target_name:
            return variant_map
        text = zf.read(target_name).decode("utf-8", errors="ignore")

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        codepoint, field_name, value = parts[0], parts[1], parts[2]
        if field_name != "kSimplifiedVariant":
            continue
        if not codepoint.startswith("U+"):
            continue

        try:
            trad_ch = chr(int(codepoint[2:], 16))
        except ValueError:
            continue
        if not _is_windows_renderable_cjk_text(trad_ch):
            continue

        simp_ch = ""
        for token in value.split():
            token = token.strip()
            if not token.startswith("U+"):
                continue
            try:
                candidate = chr(int(token[2:], 16))
            except ValueError:
                continue
            if not _is_windows_renderable_cjk_text(candidate):
                continue
            # Prefer an actual variant target instead of same-character echo.
            if candidate == trad_ch:
                continue
            simp_ch = candidate
            break
        if not simp_ch:
            continue

        if trad_ch not in variant_map:
            variant_map[trad_ch] = simp_ch

    return variant_map


def _load_unihan_traditional_variant_map(payload: bytes) -> Dict[str, str]:
    variant_map: Dict[str, str] = {}
    if not payload.startswith(b"PK"):
        return variant_map

    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        target_name = ""
        for name in zf.namelist():
            if name.endswith("Unihan_Variants.txt"):
                target_name = name
                break
        if not target_name:
            return variant_map
        text = zf.read(target_name).decode("utf-8", errors="ignore")

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        codepoint, field_name, value = parts[0], parts[1], parts[2]
        if field_name != "kTraditionalVariant":
            continue
        if not codepoint.startswith("U+"):
            continue

        try:
            simp_ch = chr(int(codepoint[2:], 16))
        except ValueError:
            continue
        if not _is_windows_renderable_cjk_text(simp_ch):
            continue

        trad_ch = ""
        for token in value.split():
            token = token.strip()
            if not token.startswith("U+"):
                continue
            try:
                candidate = chr(int(token[2:], 16))
            except ValueError:
                continue
            if not _is_windows_renderable_cjk_text(candidate):
                continue
            # Prefer an actual variant target instead of same-character echo.
            if candidate == simp_ch:
                continue
            trad_ch = candidate
            break
        if not trad_ch:
            continue

        if simp_ch not in variant_map:
            variant_map[simp_ch] = trad_ch

    return variant_map


def _unihan_weight_from_frequency(freq: int) -> int:
    if freq == 1:
        return 118
    if freq == 2:
        return 86
    if freq == 3:
        return 60
    if freq == 4:
        return 38
    if freq == 5:
        return 22
    return 0


def _unihan_weight_from_pinlu(freq: int) -> int:
    if freq <= 0:
        return 0
    ratio = min(1.0, math.log1p(freq) / math.log1p(30000.0))
    return 32 + int(round(ratio * 328))


def _unihan_weight_from_grade(grade: int) -> int:
    if grade == 1:
        return 52
    if grade == 2:
        return 42
    if grade == 3:
        return 34
    if grade == 4:
        return 26
    if grade == 5:
        return 18
    if grade == 6:
        return 12
    return 0


def _unihan_weight_from_core(coverage: int) -> int:
    if coverage <= 0:
        return 0
    capped = min(coverage, 7)
    return 5 + capped * 4


def _compute_unihan_single_char_weight(
    freq: int,
    pinlu_freq: int,
    grade_level: int,
    core_coverage: int,
) -> int:
    weight = 56
    if pinlu_freq > 0:
        weight += _unihan_weight_from_pinlu(pinlu_freq)
    else:
        # Keep non-pinlu characters available with conservative baseline.
        weight += 8
    if freq > 0:
        weight += _unihan_weight_from_frequency(freq)
    if grade_level > 0:
        grade_bonus = _unihan_weight_from_grade(grade_level)
        if pinlu_freq > 0:
            grade_bonus = grade_bonus // 3
        weight += grade_bonus
    if core_coverage > 0:
        core_bonus = _unihan_weight_from_core(core_coverage)
        if pinlu_freq > 0:
            core_bonus = core_bonus // 2
        weight += core_bonus

    if weight < 56:
        return 56
    if weight > 540:
        return 540
    return weight


def _adjust_unihan_weight_for_source(weight: int, source_rank: int) -> int:
    adjusted = weight
    if source_rank >= UNIHAN_SOURCE_PINLU:
        adjusted += 18
    elif source_rank == UNIHAN_SOURCE_MANDARIN:
        adjusted += 6
    else:
        adjusted -= 92

    if source_rank <= UNIHAN_SOURCE_HANYU_EXTRA:
        adjusted = min(adjusted, UNIHAN_HANYU_EXTRA_WEIGHT_CAP)

    if adjusted < 70:
        return 70
    if adjusted > 620:
        return 620
    return adjusted


def _load_pinyin_overrides(path: pathlib.Path) -> Dict[str, str]:
    overrides: Dict[str, str] = {}
    content = path.read_text(encoding="utf-8")
    for line_no, raw_line in enumerate(content.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        parts = line.split("\t")
        if len(parts) < 2:
            raise ValueError(
                f"invalid override format at {path}:{line_no}, expected text<TAB>pinyin"
            )

        text = parts[0].strip()
        if _cjk_len(text) <= 0:
            raise ValueError(
                f"invalid override text at {path}:{line_no}, expected CJK text: '{text}'"
            )

        pinyin = _normalize_pinyin(parts[1])
        if not pinyin:
            raise ValueError(
                f"invalid override pinyin at {path}:{line_no}: '{parts[1]}'"
            )

        previous = overrides.get(text, "")
        if previous and previous != pinyin:
            raise ValueError(
                f"conflicting override at {path}:{line_no} for '{text}': '{previous}' vs '{pinyin}'"
            )
        overrides[text] = pinyin

    return overrides


def _pinyin_from_unihan(text: str, unihan_map: Dict[str, str]) -> str:
    syllables: List[str] = []
    for ch in text:
        if not CJK_RE.match(ch):
            return ""
        py = unihan_map.get(ch, "")
        if not py:
            return ""
        syllables.append(py)

    merged = "".join(syllables)
    if not PINYIN_RE.fullmatch(merged):
        return ""
    return merged


def _build_from_opencc_unihan(
    opencc_text: str,
    unihan_payload: bytes,
    min_hanzi: int,
    overrides: Dict[str, str],
) -> Tuple[Dict[Tuple[str, str], int], Dict[Tuple[str, str], int], Dict[str, int]]:
    sc: Dict[Tuple[str, str], int] = {}
    tc: Dict[Tuple[str, str], int] = {}
    opencc_entries, stats = _parse_opencc_entries(opencc_text, min_hanzi)
    sc_terms = {sc_word for sc_word, _tc_word in opencc_entries}
    tc_terms = {tc_word for _sc_word, tc_word in opencc_entries}
    (
        unihan_map,
        unihan_readings_map,
        unihan_reading_source_map,
        unihan_pinlu_map,
    ) = _load_unihan_readings_detail(unihan_payload)
    unihan_freq_map, unihan_grade_map, unihan_core_map = _load_unihan_dictlike_maps(unihan_payload)
    stats["unihan_map_size"] = len(unihan_map)
    stats["unihan_readings_chars"] = len(unihan_readings_map)
    stats["unihan_readings_pairs"] = sum(len(values) for values in unihan_readings_map.values())
    stats["unihan_pinlu_size"] = len(unihan_pinlu_map)
    stats["unihan_frequency_size"] = len(unihan_freq_map)
    stats["unihan_grade_size"] = len(unihan_grade_map)
    stats["unihan_core_size"] = len(unihan_core_map)
    stats["invalid_pinyin"] = 0
    stats["override_entries"] = len(overrides)
    stats["override_hits"] = 0
    stats["fallback_hits"] = 0
    stats["override_injected"] = 0
    stats["unihan_single_char_injected_sc"] = 0
    stats["unihan_single_char_injected_tc"] = 0

    for sc_word, tc_word in opencc_entries:
        for text, bucket in ((sc_word, sc), (tc_word, tc)):
            if _cjk_len(text) < min_hanzi:
                continue
            pinyin = overrides.get(text, "")
            if pinyin:
                stats["override_hits"] += 1
            else:
                pinyin = _pinyin_from_unihan(text, unihan_map)
                if pinyin:
                    stats["fallback_hits"] += 1
            if not pinyin:
                stats["invalid_pinyin"] += 1
                continue

            key = (pinyin, text)
            weight = _compute_weight(text)
            previous = bucket.get(key, 0)
            if weight > previous:
                bucket[key] = weight

    # Ensure override entries are included even when source phrase lists do not contain them.
    for text, pinyin in overrides.items():
        if _cjk_len(text) < min_hanzi:
            continue
        key = (pinyin, text)
        # Explicit overrides should be easier to surface in top candidates.
        weight = min(1000, _compute_weight(text) + 80)
        if (text in sc_terms) and (text not in tc_terms):
            target_buckets = (sc,)
        elif (text in tc_terms) and (text not in sc_terms):
            target_buckets = (tc,)
        elif (text in sc_terms) and (text in tc_terms):
            target_buckets = (sc,)
        else:
            target_buckets = (sc, tc)

        for bucket in target_buckets:
            previous = bucket.get(key, 0)
            if weight > previous:
                bucket[key] = weight
                stats["override_injected"] += 1

    # Inject Unihan single-character entries when min_hanzi allows them.
    # This keeps single-char ranking logic centralized in lexicon pipeline.
    if min_hanzi <= 1:
        for ch, pinyin_set in unihan_readings_map.items():
            if _cjk_len(ch) != 1:
                continue
            if not pinyin_set:
                continue
            base_weight = _compute_unihan_single_char_weight(
                freq=unihan_freq_map.get(ch, 0),
                pinlu_freq=unihan_pinlu_map.get(ch, 0),
                grade_level=unihan_grade_map.get(ch, 0),
                core_coverage=unihan_core_map.get(ch, 0),
            )

            # Keep script buckets separated when OpenCC mapping is explicit.
            if (ch in sc_terms) and (ch not in tc_terms):
                target_buckets = (sc,)
            elif (ch in tc_terms) and (ch not in sc_terms):
                target_buckets = (tc,)
            else:
                target_buckets = (sc, tc)

            for pinyin in sorted(pinyin_set):
                key = (pinyin, ch)
                source_rank = unihan_reading_source_map.get((ch, pinyin), UNIHAN_SOURCE_MANDARIN)
                output_weight = _adjust_unihan_weight_for_source(base_weight, source_rank)

                for bucket in target_buckets:
                    previous = bucket.get(key, 0)
                    if output_weight > previous:
                        bucket[key] = output_weight
                        if bucket is sc:
                            stats["unihan_single_char_injected_sc"] += 1
                        else:
                            stats["unihan_single_char_injected_tc"] += 1

    return sc, tc, stats


def _build_from_unihan_only(
    unihan_payload: bytes,
    min_hanzi: int,
    overrides: Dict[str, str],
    trad_to_simp_char_map: Dict[str, str],
    simp_to_trad_char_map: Dict[str, str],
    sc_chars: Set[str],
    tc_chars: Set[str],
) -> Tuple[Dict[Tuple[str, str], int], Dict[Tuple[str, str], int], Dict[str, int]]:
    sc: Dict[Tuple[str, str], int] = {}
    tc: Dict[Tuple[str, str], int] = {}
    (
        _unihan_map,
        unihan_readings_map,
        unihan_reading_source_map,
        unihan_pinlu_map,
    ) = _load_unihan_readings_detail(unihan_payload)
    unihan_freq_map, unihan_grade_map, unihan_core_map = _load_unihan_dictlike_maps(unihan_payload)

    stats: Dict[str, int] = {
        "unihan_map_size": len(unihan_readings_map),
        "unihan_readings_chars": len(unihan_readings_map),
        "unihan_readings_pairs": sum(len(values) for values in unihan_readings_map.values()),
        "unihan_pinlu_size": len(unihan_pinlu_map),
        "unihan_frequency_size": len(unihan_freq_map),
        "unihan_grade_size": len(unihan_grade_map),
        "unihan_core_size": len(unihan_core_map),
        "override_entries": len(overrides),
        "override_hits": 0,
        "override_injected": 0,
        "unihan_single_char_injected_sc": 0,
        "unihan_single_char_injected_tc": 0,
        "unihan_tc_only_chars": 0,
        "unihan_sc_only_chars": 0,
    }

    tc_only_chars = tc_chars.difference(sc_chars)
    sc_only_chars = sc_chars.difference(tc_chars)

    if min_hanzi <= 1:
        for ch, pinyin_set in unihan_readings_map.items():
            if _cjk_len(ch) != 1:
                continue
            if not pinyin_set:
                continue

            base_weight = _compute_unihan_single_char_weight(
                freq=unihan_freq_map.get(ch, 0),
                pinlu_freq=unihan_pinlu_map.get(ch, 0),
                grade_level=unihan_grade_map.get(ch, 0),
                core_coverage=unihan_core_map.get(ch, 0),
            )

            for pinyin in sorted(pinyin_set):
                source_rank = unihan_reading_source_map.get((ch, pinyin), UNIHAN_SOURCE_MANDARIN)
                output_weight = _adjust_unihan_weight_for_source(base_weight, source_rank)
                key = (pinyin, ch)
                if ch in tc_only_chars:
                    previous_tc = tc.get(key, 0)
                    if output_weight > previous_tc:
                        tc[key] = output_weight
                        stats["unihan_single_char_injected_tc"] += 1
                        stats["unihan_tc_only_chars"] += 1
                elif ch in sc_only_chars:
                    previous_sc = sc.get(key, 0)
                    if output_weight > previous_sc:
                        sc[key] = output_weight
                        stats["unihan_single_char_injected_sc"] += 1
                        stats["unihan_sc_only_chars"] += 1
                else:
                    previous_sc = sc.get(key, 0)
                    if output_weight > previous_sc:
                        sc[key] = output_weight
                        stats["unihan_single_char_injected_sc"] += 1

                    previous_tc = tc.get(key, 0)
                    if output_weight > previous_tc:
                        tc[key] = output_weight
                        stats["unihan_single_char_injected_tc"] += 1

    for text, pinyin in overrides.items():
        if _cjk_len(text) != 1:
            continue
        if min_hanzi > 1:
            continue

        base_weight = _compute_unihan_single_char_weight(
            freq=unihan_freq_map.get(text, 0),
            pinlu_freq=unihan_pinlu_map.get(text, 0),
            grade_level=unihan_grade_map.get(text, 0),
            core_coverage=unihan_core_map.get(text, 0),
        )
        key = (pinyin, text)
        output_weight = min(700, base_weight + 70)

        if text in tc_only_chars:
            previous_tc = tc.get(key, 0)
            if output_weight > previous_tc:
                tc[key] = output_weight
                stats["override_injected"] += 1
        elif text in sc_only_chars:
            previous_sc = sc.get(key, 0)
            if output_weight > previous_sc:
                sc[key] = output_weight
                stats["override_injected"] += 1
        else:
            previous_sc = sc.get(key, 0)
            if output_weight > previous_sc:
                sc[key] = output_weight
                stats["override_injected"] += 1

            previous_tc = tc.get(key, 0)
            if output_weight > previous_tc:
                tc[key] = output_weight
                stats["override_injected"] += 1

        stats["override_hits"] += 1

    if trad_to_simp_char_map:
        sc, normalize_stats = _normalize_sc_mapping_with_char_map(
            sc, trad_to_simp_char_map, simp_to_trad_char_map
        )
        stats.update(normalize_stats)
    if simp_to_trad_char_map:
        tc, normalize_stats = _normalize_tc_mapping_with_char_map(tc, simp_to_trad_char_map)
        stats.update(normalize_stats)

    sc, sc_script_stats = _filter_sc_mapping_with_script_hints(sc, sc_chars, tc_chars)
    stats.update(sc_script_stats)
    tc, tc_script_stats = _filter_tc_mapping_with_script_hints(tc, sc_chars, tc_chars)
    stats.update(tc_script_stats)

    return sc, tc, stats


def _build_text_pinyin_index(
    sc: Dict[Tuple[str, str], int],
    tc: Dict[Tuple[str, str], int],
) -> Dict[str, Set[str]]:
    index: Dict[str, Set[str]] = {}

    for pinyin, text in sc.keys():
        index.setdefault(text, set()).add(pinyin)
    for pinyin, text in tc.keys():
        index.setdefault(text, set()).add(pinyin)

    return index


def _build_opencc_sc_to_tc_map(opencc_entries: List[Tuple[str, str]]) -> Dict[str, Set[str]]:
    mapping: Dict[str, Set[str]] = {}
    for sc_word, tc_word in opencc_entries:
        if not sc_word or not tc_word:
            continue
        mapping.setdefault(sc_word, set()).add(tc_word)
    return mapping


def _build_opencc_tc_to_sc_map(opencc_entries: List[Tuple[str, str]]) -> Dict[str, Set[str]]:
    mapping: Dict[str, Set[str]] = {}
    for sc_word, tc_word in opencc_entries:
        if not sc_word or not tc_word:
            continue
        mapping.setdefault(tc_word, set()).add(sc_word)
    return mapping


def _build_cedict_tc_to_sc_map(source_text: str, min_hanzi: int) -> Dict[str, Set[str]]:
    mapping: Dict[str, Set[str]] = {}
    for raw_line in source_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        matched = CEDICT_LINE_RE.match(line)
        if not matched:
            continue
        trad, simp, _pinyin_raw, _defs = matched.groups()
        if _cjk_len(trad) < min_hanzi or _cjk_len(simp) < min_hanzi:
            continue
        if trad == simp:
            continue
        mapping.setdefault(trad, set()).add(simp)
    return mapping


def _merge_tc_to_sc_maps(*maps: Dict[str, Set[str]]) -> Dict[str, Set[str]]:
    merged: Dict[str, Set[str]] = {}
    for mapping in maps:
        for tc_word, sc_words in mapping.items():
            if not sc_words:
                continue
            bucket = merged.setdefault(tc_word, set())
            bucket.update(sc_words)
    return merged


def _build_char_variant_hints(
    tc_to_sc_map: Dict[str, Set[str]],
    opencc_entries: List[Tuple[str, str]],
) -> Tuple[Dict[str, str], Dict[str, str], Set[str], Set[str]]:
    # Build char-level hints from known word-level SC/TC alignments.
    # Used for:
    # 1) script split in unihan_single generation
    # 2) SC-side cleanup in broad profile.
    pair_counts: Dict[Tuple[str, str], int] = {}
    tc_identity_counts: Dict[str, int] = {}
    sc_identity_counts: Dict[str, int] = {}
    sc_chars: Set[str] = set()
    tc_chars: Set[str] = set()

    def add_pair(tc_word: str, sc_word: str) -> None:
        if len(tc_word) != len(sc_word):
            return
        for tc_ch, sc_ch in zip(tc_word, sc_word):
            if not CJK_FULL_RE.fullmatch(tc_ch):
                continue
            if not CJK_FULL_RE.fullmatch(sc_ch):
                continue
            tc_chars.add(tc_ch)
            sc_chars.add(sc_ch)
            if tc_ch == sc_ch:
                tc_identity_counts[tc_ch] = tc_identity_counts.get(tc_ch, 0) + 1
                sc_identity_counts[sc_ch] = sc_identity_counts.get(sc_ch, 0) + 1
                continue
            key = (tc_ch, sc_ch)
            pair_counts[key] = pair_counts.get(key, 0) + 1

    for sc_word, tc_word in opencc_entries:
        add_pair(tc_word, sc_word)
    for tc_word, sc_words in tc_to_sc_map.items():
        for sc_word in sc_words:
            add_pair(tc_word, sc_word)

    trad_to_simp: Dict[str, str] = {}
    per_tc: Dict[str, List[Tuple[int, str]]] = {}
    for (tc_ch, sc_ch), count in pair_counts.items():
        per_tc.setdefault(tc_ch, []).append((count, sc_ch))
    for tc_ch, candidates in per_tc.items():
        candidates.sort(key=lambda item: (-item[0], item[1]))
        best_count, best_sc = candidates[0]
        second_count = candidates[1][0] if len(candidates) > 1 else 0
        same_count = tc_identity_counts.get(tc_ch, 0)
        # Avoid overfitting lexicalized phrase-level replacements (for example 待->呆 in 待著->呆着).
        # Only keep a TC->SC char hint when evidence is strong enough.
        if best_count < 2:
            continue
        if best_count <= same_count:
            continue
        if best_count <= second_count:
            continue
        trad_to_simp[tc_ch] = best_sc

    simp_to_trad: Dict[str, str] = {}
    per_sc: Dict[str, List[Tuple[int, str]]] = {}
    for (tc_ch, sc_ch), count in pair_counts.items():
        per_sc.setdefault(sc_ch, []).append((count, tc_ch))
    for sc_ch, candidates in per_sc.items():
        candidates.sort(key=lambda item: (-item[0], item[1]))
        best_count, best_tc = candidates[0]
        second_count = candidates[1][0] if len(candidates) > 1 else 0
        same_count = sc_identity_counts.get(sc_ch, 0)
        if best_count < 2:
            continue
        if best_count <= same_count:
            continue
        if best_count <= second_count:
            continue
        simp_to_trad[sc_ch] = best_tc

    return trad_to_simp, simp_to_trad, sc_chars, tc_chars


def _normalize_sc_mapping_with_char_map(
    mapping: Dict[Tuple[str, str], int],
    trad_to_simp_char_map: Dict[str, str],
    simp_to_trad_char_map: Dict[str, str] | None = None,
) -> Tuple[Dict[Tuple[str, str], int], Dict[str, int]]:
    simp_to_trad_char_map = simp_to_trad_char_map or {}
    if not trad_to_simp_char_map:
        return mapping, {
            "sc_char_normalized_converted_entries": 0,
            "sc_char_normalized_total_entries": len(mapping),
            "sc_char_normalized_blocked_reverse_entries": 0,
        }

    normalized: Dict[Tuple[str, str], int] = {}
    converted_entries = 0
    blocked_reverse_entries = 0

    for (pinyin, text), weight in mapping.items():
        converted_chars: List[str] = []
        changed = False
        for ch in text:
            replacement = trad_to_simp_char_map.get(ch, ch)
            # Guardrail: do not rewrite a known simplified form into a
            # traditional/variant form (for example 么 -> 幺).
            if replacement != ch and ch in simp_to_trad_char_map:
                replacement = ch
                blocked_reverse_entries += 1
            if replacement != ch:
                changed = True
            converted_chars.append(replacement)
        output_text = "".join(converted_chars)
        if changed:
            converted_entries += 1

        key = (pinyin, output_text)
        previous = normalized.get(key, 0)
        if weight > previous:
            normalized[key] = weight

    stats = {
        "sc_char_normalized_converted_entries": converted_entries,
        "sc_char_normalized_total_entries": len(normalized),
        "sc_char_normalized_blocked_reverse_entries": blocked_reverse_entries,
    }
    return normalized, stats


def _filter_sc_mapping_with_script_hints(
    mapping: Dict[Tuple[str, str], int],
    sc_chars: Set[str],
    tc_chars: Set[str],
) -> Tuple[Dict[Tuple[str, str], int], Dict[str, int]]:
    filtered: Dict[Tuple[str, str], int] = {}
    dropped_entries = 0
    tc_only_chars = tc_chars.difference(sc_chars)

    if not tc_only_chars:
        return mapping, {
            "sc_script_filtered_entries": 0,
            "sc_script_filtered_total_entries": len(mapping),
        }

    for key, weight in mapping.items():
        _pinyin, text = key
        drop = False
        for ch in text:
            if ch in tc_only_chars:
                drop = True
                break
        if drop:
            dropped_entries += 1
            continue
        filtered[key] = weight

    stats = {
        "sc_script_filtered_entries": dropped_entries,
        "sc_script_filtered_total_entries": len(filtered),
    }
    return filtered, stats


def _normalize_tc_mapping_with_char_map(
    mapping: Dict[Tuple[str, str], int],
    simp_to_trad_char_map: Dict[str, str],
) -> Tuple[Dict[Tuple[str, str], int], Dict[str, int]]:
    if not simp_to_trad_char_map:
        return mapping, {
            "tc_char_normalized_converted_entries": 0,
            "tc_char_normalized_total_entries": len(mapping),
        }

    normalized: Dict[Tuple[str, str], int] = {}
    converted_entries = 0

    for (pinyin, text), weight in mapping.items():
        converted_chars: List[str] = []
        changed = False
        for ch in text:
            replacement = simp_to_trad_char_map.get(ch, ch)
            if replacement != ch:
                changed = True
            converted_chars.append(replacement)
        output_text = "".join(converted_chars)
        if changed:
            converted_entries += 1

        key = (pinyin, output_text)
        previous = normalized.get(key, 0)
        if weight > previous:
            normalized[key] = weight

    stats = {
        "tc_char_normalized_converted_entries": converted_entries,
        "tc_char_normalized_total_entries": len(normalized),
    }
    return normalized, stats


def _filter_tc_mapping_with_script_hints(
    mapping: Dict[Tuple[str, str], int],
    sc_chars: Set[str],
    tc_chars: Set[str],
) -> Tuple[Dict[Tuple[str, str], int], Dict[str, int]]:
    filtered: Dict[Tuple[str, str], int] = {}
    dropped_entries = 0
    sc_only_chars = sc_chars.difference(tc_chars)

    if not sc_only_chars:
        return mapping, {
            "tc_script_filtered_entries": 0,
            "tc_script_filtered_total_entries": len(mapping),
        }

    for key, weight in mapping.items():
        _pinyin, text = key
        drop = False
        for ch in text:
            if ch in sc_only_chars:
                drop = True
                break
        if drop:
            dropped_entries += 1
            continue
        filtered[key] = weight

    stats = {
        "tc_script_filtered_entries": dropped_entries,
        "tc_script_filtered_total_entries": len(filtered),
    }
    return filtered, stats


def _normalize_pageviews_entries_to_sc(
    pageviews_entries: Dict[str, int],
    tc_to_sc_map: Dict[str, Set[str]],
) -> Dict[str, int]:
    normalized: Dict[str, int] = {}
    for word, views in pageviews_entries.items():
        if views <= 0:
            continue
        mapped_sc = tc_to_sc_map.get(word, set())
        if mapped_sc:
            for sc_word in mapped_sc:
                normalized[sc_word] = normalized.get(sc_word, 0) + views
        else:
            normalized[word] = normalized.get(word, 0) + views
    return normalized


def _normalize_sc_mapping_with_opencc(
    sc_map: Dict[Tuple[str, str], int],
    tc_to_sc_map: Dict[str, Set[str]],
) -> Tuple[Dict[Tuple[str, str], int], Dict[str, int]]:
    normalized: Dict[Tuple[str, str], int] = {}
    converted_entries = 0

    for (pinyin, text), weight in sc_map.items():
        mapped_sc = tc_to_sc_map.get(text, set())
        if mapped_sc:
            converted_entries += 1
            targets = mapped_sc
        else:
            targets = {text}

        for target in targets:
            key = (pinyin, target)
            previous = normalized.get(key, 0)
            if weight > previous:
                normalized[key] = weight

    stats = {
        "sc_normalized_converted_entries": converted_entries,
        "sc_normalized_total_entries": len(normalized),
    }
    return normalized, stats


def _build_thuocl_frequency_map(
    max_df_map: Dict[str, int],
    coverage_map: Dict[str, int],
) -> Dict[str, int]:
    normalized: Dict[str, int] = {}
    for word, max_df in max_df_map.items():
        if max_df <= 0:
            continue
        coverage = max(1, coverage_map.get(word, 1))
        # Keep only cross-list terms to suppress domain-specific tails.
        if coverage < 2:
            continue
        # Reward broader cross-list consensus.
        coverage_factor = 0.62 + 0.14 * min(coverage, 5)
        normalized[word] = max(1, int(round(max_df * coverage_factor)))
    return normalized


def _percentile(values: List[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    ratio = min(1.0, max(0.0, percentile / 100.0))
    index = int(math.ceil(ratio * len(ordered))) - 1
    index = max(0, min(index, len(ordered) - 1))
    return ordered[index]


def _build_normalized_signal_map(
    source_frequency_map: Dict[str, int],
    percentile: float = 99.0,
) -> Dict[str, float]:
    values: List[float] = []
    for freq in source_frequency_map.values():
        if freq > 0:
            values.append(math.log1p(freq))
    cap = _percentile(values, percentile)
    if cap <= 0:
        return {}

    normalized: Dict[str, float] = {}
    for word, freq in source_frequency_map.items():
        if freq <= 0:
            continue
        score = math.log1p(freq) / cap
        normalized[word] = min(1.0, max(0.0, score))
    return normalized


def _build_direct_frequency_signal_map(
    source_frequency_map: Dict[str, int],
    power: float = 3.0,
) -> Dict[str, float]:
    """
    Build a strict frequency signal from raw counts.

    This keeps very frequent daily terms clearly separated from low-frequency
    tails inside same-pinyin buckets.
    """
    max_log = 0.0
    for freq in source_frequency_map.values():
        if freq <= 0:
            continue
        value = math.log1p(freq)
        if value > max_log:
            max_log = value

    if max_log <= 0.0:
        return {}

    shaped_power = max(1.0, float(power))
    normalized: Dict[str, float] = {}
    for word, freq in source_frequency_map.items():
        if freq <= 0:
            continue
        ratio = min(1.0, max(0.0, math.log1p(freq) / max_log))
        normalized[word] = ratio**shaped_power
    return normalized


def _build_char_frequency_prior(
    source_frequency_map: Dict[str, int],
    power: float = 1.6,
) -> Dict[str, float]:
    """
    Build a character-level prior from lexical frequencies.

    This helps same-pinyin short-word ordering (e.g. 不对 vs 部队) reflect
    common character usage, while still remaining data-driven.
    """
    char_raw: Dict[str, int] = {}
    for word, freq in source_frequency_map.items():
        if freq <= 0:
            continue
        for ch in word:
            if not CJK_FULL_RE.fullmatch(ch):
                continue
            char_raw[ch] = char_raw.get(ch, 0) + freq

    if not char_raw:
        return {}

    max_log = 0.0
    for value in char_raw.values():
        if value <= 0:
            continue
        log_value = math.log1p(value)
        if log_value > max_log:
            max_log = log_value
    if max_log <= 0.0:
        return {}

    shaped_power = max(1.0, float(power))
    prior: Dict[str, float] = {}
    for ch, value in char_raw.items():
        ratio = min(1.0, max(0.0, math.log1p(value) / max_log))
        prior[ch] = ratio**shaped_power
    return prior


def _build_usage_signal_map(
    thuocl_signal_map: Dict[str, float],
    jieba_signal_map: Dict[str, float],
    pageviews_signal_map: Dict[str, float],
    jieba_pos_map: Dict[str, str] | None = None,
    jieba_direct_signal_map: Dict[str, float] | None = None,
) -> Tuple[Dict[str, float], Dict[str, int]]:
    # Source weights reflect relative robustness of the signals:
    # THUOCL consensus DF, jieba lexical frequency, and Wikipedia usage heat.
    source_weights = {
        "thuocl": 0.46,
        "jieba": 0.31,
        "pageviews": 0.23,
    }
    consensus_step = 0.12

    usage_score_map: Dict[str, float] = {}
    source_hits_map: Dict[str, int] = {}
    jieba_pos_map = jieba_pos_map or {}
    jieba_direct_signal_map = jieba_direct_signal_map or {}

    all_terms = set(thuocl_signal_map.keys())
    all_terms.update(jieba_signal_map.keys())
    all_terms.update(pageviews_signal_map.keys())
    for term in all_terms:
        thuocl_score = thuocl_signal_map.get(term, 0.0)
        jieba_score = jieba_signal_map.get(term, 0.0)
        pageviews_score = pageviews_signal_map.get(term, 0.0)
        thuocl_hit = thuocl_score >= 0.10
        jieba_hit = jieba_score >= 0.06
        pageviews_hit = pageviews_score >= 0.05
        source_hits = int(thuocl_hit) + int(jieba_hit) + int(pageviews_hit)
        if source_hits <= 0:
            continue

        score = (
            source_weights["thuocl"] * thuocl_score
            + source_weights["jieba"] * jieba_score
            + source_weights["pageviews"] * pageviews_score
        )
        if source_hits > 1:
            score += consensus_step * (source_hits - 1)

        # Source-consensus shaping:
        # single-source words tend to include noisy transliterations/domain terms,
        # while robust daily vocabulary is usually supported by multiple signals.
        if source_hits == 1:
            if pageviews_hit and (not thuocl_hit) and (not jieba_hit):
                # Wiki top-only words are often named entities.
                score *= 0.55
            elif jieba_hit and (not thuocl_hit) and (not pageviews_hit):
                # Jieba-only terms include many low-priority lexicon tails.
                score *= 0.72
            else:
                # THUOCL-only still keeps better trust than other single-source terms.
                score *= 0.82
        elif source_hits == 2:
            score *= 0.88
        else:
            score *= 1.00

        pos_tag = jieba_pos_map.get(term, "")
        if _is_named_entity_pos(pos_tag):
            jieba_direct_score = min(1.0, max(0.0, jieba_direct_signal_map.get(term, 0.0)))
            # Named entities are useful, but web/wiki popularity alone can
            # over-promote proper nouns for IME general typing.
            # Use strict direct-frequency gates to keep only high-utility names
            # near the top by default.
            if jieba_direct_score < 0.02:
                score *= 0.22
            elif jieba_direct_score < 0.05:
                score *= 0.32
            elif jieba_direct_score < 0.10:
                score *= 0.46
            elif jieba_direct_score < 0.18:
                score *= 0.62
            else:
                score *= 0.80

            if (
                pageviews_score >= 0.30
                and source_hits >= 2
                and jieba_direct_score >= 0.12
            ):
                score *= 1.08
            elif (
                pageviews_score >= 0.20
                and source_hits >= 2
                and jieba_direct_score >= 0.08
            ):
                score *= 1.00
            else:
                score *= 0.96

        usage_score_map[term] = min(1.0, max(0.0, score))
        source_hits_map[term] = source_hits

    return usage_score_map, source_hits_map


def _build_tc_signal_map(
    source_signal_map: Dict[str, float],
    tc_to_sc_map: Dict[str, Set[str]],
) -> Dict[str, float]:
    tc_signal: Dict[str, float] = {}

    for sc_word, signal in source_signal_map.items():
        if signal <= 0.0:
            continue
        previous_sc = tc_signal.get(sc_word, 0.0)
        if signal > previous_sc:
            tc_signal[sc_word] = signal

    for tc_word, sc_words in tc_to_sc_map.items():
        best = tc_signal.get(tc_word, 0.0)
        for sc_word in sc_words:
            signal = source_signal_map.get(sc_word, 0.0)
            if signal > best:
                best = signal
        if best > 0.0:
            tc_signal[tc_word] = best

    return tc_signal


def _build_tc_source_hits_map(
    source_hits_map: Dict[str, int],
    tc_to_sc_map: Dict[str, Set[str]],
) -> Dict[str, int]:
    tc_hits: Dict[str, int] = {}

    for sc_word, hits in source_hits_map.items():
        if hits <= 0:
            continue
        previous_sc = tc_hits.get(sc_word, 0)
        if hits > previous_sc:
            tc_hits[sc_word] = hits

    for tc_word, sc_words in tc_to_sc_map.items():
        best = tc_hits.get(tc_word, 0)
        for sc_word in sc_words:
            hits = source_hits_map.get(sc_word, 0)
            if hits > best:
                best = hits
        if best > 0:
            tc_hits[tc_word] = best

    return tc_hits


def _build_tc_pos_map(
    source_pos_map: Dict[str, str],
    tc_to_sc_map: Dict[str, Set[str]],
) -> Dict[str, str]:
    tc_pos: Dict[str, str] = {}

    for sc_word, pos_tag in source_pos_map.items():
        if not pos_tag:
            continue
        if sc_word not in tc_pos:
            tc_pos[sc_word] = pos_tag

    for tc_word, sc_words in tc_to_sc_map.items():
        best_tag = tc_pos.get(tc_word, "")
        for sc_word in sc_words:
            pos_tag = source_pos_map.get(sc_word, "")
            if not pos_tag:
                continue
            if not best_tag or len(pos_tag) > len(best_tag):
                best_tag = pos_tag
        if best_tag:
            tc_pos[tc_word] = best_tag

    return tc_pos


def _rescore_mapping_with_signals(
    mapping: Dict[Tuple[str, str], int],
    usage_score_map: Dict[str, float],
    source_hits_map: Dict[str, int],
    pageviews_signal_map: Dict[str, float],
    wiki_titles: Set[str],
    jieba_direct_signal_map: Dict[str, float] | None,
    jieba_pos_map: Dict[str, str] | None,
    char_frequency_prior: Dict[str, float] | None,
    core_entry: bool,
    stats_prefix: str,
) -> Dict[str, int]:
    stats = {
        f"{stats_prefix}_rescored": 0,
        f"{stats_prefix}_usage_hits": 0,
        f"{stats_prefix}_multi_source_hits": 0,
        f"{stats_prefix}_pageviews_hits": 0,
        f"{stats_prefix}_wiki_hits": 0,
        f"{stats_prefix}_named_entity_penalized": 0,
        f"{stats_prefix}_single_char_adjusted": 0,
    }
    jieba_direct_signal_map = jieba_direct_signal_map or {}
    jieba_pos_map = jieba_pos_map or {}
    char_prior = _build_effective_char_prior(mapping, char_frequency_prior)
    for key in list(mapping.keys()):
        _pinyin, text = key
        usage_score = usage_score_map.get(text, 0.0)
        source_hits = source_hits_map.get(text, 0)
        pageviews_score = pageviews_signal_map.get(text, 0.0)
        wiki_hit = _has_effective_wiki_support(
            text,
            wiki_titles,
            pageview_score=pageviews_score,
            source_hits=source_hits,
        )
        jieba_direct_score = min(1.0, max(0.0, jieba_direct_signal_map.get(text, 0.0)))
        pos_tag = jieba_pos_map.get(text, "")
        char_score = _compute_text_single_char_prior(text, char_prior)
        weight = _compute_weight_with_signals(
            text,
            usage_score=usage_score,
            source_hits=source_hits,
            pageview_score=pageviews_score,
            wiki_hit=wiki_hit,
            core_entry=core_entry,
            jieba_direct_score=jieba_direct_score,
            pos_tag=pos_tag,
            char_score=char_score,
        )
        text_len = _cjk_len(text)
        if text_len == 1:
            if char_score >= 0.88:
                weight = min(1000, weight + 180)
                stats[f"{stats_prefix}_single_char_adjusted"] += 1
            elif char_score >= 0.76:
                weight = min(1000, weight + 110)
                stats[f"{stats_prefix}_single_char_adjusted"] += 1
            elif (
                char_score <= 0.06
                and usage_score < 0.03
                and jieba_direct_score < 0.03
                and source_hits <= 1
                and pageviews_score < 0.02
            ):
                weight = max(1, weight - 240)
                stats[f"{stats_prefix}_single_char_adjusted"] += 1
            elif (
                char_score <= 0.12
                and usage_score < 0.05
                and jieba_direct_score < 0.05
                and source_hits <= 1
                and pageviews_score < 0.03
            ):
                weight = max(1, weight - 140)
                stats[f"{stats_prefix}_single_char_adjusted"] += 1
        if _is_named_entity_pos(pos_tag):
            if source_hits <= 2 and pageviews_score < 0.08 and jieba_direct_score < 0.12:
                penalty = 68 if text_len <= 2 else (44 if text_len <= 4 else 28)
                weight = max(1, weight - penalty)
                stats[f"{stats_prefix}_named_entity_penalized"] += 1

        if mapping[key] != weight:
            stats[f"{stats_prefix}_rescored"] += 1
            mapping[key] = weight
        if usage_score > 0.0:
            stats[f"{stats_prefix}_usage_hits"] += 1
        if source_hits > 1:
            stats[f"{stats_prefix}_multi_source_hits"] += 1
        if pageviews_score > 0.0:
            stats[f"{stats_prefix}_pageviews_hits"] += 1
        if wiki_hit:
            stats[f"{stats_prefix}_wiki_hits"] += 1

    return stats


def _augment_with_frequency_lexicon(
    sc: Dict[Tuple[str, str], int],
    tc: Dict[Tuple[str, str], int],
    usage_score_map: Dict[str, float],
    source_hits_map: Dict[str, int],
    pageviews_signal_map: Dict[str, float],
    jieba_direct_signal_map: Dict[str, float],
    jieba_pos_map: Dict[str, str],
    char_frequency_prior: Dict[str, float],
    opencc_entries: List[Tuple[str, str]],
    tc_to_sc_map: Dict[str, Set[str]],
    unihan_map: Dict[str, str],
    wiki_titles: Set[str],
    min_hanzi: int,
) -> Dict[str, int]:
    stats = {
        "freqlex_terms_total": 0,
        "freqlex_terms_added_sc": 0,
        "freqlex_terms_boosted_sc": 0,
        "freqlex_terms_added_tc": 0,
        "freqlex_terms_boosted_tc": 0,
        "freqlex_skipped_short": 0,
        "freqlex_skipped_non_cjk": 0,
        "freqlex_skipped_no_pinyin": 0,
        "freqlex_skipped_weak_fallback": 0,
        "freqlex_existing_pinyin_hits": 0,
        "freqlex_unihan_fallback_hits": 0,
        "freqlex_opencc_tc_hits": 0,
    }

    opencc_sc_to_tc = _build_opencc_sc_to_tc_map(opencc_entries)
    pinyin_index = _build_text_pinyin_index(sc, tc)
    tc_existing_texts = {text for _pinyin, text in tc.keys()}
    char_prior = _build_effective_char_prior(sc, char_frequency_prior)

    for word, usage_score in usage_score_map.items():
        stats["freqlex_terms_total"] += 1

        if not CJK_FULL_RE.fullmatch(word):
            stats["freqlex_skipped_non_cjk"] += 1
            continue
        if _cjk_len(word) < min_hanzi:
            stats["freqlex_skipped_short"] += 1
            continue

        pinyin_candidates = sorted(pinyin_index.get(word, set()))
        if pinyin_candidates:
            stats["freqlex_existing_pinyin_hits"] += 1
        else:
            fallback = _pinyin_from_unihan(word, unihan_map)
            if not fallback:
                stats["freqlex_skipped_no_pinyin"] += 1
                continue
            source_hits = source_hits_map.get(word, 0)
            pageview_score = pageviews_signal_map.get(word, 0.0)
            # Unihan fallback can generate many low-value pseudo-words.
            # Keep only strongly supported terms when no curated pinyin source exists.
            hanzi_len = _cjk_len(word)
            if hanzi_len <= 2:
                allow_fallback = (
                    usage_score >= 0.42 or source_hits >= 2 or pageview_score >= 0.15
                )
            elif hanzi_len <= 4:
                allow_fallback = (
                    usage_score >= 0.20 or source_hits >= 2 or pageview_score >= 0.10
                )
            else:
                allow_fallback = (
                    usage_score >= 0.12 or source_hits >= 1 or pageview_score >= 0.06
                )
            if not allow_fallback:
                stats["freqlex_skipped_weak_fallback"] += 1
                continue
            pinyin_candidates = [fallback]
            stats["freqlex_unihan_fallback_hits"] += 1

        source_hits = source_hits_map.get(word, 0)
        pageview_score = pageviews_signal_map.get(word, 0.0)
        jieba_direct_score = min(1.0, max(0.0, jieba_direct_signal_map.get(word, 0.0)))
        pos_tag = jieba_pos_map.get(word, "")
        char_score = _compute_text_single_char_prior(word, char_prior)
        weight = _compute_weight_with_signals(
            word,
            usage_score=usage_score,
            source_hits=source_hits,
            pageview_score=pageview_score,
            wiki_hit=_has_effective_wiki_support(
                word,
                wiki_titles,
                pageview_score=pageview_score,
                source_hits=source_hits,
            ),
            core_entry=False,
            jieba_direct_score=jieba_direct_score,
            pos_tag=pos_tag,
            char_score=char_score,
        )
        sc_words = tc_to_sc_map.get(word, set())
        if not sc_words:
            sc_words = {word}
        added_sc = False
        boosted_sc = False
        for sc_word in sc_words:
            if _cjk_len(sc_word) < min_hanzi:
                continue
            for pinyin in pinyin_candidates:
                key = (pinyin, sc_word)
                existing_weight = sc.get(key)
                if existing_weight is None:
                    sc[key] = weight
                    added_sc = True
                elif weight > existing_weight:
                    sc[key] = weight
                    boosted_sc = True
        if added_sc:
            stats["freqlex_terms_added_sc"] += 1
        if boosted_sc:
            stats["freqlex_terms_boosted_sc"] += 1

        tc_words = opencc_sc_to_tc.get(word, set())
        if tc_words:
            stats["freqlex_opencc_tc_hits"] += 1
        elif word in tc_existing_texts:
            tc_words = {word}

        added_tc = False
        boosted_tc = False
        for tc_word in tc_words:
            if _cjk_len(tc_word) < min_hanzi:
                continue
            tc_char_score = _compute_text_single_char_prior(tc_word, char_prior)
            tc_weight = _compute_weight_with_signals(
                tc_word,
                usage_score=usage_score,
                source_hits=source_hits,
                pageview_score=pageview_score,
                wiki_hit=_has_effective_wiki_support(
                    tc_word,
                    wiki_titles,
                    pageview_score=pageview_score,
                    source_hits=source_hits,
                ),
                core_entry=False,
                jieba_direct_score=jieba_direct_score,
                pos_tag=pos_tag,
                char_score=tc_char_score,
            )
            for pinyin in pinyin_candidates:
                key = (pinyin, tc_word)
                existing_weight = tc.get(key)
                if existing_weight is None:
                    tc[key] = tc_weight
                    added_tc = True
                elif tc_weight > existing_weight:
                    tc[key] = tc_weight
                    boosted_tc = True
        if added_tc:
            stats["freqlex_terms_added_tc"] += 1
        if boosted_tc:
            stats["freqlex_terms_boosted_tc"] += 1

    return stats


def _apply_limit(
    mapping: Dict[Tuple[str, str], int],
    max_entries: int,
) -> Dict[Tuple[str, str], int]:
    if max_entries <= 0 or len(mapping) <= max_entries:
        return mapping

    items = sorted(
        mapping.items(),
        key=lambda kv: (-kv[1], kv[0][0], kv[0][1]),
    )[:max_entries]
    return dict(items)


def _filter_windows_unrenderable_entries(
    mapping: Dict[Tuple[str, str], int],
) -> Tuple[Dict[Tuple[str, str], int], int]:
    filtered: Dict[Tuple[str, str], int] = {}
    dropped = 0
    for key, weight in mapping.items():
        _pinyin, text = key
        if not _is_windows_renderable_cjk_text(text):
            dropped += 1
            continue
        filtered[key] = weight
    return filtered, dropped


def _write_dict(path: pathlib.Path, mapping: Dict[Tuple[str, str], int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for (pinyin, text), weight in sorted(
            mapping.items(), key=lambda kv: (kv[0][0], kv[0][1], -kv[1])
        ):
            f.write(f"{pinyin}\t{text}\t{weight}\n")


def _write_manifest(path: pathlib.Path, profile: str, sources: List[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    generated_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()

    lines: List[str] = [
        "version: 1",
        f'generated_at: "{generated_at}"',
        f"profile: {profile}",
        "sources:",
    ]
    for source in sources:
        lines.extend(
            [
                f"  - id: {source['id']}",
                f"    name: {source['name']}",
                f"    download_url: {source['download_url']}",
                f"    homepage: {source['homepage']}",
                f"    license: {source['license']}",
                f"    risk_level: {source['risk_level']}",
                f"    redistribution_class: {source['redistribution_class']}",
                "    attribution_required: "
                + _to_yaml_bool(bool(source["attribution_required"])),
                "    raw_committed: " + _to_yaml_bool(bool(source["raw_committed"])),
                f"    notes: {_yaml_single_quote(source['notes'])}",
            ]
        )
    lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def _write_report(
    path: pathlib.Path,
    profile: str,
    sources: List[Dict[str, object]],
    output_sc: pathlib.Path,
    output_tc: pathlib.Path,
    stats: Dict[str, int],
    count_sc: int,
    count_tc: int,
    min_hanzi: int,
    max_entries: int,
    suspicious_sc: List[Dict[str, object]] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# External Build Report",
        "",
        f"- profile: {profile}",
        f"- generated_at_utc: {dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()}",
        f"- min_hanzi: {min_hanzi}",
        f"- max_entries: {max_entries if max_entries > 0 else 'unlimited'}",
        "",
        "## Sources",
    ]
    for source in sources:
        lines.extend(
            [
                f"- {source['id']}: {source['name']}",
                f"  - license: {source['license']}",
                f"  - risk_level: {source['risk_level']}",
                f"  - redistribution_class: {source['redistribution_class']}",
                f"  - url: {source['download_url']}",
            ]
        )

    lines.append("")
    lines.append("## Parse stats")
    for key in sorted(stats.keys()):
        lines.append(f"- {key}: {stats[key]}")

    lines.extend(
        [
            "",
            "## Output",
            f"- sc_file: {output_sc}",
            f"- tc_file: {output_tc}",
            f"- sc_entries: {count_sc}",
            f"- tc_entries: {count_tc}",
            "",
        ]
    )

    suspicious_sc = suspicious_sc or []
    if suspicious_sc:
        lines.append("## Suspicious High-Weight SC Entries")
        lines.append("")
        lines.append(
            "| text | pinyin | weight | usage | jieba | pageviews | source_hits | char_score | pos | reasons |"
        )
        lines.append(
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |"
        )
        for item in suspicious_sc:
            lines.append(
                "| {text} | {pinyin} | {weight} | {usage:.3f} | {jieba:.3f} | {pageviews:.3f} |"
                " {source_hits} | {char_score:.3f} | {pos} | {reasons} |".format(**item)
            )
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def _resolve_profile_config(args: argparse.Namespace) -> Dict[str, object]:
    if args.profile not in PROFILE_DEFAULTS:
        known = ", ".join(sorted(PROFILE_DEFAULTS.keys()))
        raise ValueError(f"unknown profile '{args.profile}', expected one of: {known}")

    base = PROFILE_DEFAULTS[args.profile]
    config: Dict[str, object] = {
        "parser": base["parser"],
        "sources": [dict(item) for item in base["sources"]],  # deep copy for source dicts
    }
    sources: List[Dict[str, object]] = config["sources"]  # type: ignore[assignment]
    if not sources:
        raise ValueError(f"profile '{args.profile}' has no sources configured")

    # Apply optional source overrides to primary source only.
    primary = sources[0]
    override_pairs = (
        ("download_url", args.source_url),
        ("id", args.source_id),
        ("name", args.source_name),
        ("homepage", args.source_homepage),
        ("license", args.source_license),
        ("risk_level", args.risk_level),
        ("redistribution_class", args.redistribution_class),
        ("notes", args.source_notes),
    )
    for key, value in override_pairs:
        if value:
            primary[key] = value
    if args.attribution_required:
        primary["attribution_required"] = _parse_bool(args.attribution_required)

    required_keys = (
        "id",
        "name",
        "download_url",
        "homepage",
        "license",
        "risk_level",
        "redistribution_class",
        "notes",
    )
    for source in sources:
        for key in required_keys:
            if not str(source.get(key, "")).strip():
                raise ValueError(f"profile '{args.profile}' source requires key '{key}'")

    if args.profile == "clean_permissive":
        for source in sources:
            license_lower = str(source["license"]).lower()
            if any(token in license_lower for token in COPYLEFT_LICENSE_TOKENS):
                raise ValueError(
                    "clean_permissive profile rejects copyleft/share-alike licenses; "
                    f"got '{source['license']}' in source {source['id']}"
                )
            if str(source.get("redistribution_class", "")).lower() != "permissive":
                raise ValueError(
                    "clean_permissive profile requires redistribution_class=permissive"
                )
            if str(source.get("risk_level", "")).lower() != "low":
                raise ValueError("clean_permissive profile requires risk_level=low")

    return config


def _resolve_cache_source_id(
    parser_name: str, sources: List[Dict[str, object]], explicit_source_id: str
) -> str:
    if not sources:
        raise ValueError("no sources configured for cache resolution")

    known_ids = [str(item.get("id", "")) for item in sources if str(item.get("id", "")).strip()]
    if not known_ids:
        raise ValueError("all sources are missing non-empty id")

    if explicit_source_id:
        if explicit_source_id not in known_ids:
            raise ValueError(
                f"--cache-source-id '{explicit_source_id}' not found in current profile sources: "
                + ", ".join(known_ids)
            )
        return explicit_source_id

    preferred_by_parser = {
        "cedict": "cc-cedict",
        "cedict_thuocl_jieba_opencc_unihan_wiki": "cc-cedict",
        "opencc_unihan": "opencc-stphrases",
        "unihan_only": "unicode-unihan-readings",
    }
    preferred = preferred_by_parser.get(parser_name, "")
    if preferred and preferred in known_ids:
        return preferred

    return known_ids[0]


def _require_source_payload(
    payload_map: Dict[str, bytes],
    sources: List[Dict[str, object]],
    *,
    role: str,
    source_id: str,
    download_url: str,
) -> bytes:
    source: Dict[str, object] | None = None
    for candidate in sources:
        if str(candidate.get("id", "")) == source_id:
            source = candidate
            break

    if source is None:
        for candidate in sources:
            if str(candidate.get("download_url", "")) == download_url:
                source = candidate
                break

    if source is None:
        raise ValueError(
            f"missing source payload for role '{role}' "
            f"(id='{source_id}', url='{download_url}')"
        )

    payload_key = str(source.get("id", ""))
    payload = payload_map.get(payload_key)
    if payload is None:
        raise ValueError(
            f"missing payload bytes for role '{role}' source id '{payload_key}'"
    )
    return payload


def _require_source_config(
    sources: List[Dict[str, object]],
    *,
    role: str,
    source_id: str,
    download_url: str,
) -> Dict[str, object]:
    for candidate in sources:
        if str(candidate.get("id", "")) == source_id:
            return candidate
    for candidate in sources:
        if str(candidate.get("download_url", "")) == download_url:
            return candidate
    raise ValueError(
        f"missing source config for role '{role}' (id='{source_id}', url='{download_url}')"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build dictionary seed files from external data sources."
    )
    parser.add_argument(
        "--profile",
        default="external_cedict",
        choices=sorted(PROFILE_DEFAULTS.keys()),
    )
    parser.add_argument("--source-url", default="")
    parser.add_argument("--source-id", default="")
    parser.add_argument("--source-name", default="")
    parser.add_argument("--source-homepage", default="")
    parser.add_argument("--source-license", default="")
    parser.add_argument("--risk-level", default="")
    parser.add_argument("--redistribution-class", default="")
    parser.add_argument(
        "--attribution-required",
        default="",
        help="Optional bool override for primary source: true/false.",
    )
    parser.add_argument("--source-notes", default="")
    parser.add_argument(
        "--cache-file",
        default="",
        help="Optional local cache file. Bound to --cache-source-id "
        "(or profile default source role when omitted).",
    )
    parser.add_argument(
        "--cache-source-id",
        default="",
        help="Optional source id to bind --cache-file to (for example: cc-cedict).",
    )
    parser.add_argument("--output-sc", default="data/generated/dict_clean_sc.txt")
    parser.add_argument("--output-tc", default="data/generated/dict_clean_tc.txt")
    parser.add_argument("--manifest", default="manifests/sources.public.yml")
    parser.add_argument("--report", default="reports/external_build_report.md")
    parser.add_argument(
        "--pinyin-overrides",
        default=DEFAULT_PERMISSIVE_OVERRIDES,
        help="Optional override TSV for clean_permissive/unihan_single profile: text<TAB>pinyin",
    )
    parser.add_argument("--min-hanzi", type=int, default=2)
    parser.add_argument(
        "--max-entries",
        type=int,
        default=0,
        help="Limit output entries per script. 0 means unlimited.",
    )
    parser.add_argument(
        "--pageviews-months",
        type=int,
        default=6,
        help="Number of recent complete months for Wikimedia pageviews-top aggregation.",
    )
    parser.add_argument(
        "--pageviews-max-rank",
        type=int,
        default=1000,
        help="Per-month pageviews rank cutoff (1..1000).",
    )
    args = parser.parse_args()

    repo_root = pathlib.Path(__file__).resolve().parents[1]
    output_sc = repo_root / args.output_sc
    output_tc = repo_root / args.output_tc
    manifest = repo_root / args.manifest
    report = repo_root / args.report
    if args.pageviews_months < 0:
        raise ValueError("--pageviews-months must be >= 0")
    if args.pageviews_max_rank <= 0:
        raise ValueError("--pageviews-max-rank must be > 0")

    profile_config = _resolve_profile_config(args)
    parser_name = str(profile_config["parser"])
    sources: List[Dict[str, object]] = profile_config["sources"]  # type: ignore[assignment]

    payload_map: Dict[str, bytes] = {}
    usage_score_map: Dict[str, float] = {}
    source_hits_map: Dict[str, int] = {}
    jieba_direct_signal_map: Dict[str, float] = {}
    jieba_pos_map: Dict[str, str] = {}
    char_frequency_prior: Dict[str, float] = {}
    pageviews_signal_map: Dict[str, float] = {}
    wiki_titles: Set[str] = set()
    tc_usage_score_map: Dict[str, float] = {}
    tc_source_hits_map: Dict[str, int] = {}
    tc_jieba_direct_signal_map: Dict[str, float] = {}
    tc_jieba_pos_map: Dict[str, str] = {}
    tc_char_frequency_prior: Dict[str, float] = {}
    tc_pageviews_signal_map: Dict[str, float] = {}
    primary_cache = repo_root / args.cache_file if args.cache_file else None
    cache_source_id = ""
    if primary_cache is not None:
        cache_source_id = _resolve_cache_source_id(parser_name, sources, args.cache_source_id)
    for source in sources:
        source_id = str(source["id"])
        if source_id in payload_map:
            raise ValueError(f"duplicate source id in profile '{args.profile}': {source_id}")
        if source_id == "wikimedia-pageviews-top":
            # This source is fetched via monthly API calls with dedicated local cache files.
            continue
        cache_file = primary_cache if (primary_cache is not None and source_id == cache_source_id) else None
        payload = _read_source_bytes(str(source["download_url"]), cache_file)
        payload_map[source_id] = payload

    if parser_name == "cedict":
        primary_source_id = str(sources[0]["id"])
        source_payload = payload_map[primary_source_id]
        source_text = _decode_text(source_payload)
        sc_map, tc_map, stats = _parse_cedict_entries(source_text, args.min_hanzi)
    elif parser_name == "cedict_thuocl_jieba_opencc_unihan_wiki":
        cedict_payload = _require_source_payload(
            payload_map,
            sources,
            role="cc-cedict",
            source_id="cc-cedict",
            download_url=CEDICT_DEFAULT_URL,
        )
        thuocl_payload = _require_source_payload(
            payload_map,
            sources,
            role="thuocl",
            source_id="thuocl",
            download_url=THUOCL_ZIP_URL,
        )
        opencc_payload = _require_source_payload(
            payload_map,
            sources,
            role="opencc-stphrases",
            source_id="opencc-stphrases",
            download_url=OPENCC_STPHRASES_URL,
        )
        jieba_payload = _require_source_payload(
            payload_map,
            sources,
            role="jieba-dict",
            source_id="jieba-dict",
            download_url=JIEBA_DICT_URL,
        )
        unihan_payload = _require_source_payload(
            payload_map,
            sources,
            role="unicode-unihan-readings",
            source_id="unicode-unihan-readings",
            download_url=UNICODE_UNIHAN_URL,
        )
        wiki_titles_payload = _require_source_payload(
            payload_map,
            sources,
            role="zhwiki-titles-ns0",
            source_id="zhwiki-titles-ns0",
            download_url=ZHWIKI_TITLES_URL,
        )
        cedict_text = _decode_text(cedict_payload)
        opencc_text = _decode_text(opencc_payload)
        cedict_tc_to_sc_map = _build_cedict_tc_to_sc_map(cedict_text, args.min_hanzi)

        sc_map, tc_map, cedict_stats = _parse_cedict_entries(cedict_text, args.min_hanzi)
        opencc_entries, opencc_stats = _parse_opencc_entries(opencc_text, args.min_hanzi)
        opencc_tc_to_sc_map = _build_opencc_tc_to_sc_map(opencc_entries)
        tc_to_sc_map = _merge_tc_to_sc_maps(opencc_tc_to_sc_map, cedict_tc_to_sc_map)
        thuocl_max_df, thuocl_coverage, thuocl_stats = _parse_thuocl_entries(thuocl_payload)
        jieba_entries, jieba_pos_map, jieba_stats = _parse_jieba_frequency_entries(
            jieba_payload, args.min_hanzi
        )
        thuocl_entries = _build_thuocl_frequency_map(thuocl_max_df, thuocl_coverage)
        pageviews_source = _require_source_config(
            sources,
            role="wikimedia-pageviews-top",
            source_id="wikimedia-pageviews-top",
            download_url=WIKIMEDIA_PAGEVIEWS_TOP_URL,
        )
        pageviews_entries, pageviews_stats = _load_wikimedia_pageviews_entries(
            repo_root=repo_root,
            source_url=str(pageviews_source["download_url"]),
            min_hanzi=args.min_hanzi,
            months=args.pageviews_months,
            max_rank=args.pageviews_max_rank,
        )
        pageviews_entries_sc = _normalize_pageviews_entries_to_sc(
            pageviews_entries,
            tc_to_sc_map,
        )
        thuocl_signal_map = _build_normalized_signal_map(thuocl_entries)
        jieba_signal_map = _build_normalized_signal_map(jieba_entries)
        jieba_direct_signal_map = _build_direct_frequency_signal_map(jieba_entries)
        char_frequency_prior = _build_char_frequency_prior(jieba_entries)
        pageviews_signal_map = _build_normalized_signal_map(pageviews_entries_sc)
        usage_score_map, source_hits_map = _build_usage_signal_map(
            thuocl_signal_map,
            jieba_signal_map,
            pageviews_signal_map,
            jieba_pos_map=jieba_pos_map,
            jieba_direct_signal_map=jieba_direct_signal_map,
        )
        unihan_map = _load_unihan_mandarin_map(unihan_payload)
        wiki_titles, wiki_stats = _parse_wiki_titles_entries(
            wiki_titles_payload, min_hanzi=args.min_hanzi
        )
        tc_usage_score_map = _build_tc_signal_map(usage_score_map, tc_to_sc_map)
        tc_source_hits_map = _build_tc_source_hits_map(source_hits_map, tc_to_sc_map)
        tc_jieba_direct_signal_map = _build_tc_signal_map(jieba_direct_signal_map, tc_to_sc_map)
        tc_jieba_pos_map = _build_tc_pos_map(jieba_pos_map, tc_to_sc_map)
        tc_char_frequency_prior = _build_tc_signal_map(char_frequency_prior, tc_to_sc_map)
        tc_pageviews_signal_map = _build_tc_signal_map(pageviews_signal_map, tc_to_sc_map)
        (
            trad_to_simp_char_map,
            simp_to_trad_char_map,
            sc_script_chars,
            tc_script_chars,
        ) = _build_char_variant_hints(tc_to_sc_map, opencc_entries)
        unihan_simplified_variant_map = _load_unihan_simplified_variant_map(unihan_payload)
        for trad_ch, simp_ch in unihan_simplified_variant_map.items():
            if trad_ch not in trad_to_simp_char_map:
                trad_to_simp_char_map[trad_ch] = simp_ch
            if simp_ch not in simp_to_trad_char_map:
                simp_to_trad_char_map[simp_ch] = trad_ch
        unihan_traditional_variant_map = _load_unihan_traditional_variant_map(unihan_payload)
        for simp_ch, trad_ch in unihan_traditional_variant_map.items():
            if simp_ch not in simp_to_trad_char_map:
                simp_to_trad_char_map[simp_ch] = trad_ch
            if trad_ch not in trad_to_simp_char_map:
                trad_to_simp_char_map[trad_ch] = simp_ch
        sc_rescore_stats = _rescore_mapping_with_signals(
            sc_map,
            usage_score_map=usage_score_map,
            source_hits_map=source_hits_map,
            pageviews_signal_map=pageviews_signal_map,
            wiki_titles=wiki_titles,
            jieba_direct_signal_map=jieba_direct_signal_map,
            jieba_pos_map=jieba_pos_map,
            char_frequency_prior=char_frequency_prior,
            core_entry=True,
            stats_prefix="sc_core",
        )
        tc_rescore_stats = _rescore_mapping_with_signals(
            tc_map,
            usage_score_map=tc_usage_score_map,
            source_hits_map=tc_source_hits_map,
            pageviews_signal_map=tc_pageviews_signal_map,
            wiki_titles=wiki_titles,
            jieba_direct_signal_map=tc_jieba_direct_signal_map,
            jieba_pos_map=tc_jieba_pos_map,
            char_frequency_prior=tc_char_frequency_prior,
            core_entry=True,
            stats_prefix="tc_core",
        )
        augment_stats = _augment_with_frequency_lexicon(
            sc_map,
            tc_map,
            usage_score_map,
            source_hits_map,
            pageviews_signal_map,
            jieba_direct_signal_map,
            jieba_pos_map,
            char_frequency_prior,
            opencc_entries,
            tc_to_sc_map,
            unihan_map,
            wiki_titles,
            args.min_hanzi,
        )
        sc_map, sc_normalize_stats = _normalize_sc_mapping_with_opencc(sc_map, tc_to_sc_map)
        sc_map, sc_char_normalize_stats = _normalize_sc_mapping_with_char_map(
            sc_map, trad_to_simp_char_map, simp_to_trad_char_map
        )
        sc_map, sc_script_filter_stats = _filter_sc_mapping_with_script_hints(
            sc_map, sc_script_chars, tc_script_chars
        )
        tc_map, tc_char_normalize_stats = _normalize_tc_mapping_with_char_map(
            tc_map, simp_to_trad_char_map
        )
        tc_map, tc_script_filter_stats = _filter_tc_mapping_with_script_hints(
            tc_map, sc_script_chars, tc_script_chars
        )

        stats = {}
        stats.update(cedict_stats)
        stats.update(opencc_stats)
        stats.update(thuocl_stats)
        stats.update(jieba_stats)
        stats["thuocl_frequency_terms"] = len(thuocl_entries)
        stats["jieba_frequency_terms"] = len(jieba_entries)
        stats.update(pageviews_stats)
        stats["pageviews_frequency_terms"] = len(pageviews_entries)
        stats["pageviews_sc_normalized_terms"] = len(pageviews_entries_sc)
        stats["usage_score_terms"] = len(usage_score_map)
        stats["jieba_direct_score_terms"] = len(jieba_direct_signal_map)
        stats["jieba_pos_terms"] = len(jieba_pos_map)
        stats["char_frequency_prior_terms"] = len(char_frequency_prior)
        stats.update(wiki_stats)
        stats.update(sc_rescore_stats)
        stats.update(tc_rescore_stats)
        stats.update(augment_stats)
        stats.update(sc_normalize_stats)
        stats.update(sc_char_normalize_stats)
        stats.update(sc_script_filter_stats)
        stats.update(tc_char_normalize_stats)
        stats.update(tc_script_filter_stats)
        stats["unihan_map_size"] = len(unihan_map)
        stats["tc_usage_score_terms"] = len(tc_usage_score_map)
        stats["tc_jieba_direct_score_terms"] = len(tc_jieba_direct_signal_map)
        stats["tc_jieba_pos_terms"] = len(tc_jieba_pos_map)
        stats["tc_char_frequency_prior_terms"] = len(tc_char_frequency_prior)
        stats["tc_pageviews_score_terms"] = len(tc_pageviews_signal_map)
        stats["tc_to_sc_map_terms"] = len(tc_to_sc_map)
        stats["wiki_title_set_size"] = len(wiki_titles)
    elif parser_name == "opencc_unihan":
        opencc_payload = _require_source_payload(
            payload_map,
            sources,
            role="opencc-stphrases",
            source_id="opencc-stphrases",
            download_url=OPENCC_STPHRASES_URL,
        )
        unihan_payload = _require_source_payload(
            payload_map,
            sources,
            role="unicode-unihan-readings",
            source_id="unicode-unihan-readings",
            download_url=UNICODE_UNIHAN_URL,
        )
        opencc_text = _decode_text(opencc_payload)
        overrides: Dict[str, str] = {}
        if args.pinyin_overrides:
            overrides = _load_pinyin_overrides(repo_root / args.pinyin_overrides)
        sc_map, tc_map, stats = _build_from_opencc_unihan(
            opencc_text, unihan_payload, args.min_hanzi, overrides
        )
        opencc_entries_for_hints, _opencc_hint_stats = _parse_opencc_entries(opencc_text, 1)
        opencc_tc_to_sc_map = _build_opencc_tc_to_sc_map(opencc_entries_for_hints)
        (
            trad_to_simp_char_map,
            simp_to_trad_char_map,
            sc_script_chars,
            tc_script_chars,
        ) = _build_char_variant_hints(opencc_tc_to_sc_map, opencc_entries_for_hints)
        unihan_simplified_variant_map = _load_unihan_simplified_variant_map(unihan_payload)
        for trad_ch, simp_ch in unihan_simplified_variant_map.items():
            if trad_ch not in trad_to_simp_char_map:
                trad_to_simp_char_map[trad_ch] = simp_ch
            if simp_ch not in simp_to_trad_char_map:
                simp_to_trad_char_map[simp_ch] = trad_ch
        unihan_traditional_variant_map = _load_unihan_traditional_variant_map(unihan_payload)
        for simp_ch, trad_ch in unihan_traditional_variant_map.items():
            if simp_ch not in simp_to_trad_char_map:
                simp_to_trad_char_map[simp_ch] = trad_ch
            if trad_ch not in trad_to_simp_char_map:
                trad_to_simp_char_map[trad_ch] = simp_ch
        sc_map, sc_char_normalize_stats = _normalize_sc_mapping_with_char_map(
            sc_map, trad_to_simp_char_map, simp_to_trad_char_map
        )
        sc_map, sc_script_filter_stats = _filter_sc_mapping_with_script_hints(
            sc_map, sc_script_chars, tc_script_chars
        )
        tc_map, tc_char_normalize_stats = _normalize_tc_mapping_with_char_map(
            tc_map, simp_to_trad_char_map
        )
        tc_map, tc_script_filter_stats = _filter_tc_mapping_with_script_hints(
            tc_map, sc_script_chars, tc_script_chars
        )
        stats.update(sc_char_normalize_stats)
        stats.update(sc_script_filter_stats)
        stats.update(tc_char_normalize_stats)
        stats.update(tc_script_filter_stats)
    elif parser_name == "unihan_only":
        opencc_payload = _require_source_payload(
            payload_map,
            sources,
            role="opencc-stphrases",
            source_id="opencc-stphrases",
            download_url=OPENCC_STPHRASES_URL,
        )
        unihan_payload = _require_source_payload(
            payload_map,
            sources,
            role="unicode-unihan-readings",
            source_id="unicode-unihan-readings",
            download_url=UNICODE_UNIHAN_URL,
        )
        opencc_text = _decode_text(opencc_payload)
        opencc_entries, opencc_stats = _parse_opencc_entries(opencc_text, 1)
        opencc_tc_to_sc_map = _build_opencc_tc_to_sc_map(opencc_entries)
        (
            trad_to_simp_char_map,
            simp_to_trad_char_map,
            sc_script_chars,
            tc_script_chars,
        ) = _build_char_variant_hints(opencc_tc_to_sc_map, opencc_entries)
        unihan_simplified_variant_map = _load_unihan_simplified_variant_map(unihan_payload)
        for trad_ch, simp_ch in unihan_simplified_variant_map.items():
            if trad_ch not in trad_to_simp_char_map:
                trad_to_simp_char_map[trad_ch] = simp_ch
            if simp_ch not in simp_to_trad_char_map:
                simp_to_trad_char_map[simp_ch] = trad_ch
        unihan_traditional_variant_map = _load_unihan_traditional_variant_map(unihan_payload)
        for simp_ch, trad_ch in unihan_traditional_variant_map.items():
            if simp_ch not in simp_to_trad_char_map:
                simp_to_trad_char_map[simp_ch] = trad_ch
            if trad_ch not in trad_to_simp_char_map:
                trad_to_simp_char_map[trad_ch] = simp_ch
        overrides: Dict[str, str] = {}
        if args.pinyin_overrides:
            overrides = _load_pinyin_overrides(repo_root / args.pinyin_overrides)
        sc_map, tc_map, stats = _build_from_unihan_only(
            unihan_payload,
            args.min_hanzi,
            overrides,
            trad_to_simp_char_map,
            simp_to_trad_char_map,
            sc_script_chars,
            tc_script_chars,
        )
        stats.update(opencc_stats)
    else:
        raise ValueError(f"unsupported parser: {parser_name}")

    sc_map, dropped_sc_non_windows = _filter_windows_unrenderable_entries(sc_map)
    tc_map, dropped_tc_non_windows = _filter_windows_unrenderable_entries(tc_map)
    stats["sc_filtered_non_windows_cjk"] = dropped_sc_non_windows
    stats["tc_filtered_non_windows_cjk"] = dropped_tc_non_windows

    sc_homophone_stats = _rerank_homophone_buckets(
        sc_map,
        usage_score_map=usage_score_map,
        source_hits_map=source_hits_map,
        pageviews_signal_map=pageviews_signal_map,
        wiki_titles=wiki_titles,
        jieba_direct_signal_map=jieba_direct_signal_map,
        jieba_pos_map=jieba_pos_map,
        char_frequency_prior=char_frequency_prior,
        stats_prefix="sc",
    )
    stats.update(sc_homophone_stats)
    sc_low_signal_stats = _filter_low_signal_rare_entries(
        sc_map,
        usage_score_map=usage_score_map,
        source_hits_map=source_hits_map,
        pageviews_signal_map=pageviews_signal_map,
        wiki_titles=wiki_titles,
        jieba_direct_signal_map=jieba_direct_signal_map,
        jieba_pos_map=jieba_pos_map,
        char_frequency_prior=char_frequency_prior,
        stats_prefix="sc",
    )
    stats.update(sc_low_signal_stats)
    sc_global_tail_stats = _filter_global_tail_entries(
        sc_map,
        usage_score_map=usage_score_map,
        source_hits_map=source_hits_map,
        pageviews_signal_map=pageviews_signal_map,
        wiki_titles=wiki_titles,
        jieba_direct_signal_map=jieba_direct_signal_map,
        jieba_pos_map=jieba_pos_map,
        char_frequency_prior=char_frequency_prior,
        stats_prefix="sc",
    )
    stats.update(sc_global_tail_stats)

    tc_homophone_stats = _rerank_homophone_buckets(
        tc_map,
        usage_score_map=tc_usage_score_map,
        source_hits_map=tc_source_hits_map,
        pageviews_signal_map=tc_pageviews_signal_map,
        wiki_titles=wiki_titles,
        jieba_direct_signal_map=tc_jieba_direct_signal_map,
        jieba_pos_map=tc_jieba_pos_map,
        char_frequency_prior=tc_char_frequency_prior,
        stats_prefix="tc",
    )
    stats.update(tc_homophone_stats)
    tc_low_signal_stats = _filter_low_signal_rare_entries(
        tc_map,
        usage_score_map=tc_usage_score_map,
        source_hits_map=tc_source_hits_map,
        pageviews_signal_map=tc_pageviews_signal_map,
        wiki_titles=wiki_titles,
        jieba_direct_signal_map=tc_jieba_direct_signal_map,
        jieba_pos_map=tc_jieba_pos_map,
        char_frequency_prior=tc_char_frequency_prior,
        stats_prefix="tc",
    )
    stats.update(tc_low_signal_stats)
    tc_global_tail_stats = _filter_global_tail_entries(
        tc_map,
        usage_score_map=tc_usage_score_map,
        source_hits_map=tc_source_hits_map,
        pageviews_signal_map=tc_pageviews_signal_map,
        wiki_titles=wiki_titles,
        jieba_direct_signal_map=tc_jieba_direct_signal_map,
        jieba_pos_map=tc_jieba_pos_map,
        char_frequency_prior=tc_char_frequency_prior,
        stats_prefix="tc",
    )
    stats.update(tc_global_tail_stats)

    sc_map = _apply_limit(sc_map, args.max_entries)
    tc_map = _apply_limit(tc_map, args.max_entries)
    suspicious_sc_entries = _collect_suspicious_high_weight_entries(
        sc_map,
        usage_score_map=usage_score_map,
        source_hits_map=source_hits_map,
        pageviews_signal_map=pageviews_signal_map,
        wiki_titles=wiki_titles,
        jieba_direct_signal_map=jieba_direct_signal_map,
        jieba_pos_map=jieba_pos_map,
        char_frequency_prior=char_frequency_prior,
    )

    _write_dict(output_sc, sc_map)
    _write_dict(output_tc, tc_map)
    _write_manifest(manifest, args.profile, sources)
    _write_report(
        report,
        args.profile,
        sources,
        output_sc,
        output_tc,
        stats,
        len(sc_map),
        len(tc_map),
        args.min_hanzi,
        args.max_entries,
        suspicious_sc_entries,
    )

    print(f"Build completed: profile={args.profile} sc={len(sc_map)} tc={len(tc_map)}")
    print(f"Manifest updated: {manifest}")
    print(f"Report written: {report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
