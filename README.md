# Cassotis Lexicon

English | [简体中文](README.CN.md)

Lexicon build and release repository for Cassotis IME.

## Repository role
- Maintains lexicon build scripts, manifests, and generated outputs.
- Supports external-source bootstrap and private-corpus integration workflows.
- Keeps attribution and release policy files aligned with exported public artifacts.

## Current dictionary snapshot (2026-03-06 build)

| File | Variant | Entries |
|------|---------|---------|
| `data/generated/dict_clean_sc.txt` | Simplified Chinese | 103,915 |
| `data/generated/dict_clean_tc.txt` | Traditional Chinese | 90,209 |
| `data/generated/dict_unihan_sc.txt` | Simplified single-char (Unihan) | 30,397 |
| `data/generated/dict_unihan_tc.txt` | Traditional single-char (Unihan) | 31,009 |

## External bootstrap sources (`external_broad`)

| Source | License | Usage |
|--------|---------|-------|
| CC-CEDICT | CC BY-SA 4.0 | Core dictionary entries and pinyin |
| THUOCL | THUOCL custom open terms | Broad coverage and DF statistics |
| OpenCC STPhrases | Apache-2.0 | SC-TC phrase mapping |
| jieba `dict.txt` | MIT | Frequency ranking signal |
| Unicode Unihan | Unicode-3.0 | Character-level Mandarin fallback and single-char dictionaries |
| Wikipedia zh titles (ns0) | CC BY-SA 4.0 | Named-entity coverage |
| Wikimedia Pageviews Top (zh.wikipedia) | CC BY-SA 4.0 | Real-world usage heat signal |

See:
- `manifests/sources.public.yml`
- `attribution/ATTRIBUTION.md`

## Post-import optimization and filtering (external sources)
- Normalize and de-duplicate imported entries across heterogeneous source formats.
- Build weights from multiple signals (base frequency, DF/frequency side signals, and pageview heat) with balanced scaling.
- Damp low-signal named entities, likely personal names, and long-tail noise to reduce rare proper nouns crowding common phrases.
- Apply IME-oriented validity filters (for example renderability and script constraints) to keep outputs practical on mainstream Windows clients.
- Keep ranking behavior stable through rule-based corrections and regression sample checks.

## Directory layout
- `data/generated/`: generated lexicon files.
- `manifests/`: source/license manifests and regression samples.
- `scripts/`: build/validation/export helper scripts.
- `reports/`: generated build reports.
- `rules/`: export/release rules.

## Build and validation

```powershell
# Full rebuild (external_broad + unihan_single + regression checks)
.\rebuild_all.ps1

# Build one profile directly
.\scripts\build_external_seed.ps1 -Profile external_broad
```

## Constraints
- Public repository commit messages must be in English.
- Do not commit private raw corpus, drafts, or author manuscripts.
