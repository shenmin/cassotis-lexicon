# Cassotis Lexicon

English | [简体中文](README.CN.md)

Lexicon build and release repository for Cassotis IME.

## Repository role
- Maintains lexicon build scripts, manifests, and generated outputs.
- Supports external-source bootstrap and private-corpus integration workflows.
- Keeps attribution and release policy files aligned with exported public artifacts.

## Current dictionary snapshot (2026-03-27 build)

| File | Variant | Entries |
|------|---------|---------|
| `data/generated/dict_clean_sc.txt` | Simplified Chinese | 143,725 |
| `data/generated/dict_clean_tc.txt` | Traditional Chinese | 156,914 |
| `data/generated/dict_unihan_sc.txt` | Simplified single-char (Unihan) | 23,909 |
| `data/generated/dict_unihan_tc.txt` | Traditional single-char (Unihan) | 24,064 |

## External sources and project-maintained supplements (`external_broad`)

### External sources

| Source | License | Usage |
|--------|---------|-------|
| Unicode Unihan | Unicode-3.0 | Character-level Mandarin fallback and single-char dictionaries |
| CC-CEDICT | CC BY-SA 4.0 | Core dictionary entries and pinyin |
| OpenCC STPhrases | Apache-2.0 | SC-TC phrase mapping |
| THUOCL | THUOCL custom open terms | Broad coverage and DF statistics |
| jieba `dict.txt` | MIT | Frequency ranking signal |
| Wiktionary zh titles (ns0) | CC BY-SA 4.0 | Daily wording, colloquial phrases, and chat-style lexical seeds |
| Wikipedia zh titles (ns0) | CC BY-SA 4.0 | Named-entity coverage and high-confidence proper-noun seeds |
| Wikimedia Pageviews Top (zh.wikipedia) | CC BY-SA 4.0 | Real-world usage heat signal |
| Filtered `THUOCL_IT` subset | THUOCL custom open terms | Computing vertical-layer candidate source, filtered before import so it does not behave like the everyday/chat phrase layer |
| MeSH descriptor catalog | NLM MeSH terms and conditions | Medical descriptor whitelist used to keep the medical vertical layer tied to recognized MeSH concepts |
| Wikidata zh medical entities (MeSH-linked) | CC0-1.0 | Chinese medical labels and aliases linked to MeSH descriptors, imported as the main medical-entity layer |
| Filtered `THUOCL_medical` subset | THUOCL custom open terms | Medical vertical-layer candidate source, filtered and weighted more conservatively than the MeSH-linked medical layer |

### Project-maintained supplements

| Supplement | License | Usage |
|-----------|---------|-------|
| Cassotis curated daily/chat phrases | Repository license (project-authored) | High-value everyday/chat phrasing that is worth keeping stable even when open sources miss it |
| Cassotis curated proper nouns | Repository license (project-authored) | Project-maintained proper-noun list for names, titles, organizations, and other specific entities that should not share the daily/chat preferred-term path |
| Cassotis curated computing terms | Repository license (project-authored) | Project-maintained computing/domain term list used by the isolated computing vertical layer; does not share the daily/chat preferred-term path |
| Cassotis curated medical terms | Repository license (project-authored) | Project-maintained medical supplement used for high-value medical terms and explicit pinyin corrections that should remain isolated from the daily/chat preferred-term path |

See:
- `manifests/sources.public.yml`
- `attribution/ATTRIBUTION.md`

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

## Layering policy
- `manifests/curated_daily_phrases.tsv` is reserved for everyday/chat phrasing that should receive daily-use preference treatment.
- `manifests/vertical_layers.public.json` declares isolated vertical terminology layers.
- `manifests/vertical/*.tsv` stores project-authored vertical term lists such as proper nouns and computing vocabulary.
- Vertical layers can add domain vocabulary without inheriting the same preferred-term bias used for daily/chat phrases.
- The active project-maintained proper-noun layer keeps names, titles, and in-world entities separate from everyday/chat phrasing.
- The computing layer currently combines a filtered `THUOCL_IT` subset with project-curated computing terminology.
- The medicine layer currently combines project-curated medical terms, the MeSH descriptor catalog, MeSH-linked Wikidata entities, and a filtered `THUOCL_medical` subset while staying isolated from the daily/chat preferred-term path.

## Directory layout
- `data/generated/`: generated lexicon files.
- `manifests/`: source/license manifests and regression samples.
- `manifests/vertical/`: project-authored isolated vertical term lists.
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

`external_broad` and `external_cedict` automatically load
`manifests/vertical_layers.public.json` when present.

## Constraints
- Public repository commit messages must be in English.
- Do not commit private raw corpus, drafts, or author manuscripts.
