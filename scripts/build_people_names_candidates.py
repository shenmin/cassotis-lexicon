#!/usr/bin/env python3
"""Generate manual-review people-name candidates from Wikidata.

The generated TSV is intentionally not imported by the normal build. It is a
review queue for maintainers to copy vetted names into
manifests/vertical/people_names.tsv with explicit pinyin.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Set, Tuple


WIKIDATA_SPARQL_URL = "https://query.wikidata.org/sparql"
CJK_NAME_RE = re.compile(r"^[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]{2,8}$")

OCCUPATIONS: Sequence[Tuple[str, str]] = (
    ("actor", "Q33999"),
    ("singer", "Q177220"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate manual-review contemporary people-name candidates."
    )
    parser.add_argument(
        "--people-names",
        default="manifests/vertical/people_names.tsv",
        help="Existing curated people_names TSV used for de-duplication.",
    )
    parser.add_argument(
        "--output",
        default="data/cache/people_names_candidates.tsv",
        help="Output TSV for manual review. The default is ignored by git.",
    )
    parser.add_argument(
        "--cache",
        default="data/cache/wikidata_people_name_candidates.json",
        help="JSON cache for Wikidata query results.",
    )
    parser.add_argument(
        "--min-sitelinks",
        type=int,
        default=8,
        help="Minimum Wikidata sitelink count for candidate labels.",
    )
    parser.add_argument(
        "--limit-per-occupation",
        type=int,
        default=250,
        help="SPARQL LIMIT for each occupation query.",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Ignore the local cache and query Wikidata again.",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=1.0,
        help="Delay between Wikidata queries to avoid hammering the endpoint.",
    )
    return parser.parse_args()


def load_existing_terms(path: Path) -> Set[str]:
    terms: Set[str] = set()
    if not path.exists():
        return terms
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        terms.add(parts[0].strip())
        terms.add(parts[1].strip())
    return {term for term in terms if term}


def build_query(occupation_qid: str, min_sitelinks: int, limit: int) -> str:
    return f"""PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX schema: <http://schema.org/>
PREFIX wikibase: <http://wikiba.se/ontology#>
SELECT DISTINCT ?item ?term ?sitelinks WHERE {{
  ?item wdt:P31 wd:Q5 ;
        wdt:P106 wd:{occupation_qid} ;
        wikibase:sitelinks ?sitelinks ;
        rdfs:label ?label .
  ?article schema:about ?item ;
           schema:isPartOf <https://zh.wikipedia.org/> .
  FILTER(LANG(?label) = "zh")
  FILTER(?sitelinks >= {min_sitelinks})
  BIND(STR(?label) AS ?term)
}}
ORDER BY DESC(?sitelinks)
LIMIT {limit}"""


def fetch_sparql(query: str) -> Dict[str, Any]:
    payload = urllib.parse.urlencode({"query": query, "format": "json"}).encode("utf-8")
    request = urllib.request.Request(
        WIKIDATA_SPARQL_URL,
        data=payload,
        headers={
            "Accept": "application/sparql-results+json",
            "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
            "User-Agent": "CassotisLexicon/people-name-candidates",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def parse_bindings(payload: Dict[str, Any], occupation: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    bindings = payload.get("results", {}).get("bindings", [])
    for binding in bindings:
        term = str(binding.get("term", {}).get("value", "")).strip()
        item = str(binding.get("item", {}).get("value", "")).strip()
        sitelinks_text = str(binding.get("sitelinks", {}).get("value", "0")).strip()
        try:
            sitelinks = int(sitelinks_text)
        except ValueError:
            sitelinks = 0
        rows.append(
            {
                "term": term,
                "occupation": occupation,
                "sitelinks": sitelinks,
                "item": item,
            }
        )
    return rows


def cache_matches_args(payload: Dict[str, Any], args: argparse.Namespace) -> bool:
    occupations = payload.get("occupations", [])
    expected_occupations = [{"name": name, "qid": qid} for name, qid in OCCUPATIONS]
    return (
        payload.get("min_sitelinks") == args.min_sitelinks
        and payload.get("limit_per_occupation") == args.limit_per_occupation
        and occupations == expected_occupations
    )


def load_or_fetch_rows(args: argparse.Namespace, cache_path: Path) -> List[Dict[str, Any]]:
    if cache_path.exists() and not args.refresh:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        if cache_matches_args(payload, args):
            return list(payload.get("rows", []))

    all_rows: List[Dict[str, Any]] = []
    for index, (occupation, qid) in enumerate(OCCUPATIONS):
        query = build_query(qid, args.min_sitelinks, args.limit_per_occupation)
        payload = fetch_sparql(query)
        all_rows.extend(parse_bindings(payload, occupation))
        if index < len(OCCUPATIONS) - 1 and args.sleep_seconds > 0:
            time.sleep(args.sleep_seconds)

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_payload = {
        "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "min_sitelinks": args.min_sitelinks,
        "limit_per_occupation": args.limit_per_occupation,
        "occupations": [{"name": name, "qid": qid} for name, qid in OCCUPATIONS],
        "rows": all_rows,
    }
    cache_path.write_text(
        json.dumps(cache_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return all_rows


def score_hint(sitelinks: int) -> float:
    if sitelinks >= 100:
        return 0.80
    if sitelinks >= 50:
        return 0.78
    if sitelinks >= 25:
        return 0.76
    if sitelinks >= 12:
        return 0.74
    return 0.72


def filter_candidates(
    rows: Iterable[Dict[str, Any]], existing_terms: Set[str]
) -> List[Dict[str, Any]]:
    best_by_term: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        term = str(row.get("term", "")).strip()
        if term in existing_terms:
            continue
        if not CJK_NAME_RE.fullmatch(term):
            continue
        current = best_by_term.get(term)
        if current is None or int(row.get("sitelinks", 0)) > int(current.get("sitelinks", 0)):
            best_by_term[term] = row
    return sorted(
        best_by_term.values(),
        key=lambda row: (-int(row.get("sitelinks", 0)), str(row.get("term", ""))),
    )


def write_candidates(path: Path, candidates: Sequence[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# term\tsuggested_usage_score\toccupation\tsitelinks\twikidata_item",
        "# Manual review only: copy vetted rows into manifests/vertical/people_names.tsv with explicit pinyin.",
    ]
    for row in candidates:
        term = str(row.get("term", "")).strip()
        sitelinks = int(row.get("sitelinks", 0))
        lines.append(
            "\t".join(
                [
                    term,
                    f"{score_hint(sitelinks):.2f}",
                    str(row.get("occupation", "")).strip(),
                    str(sitelinks),
                    str(row.get("item", "")).strip(),
                ]
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    root = Path.cwd()
    people_names_path = (root / args.people_names).resolve()
    output_path = (root / args.output).resolve()
    cache_path = (root / args.cache).resolve()

    existing_terms = load_existing_terms(people_names_path)
    rows = load_or_fetch_rows(args, cache_path)
    candidates = filter_candidates(rows, existing_terms)
    write_candidates(output_path, candidates)
    print(f"Wrote {len(candidates)} candidates: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
