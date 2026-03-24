# Cassotis Lexicon

<p align="center">
  <img src="cassotis_ime_yanquan.png" alt="Cassotis IME logo" width="280">
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-CC%20BY--SA%204.0-blue" alt="License: CC BY-SA 4.0"></a>
</p>

English | [简体中文](README.CN.md)

Lexicon build and release repository for Cassotis IME.

## Repository role
- Maintains lexicon build scripts, manifests, and generated outputs.
- Supports external-source bootstrap and lexicon release workflows.
- Keeps attribution and release policy files aligned with repository artifacts.

## Current dictionary snapshot (2026-03-24 build)

| File | Variant | Entries |
|------|---------|---------|
| `data/generated/dict_clean_sc.txt` | Simplified Chinese | 114,051 |
| `data/generated/dict_clean_tc.txt` | Traditional Chinese | 111,612 |
| `data/generated/dict_unihan_sc.txt` | Simplified single-char (Unihan) | 23,910 |
| `data/generated/dict_unihan_tc.txt` | Traditional single-char (Unihan) | 24,065 |

## Bootstrap sources and curated supplements (`external_broad`)

| Source | License | Usage |
|--------|---------|-------|
| CC-CEDICT | CC BY-SA 4.0 | Core dictionary entries and pinyin |
| THUOCL | THUOCL custom open terms | Broad coverage and DF statistics |
| OpenCC STPhrases | Apache-2.0 | SC-TC phrase mapping |
| jieba `dict.txt` | MIT | Frequency ranking signal |
| Unicode Unihan | Unicode-3.0 | Character-level Mandarin fallback and single-char dictionaries |
| Wiktionary zh titles (ns0) | CC BY-SA 4.0 | Daily wording, colloquial phrases, and chat-style lexical seeds |
| Cassotis curated daily/chat phrases | Repository license (project-authored) | High-value everyday/chat phrasing that is worth keeping stable even when open sources miss it |
| Wikipedia zh titles (ns0) | CC BY-SA 4.0 | Named-entity coverage |
| Wikimedia Pageviews Top (zh.wikipedia) | CC BY-SA 4.0 | Real-world usage heat signal |

See:
- `attribution/ATTRIBUTION.md`
- `reports/external_build_report.md`
- `reports/unihan_build_report.md`

## Post-import optimization and filtering (external sources)
- Normalize and de-duplicate imported entries across heterogeneous source formats.
- Build weights from multiple signals (base frequency, DF/frequency side signals, and pageview heat) with balanced scaling.
- Derive shorter daily/chat prefixes from already-supported longer colloquial expressions so phrases such as common sentence pivots surface earlier in IME use.
- Damp low-signal named entities, likely personal names, and long-tail noise to reduce rare proper nouns crowding common phrases.
- Apply IME-oriented validity filters (for example renderability and script constraints) to keep outputs practical on mainstream Windows clients.
- Keep ranking behavior stable through rule-based corrections and regression sample checks.

## Coverage focus
- Prioritize everyday wording and conversational phrasing that improves fluent chat input, not only topical hotwords.
- Use open lexical sources to recover common short expressions such as sentence pivots, mood particles, and colloquial transitions.
- Keep a small project-maintained whitelist for high-value daily phrases when open lexical sources still miss them.
- Keep named entities and bursty web terms as secondary signals instead of letting them dominate core daily typing paths.

## Directory layout
- `data/generated/`: generated lexicon files.
- `manifests/`: source/license manifests and regression samples.
- `scripts/`: build/validation/export helper scripts.
- `reports/`: generated build reports.
- `rules/`: export/release rules.

## Build

```powershell
# Full rebuild (external_broad + unihan_single + regression checks)
.\rebuild_all.ps1

# Build one profile directly
.\scripts\build_external_seed.ps1 -Profile external_broad
```

## Constraints
- Do not commit raw corpus files, drafts, or author manuscripts.
