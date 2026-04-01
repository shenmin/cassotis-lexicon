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
- Supports external-source bootstrap and private-corpus integration workflows.
- Keeps attribution and release policy files aligned with exported public artifacts.

## Current dictionary snapshot (2026-03-30 build)

| File | Variant | Entries |
|------|---------|---------|
| `data/generated/dict_clean_sc.txt` | Simplified Chinese | 156,800 |
| `data/generated/dict_clean_tc.txt` | Traditional Chinese | 173,555 |
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
| Getty AAT zh architectural terms | ODC-By 1.0 | Official architecture-term source imported conservatively into the isolated architecture-terms layer |
| Wikidata zh architectural elements / styles / landmarks | CC0-1.0 | Architecture-term and landmark-entity supplements imported into isolated architecture vertical layers |
| Wikidata zh video games / series / genres / consoles | CC0-1.0 | Main gaming-title/entity sources imported into an isolated gaming vertical layer |
| Filtered Wiktionary / Wikipedia zh gaming lexical titles | CC BY-SA 4.0 | Lightweight gaming-lexicon supplements imported conservatively into the gaming vertical layer |
| Godot Docs zh-cn title index | CC BY 3.0 | Main game-development terminology source, filtered before import into the isolated game-development layer |
| Wikidata zh game engines | CC0-1.0 | Game-engine entity supplement for the isolated game-development layer |
| MeSH descriptor catalog | NLM MeSH terms and conditions | Medical descriptor whitelist used to keep the medical vertical layer tied to recognized MeSH concepts |
| Wikidata zh medical entities (MeSH-linked) | CC0-1.0 | Chinese medical labels and aliases linked to MeSH descriptors, imported as the main medical-entity layer |
| Filtered `THUOCL_medical` subset | THUOCL custom open terms | Medical vertical-layer candidate source, filtered and weighted more conservatively than the MeSH-linked medical layer |

### Project-maintained supplements

| Supplement | License | Usage |
|-----------|---------|-------|
| Cassotis curated daily/chat phrases | Repository license (project-authored) | High-value everyday/chat phrasing that is worth keeping stable even when open sources miss it |
| Cassotis curated fiction entities | Repository license (project-authored) | Project-maintained fiction entity list for novel characters, titles, and in-world named entities, kept separate from daily/chat phrasing and from general proper nouns |
| Cassotis curated proper nouns | Repository license (project-authored) | Project-maintained general proper-noun list for names, titles, organizations, brands, and other real-world named entities that should not share the daily/chat preferred-term path |
| Cassotis curated computing terms | Repository license (project-authored) | Project-maintained computing/domain term list used by the isolated computing vertical layer; does not share the daily/chat preferred-term path |
| Cassotis curated civic terms | Repository license (project-authored) | Project-maintained civic/public-service terminology layer for taxation, housing, household-registration, and related administrative vocabulary, isolated from daily/chat preferred-term ranking |
| Cassotis curated architecture terms | Repository license (project-authored) | Project-maintained architecture terminology supplement used by the isolated architecture-terms layer |
| Cassotis curated architecture entities | Repository license (project-authored) | Project-maintained architecture entity supplement used by the isolated architecture-entity layer |
| Cassotis curated gaming terms | Repository license (project-authored) | Project-maintained gaming terminology supplement used by the isolated gaming vertical layer |
| Cassotis curated game development terms | Repository license (project-authored) | Project-maintained game-development terminology supplement used by the isolated game-development vertical layer |
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
- `manifests/vertical/*.tsv` stores project-authored vertical term lists such as fiction entities, proper nouns, computing vocabulary, civic/public-service terminology, architecture terminology/entities, gaming terminology, and game-development terminology.
- Vertical layers can add domain vocabulary without inheriting the same preferred-term bias used for daily/chat phrases.
- The fiction layer keeps novel characters, titles, and in-world named entities separate from everyday/chat phrasing and from general proper nouns.
- The active project-maintained proper-noun layer keeps names, titles, and general real-world named entities separate from everyday/chat phrasing.
- The computing layer currently combines a filtered `THUOCL_IT` subset with project-curated computing terminology.
- The civic layer currently contains project-curated taxation, housing, household-registration, and other public-service terminology.
- The architecture-terms layer currently combines project-curated terminology, Getty AAT architectural terms, and Wikidata architectural elements/styles.
- The architecture-entities layer currently combines project-curated architecture entities with a conservative Wikidata architectural-landmark supplement.
- The gaming layer currently combines project-curated gaming terms, Wikidata gaming entities, and filtered zhwiki/zhwiktionary gaming lexical titles.
- The game-development layer currently combines project-curated game-development terms, filtered Godot docs titles, a Wikidata game-engine supplement, and filtered zhwiki/zhwiktionary game-development lexical titles.
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
