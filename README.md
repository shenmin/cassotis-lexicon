# Cassotis Lexicon

<p align="center">
  <img src="cassotis_ime_yanquan.png" alt="Cassotis IME logo" width="280">
</p>

<p align="center">
  <a href="https://www.yanquan.org">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="readme_slogan_dark.svg">
      <img src="readme_slogan.svg" alt="翩若惊鸿，言如泉涌。" width="640">
    </picture>
  </a>
</p>

<p align="center">
  <a href="https://www.yanquan.org"><img src="https://img.shields.io/badge/website-yanquan.org-2a4374" alt="Website: yanquan.org"></a>
  <a href="https://github.com/shenmin/cassotis-lexicon/releases/latest"><img src="https://img.shields.io/github/v/release/shenmin/cassotis-lexicon?color=b0432f" alt="Latest release"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-CC%20BY--SA%204.0-blue" alt="License: CC BY-SA 4.0"></a>
</p>

**[Website: www.yanquan.org](https://www.yanquan.org)** | English | [简体中文](README.zh-Hans.md) | [繁體中文](README.zh-Hant.md) | [Cassotis IME](https://github.com/shenmin/cassotis-ime)

Build and release repository for the simplified and traditional base dictionaries and candidate-ranking statistical tables used by Cassotis IME (言泉输入法). All dictionaries and tables are bundled in the Cassotis IME installer, so end users do not need to download anything from this repository.

## Repository role
- Build the simplified and traditional base dictionaries from open lexical sources and project-maintained word lists (including build scripts, source manifests, and generated outputs).
- Publish the statistical tables imported by Cassotis IME alongside each release: path priors, word transitions, character n-grams, completion indexes, general and conversational word frequencies, and short-word promotion tables.
- Support reproducible rebuilds from external sources (`external_broad`).
- Keep attribution and license files synchronized with the generated artifacts.

## Current dictionary snapshot (2026-11-23 build)

| File | Variant | Entries |
|------|---------|---------|
| `data/generated/dict_clean_sc.txt` | Simplified Chinese | 245,607 |
| `data/generated/dict_clean_tc.txt` | Traditional Chinese | 248,174 |
| `data/generated/dict_unihan_sc.txt` | Simplified single-char (Unihan) | 24,161 |
| `data/generated/dict_unihan_tc.txt` | Traditional single-char (Unihan) | 24,351 |

Multi-character entries in the traditional dictionary use Taiwan standard character forms (為, 裡, 著, 群, 吃), while the single-character dictionary retains variant forms so they remain available when needed. See the [Taiwan form mapping](manifests/traditional_taiwan_forms.tsv).

Specialist vocabulary is added only for missing entries at low weights, without boosting existing words or characters. Uncommon technical terms can be selected by typing their full Pinyin, but catalog-only entries are excluded from short-prefix completions and Tab predictions by default; reviewed general-use expressions remain eligible for completion. See the [specialist admission records](manifests/vertical/thuocl_specialist_admissions.tsv) and the [common-term completion list](manifests/specialist_common_terms.tsv).

The dictionaries also include 7,747 lines of classical poetry drawn from school curricula, 唐诗三百首, 千家诗, and 宋词三百首 (`manifests/curated_daily_supplement_phrases.tsv`). Typing two or more leading syllables can trigger a full-line one-key completion; typing the full Pinyin places the line first among candidates, and the continuation index suggests the following line (`manifests/classical_poetry_next_lines.tsv`).

## Ranking data for Cassotis IME

Alongside the dictionaries, Cassotis Lexicon publishes statistical tables that Cassotis IME imports into its local SQLite dictionary databases. Because these tables provide ranking and completion signals rather than selectable entries, they are not counted in the dictionary snapshot above. They store only frequency counts, word pairs, and character n-grams—never raw corpus sentences—and all IME benchmark sets are excluded from their sources. The IME's own models (its character language model, decision policies, and structural rankers) are trained and distributed in the main IME repository; see [Models and Ranking](https://github.com/shenmin/cassotis-ime#models-and-ranking).

Version ranges below indicate identical published artifacts across those releases. Row counts exclude file headers.

### Path statistics

| Version | Query-path priors (SC / TC) | Word-path transitions (SC / TC) | Forward character n-gram parameters (SC / TC) | Reverse character n-gram parameters (SC / TC) |
|---|---:|---:|---:|---:|
| `v2.7.0` - `v2.8.0` | 23,603 / 22,749 | 904,762 / 833,694 | 698,694 / 697,033 | 2,538,336 / 2,538,261 |
| `v2.6.0` | 23,603 / 22,683 | 904,762 / 833,701 | 698,694 / 697,013 | 2,538,336 / 2,538,235 |
| `v2.5.0` | 23,603 / 22,681 | 904,767 / 833,707 | 698,694 / 697,013 | 2,538,336 / 2,538,235 |
| `v2.3.0` - `v2.4.0` | 23,603 / 22,681 | 289,955 / 257,124 | 698,694 / 697,013 | 2,538,336 / 2,538,235 |
| `v1.14.0` - `v2.2.0` | 23,603 / 22,723 | 289,955 / 257,125 | 698,694 / 698,777 | 2,538,336 / 2,539,067 |
| `v1.13.0` | 23,598 / 22,720 | 289,955 / 257,125 | 698,694 / 698,777 | 2,538,336 / 2,539,067 |
| `v1.12.0` | 23,593 / 22,717 | 289,955 / 257,125 | 698,694 / 698,777 | — |
| `v1.11.0` | 23,593 / 22,717 | 281,091 / 250,354 | 698,694 / 698,777 | — |
| `v1.10.0` | 23,593 / 22,717 | 161,543 / 151,204 | 698,694 / 698,777 | — |
| `v1.9.0` | 23,593 / 22,717 | 152,729 / 145,284 | 698,694 / 698,777 | — |
| `v1.8.1` | 23,580 / 22,732 | 152,729 / 145,284 | 698,694 / 698,777 | — |
| `v1.7.0` | 23,570 / 22,722 | 152,729 / 145,284 | 698,694 / 698,777 | — |
| `v1.6.0` | 23,557 / 22,669 | 152,729 / 145,284 | 698,694 / 698,777 | — |
| `v1.5.0` | 23,550 / 22,702 | 152,729 / 145,284 | 698,694 / 698,777 | — |
| `v1.4.0` | 23,545 / 22,697 | 152,729 / 145,284 | 698,694 / 698,777 | — |
| `v1.3.0` | 23,541 / 22,676 | 152,729 / 145,284 | 698,694 / 698,777 | — |
| `v1.2.0` | 23,529 / 22,663 | 152,729 / 145,284 | 698,694 / 698,777 | — |
| `v1.1.0` | 23,521 / 22,655 | 152,729 / 145,284 | 558,645 / 559,128 | — |
| `v1.0.0` | 23,518 / 22,653 | — | — | — |

Query-path priors and word-level bigram/trigram transitions are built by the Lexicon pipeline. Cassotis IME uses them to score multi-word paths in long sentences, as well as word transitions for short words and out-of-vocabulary phrases. The smoothed forward and reverse character n-gram models are generated by the IME training tools and versioned in this repository; the IME imports them as auxiliary statistical features alongside its main language model (for example, in completion ranking and short-word promotion).

Notable changes across releases:
- **v1.1.0**: Published the initial corpus-trained statistical tables (word transitions and forward character n-grams).
- **v1.10.0**: Added strictly filtered 1+2 and 2+1 exact-word transitions backed by corpus counts, improving three-syllable phrase joins without introducing spurious combinations.
- **v1.11.0**: Preserved all existing transition weights and expanded 1+2, 2+1, 2+2, 2+3, and 3+2 exact-word transitions using independent counts from cleaned fiction, chat, and web corpora, checking candidates against source support, competing paths, and homophone ambiguity.
- **v1.12.0**: Expanded high-utility multi-character transitions and added corpus-backed 1+1 transitions between adjacent single characters (excluding existing two-character dictionary words and requiring common readings supported by multiple independent sources).
- **v1.13.0**: Added reverse character n-gram models for bidirectional path scoring.
- **v1.14.0**: Updated query-path priors for exact-word anchoring and phrase continuation in the IME.
- **v2.3.0**: Converted traditional tables to Taiwan character forms and merged duplicate entries resulting from character normalization.
- **v2.5.0**: Expanded word-pair transitions from 120 million characters of general Chinese corpora used for the character language model (FineWeb-Edu-Chinese, Ultra-FineWeb, and Chinese Wikipedia; counts only), while preserving all existing transitions and weights (289,955 → 904,767 SC; 257,124 → 833,707 TC). This expansion includes only two-word combinations where each word has at least two characters, plus six common single-character pairs—excluding single-character attachments that hurt long-sentence accuracy on fiction, noisy single-character fragments that would misrank two-syllable inputs, and three-word transitions with negligible benefit.
- **v2.6.0** and **v2.7.0**: Updated a small number of rows (mostly in traditional tables) following pronunciation fixes and traditional form adjustments.

### Short-word promotion and word frequencies

| Version | Short-word promotion (SC / TC) | Word frequency (SC / TC) | Conversation frequency (SC / TC) |
|---|---:|---:|---:|
| `v2.8.0` | 1,563 / 1,818 | 204,521 / 206,666 | 108,403 / 109,284 |
| `v2.7.0` | 1,529 / 1,781 | 201,868 / 204,020 | 106,115 / 107,002 |
| `v2.6.0` | 1,520 / 1,715 | 199,532 / 199,118 | — |
| `v2.5.0` | 1,498 / 1,692 | 199,072 / 198,640 | — |
| `v2.4.0` | 1,489 / 1,672 | — | — |
| `v2.3.0` | 1,488 / 1,668 | — | — |
| `v2.2.0` | 1,487 / 2,020 | — | — |
| `v2.1.0` | 1,466 / 2,002 | — | — |
| `v2.0.0` | 1,454 / 1,989 | — | — |

The short-word promotion table (`data/generated/dict_short_promotion_{sc,tc}.txt`) precomputes, for two- to four-syllable queries, which exact-match word should be promoted above the dictionary's default top entry when ranking relies on the dictionary alone. Cassotis IME generates this table from each built dictionary (`out/rebuild_short_promotion.ps1` in the IME repository), replacing an earlier runtime residual model that is now compiled only into the offline builder. Each row stores the candidate set and weights it was computed from and applies only when they still match; stale rows from an older dictionary are safely ignored.

The general word-frequency table (`data/generated/dict_word_frequency_{sc,tc}.txt`) records standalone occurrences of multi-character words (two or more characters) in general Chinese text, scaled as `100 * log10(1 + occurrences)`; traditional entries use the counts of their simplified forms. Raw counts (`manifests/general_word_counts.tsv`, generated by `scripts/count_general_word_frequency.py`) are computed over the general corpora of the Cassotis IME character language model using minimum-word segmentation, so shorter words nested inside longer dictionary entries are not double-counted. Words added later are counted incrementally where they occur as standalone words, leaving existing counts unchanged. Cassotis IME consults this table when disambiguating homophone words without left context.

The conversation word-frequency table (`data/generated/dict_conversation_frequency_{sc,tc}.txt`) applies the same segmentation and scaling to everyday dialogue from LCCC-large (Wang et al., "A Large-Scale Chinese Short-Text Conversation Dataset", NLPCC 2020; MIT License; raw counts in `manifests/conversation_word_counts.tsv`). Without left context, Cassotis IME uses it to keep the dictionary's default top word when that word is far more common in conversation and general text only slightly favors a competing homophone. Because LCCC pre-filters sensitive words, absence from this table is treated as neutral rather than negative evidence.

The IME dictionary build requires all three tables and fails immediately if any is missing, preventing silent regressions in short-word ranking.

### One-key completion data

| Version | Completion popularity priors (SC / TC) | Prefix lookup records (SC / TC) | Transition-completion index (SC / TC) |
|---|---:|---:|---:|
| `v2.8.0` | 242,697 / 245,524 | 236,052 / 246,782 | 102,449 / 96,718 |
| `v2.7.0` | 240,025 / 242,859 | 235,393 / 246,144 | 102,449 / 96,718 |
| `v2.6.0` | 237,667 / 238,280 | 234,746 / 247,842 | 102,449 / 96,718 |
| `v2.5.0` | 237,008 / 237,623 | 234,723 / 247,814 | 102,449 / 96,718 |
| `v2.4.0` | 235,383 / 235,999 | 234,673 / 247,759 | 102,449 / 96,718 |
| `v2.3.0` | 234,553 / 235,166 | 234,210 / 247,298 | 102,449 / 96,718 |
| `v2.2.0` | 233,387 / 236,329 | 285,607 / 301,336 | 102,449 / 96,718 |
| `v2.1.0` | 225,735 / 228,687 | 255,450 / 271,267 | 102,449 / 96,718 |
| `v2.0.0` | 225,346 / 228,298 | 255,424 / 271,240 | 102,449 / 96,718 |
| `v1.31.0` | 225,221 / 228,173 | 255,410 / 271,226 | 102,449 / 96,718 |
| `v1.30.0` | 225,212 / 228,164 | 255,408 / 271,224 | 102,449 / 96,718 |
| `v1.29.0` | 225,201 / 228,153 | 255,405 / 271,221 | 102,449 / 96,718 |
| `v1.28.0` | 189,388 / 192,343 | 255,282 / 271,092 | 102,449 / 96,718 |
| `v1.27.0` | 189,355 / 192,310 | 255,268 / 271,078 | 102,449 / 96,718 |
| `v1.26.1` | 189,221 / 192,176 | 255,260 / 271,070 | 102,449 / 96,718 |
| `v1.26.0` | 189,214 / 192,169 | 255,259 / 271,069 | 102,449 / 96,718 |
| `v1.25.0` | 189,210 / 192,165 | 255,258 / 271,068 | 102,449 / 96,718 |
| `v1.24.0`<br/>`v1.23.0`<br/>`v1.21.0` | 189,301 / 192,193 | 255,560 / 271,145 | 102,449 / 96,718 |
| `v1.20.0` | 189,169 / 192,061 | 255,185 / 270,770 | 102,449 / 96,718 |
| `v1.19.0` | 189,120 / 192,012 | 255,185 / 270,770 | 102,449 / 96,718 |
| `v1.18.0` | 189,077 / 191,969 | 255,185 / 270,770 | 102,449 / 96,718 |
| `v1.17.0` | 189,033 / 191,925 | 255,162 / 270,747 | 102,449 / 96,718 |
| `v1.16.0` | 188,983 / 191,875 | 255,129 / 270,714 | 102,449 / 96,718 |
| `v1.15.0` | — | — | 54,305 / 51,875 |

v1.16.0 introduced corpus-derived popularity priors and a precomputed Top-K prefix lookup index, allowing the IME to separate common completions from rare technical terms without enumerating combinations at runtime. Because popularity priors are built as an independent snapshot, their row count need not match the main dictionary size, nor does it equal the number of active suggestions—rare specialist terms remain subject to separate short-prefix and Tab eligibility rules.

The build pipeline also generates an offline transition-completion index from well-attested exact-word paths, retaining up to six vetted candidates per input prefix. At runtime, user completions take top priority, while base-dictionary and transition completions are ranked using popularity, left context, and corpus evidence.

Additional static tables for completion ranking and local continuation:

| Version | Completion competition priors (SC / TC) | Pairwise switch-audit records (SC / TC) | Long-sentence continuation index (SC / TC) |
|---|---:|---:|---:|
| `v2.3.0` - `v2.8.0` | 42,453 / 42,448 | 4,379 / 4,379 | 103,410 / 98,277 |
| `v2.2.0` | 42,453 / 42,448 | 4,379 / 4,379 | 103,410 / 98,278 |
| `v1.18.0` - `v2.1.0` | 42,453 / 42,448 | 4,379 / 4,379 | 97,589 / 92,457 |
| `v1.17.0` | 42,453 / 42,448 | 4,379 / 4,379 | 35,423 / 32,481 |

Since v1.17.0, competition priors and pairwise switch-audit records have guided completion selection and confidence-based abstention, while the continuation index supplies short phrase continuations after stable word anchors; since v2.2.0, the continuation index also maps consecutive lines of classical poetry. All three are static lookup tables rather than dictionary entries or neural network parameters.

## External sources and project-maintained supplements (`external_broad`)

### External sources

| Source | License | Usage |
|--------|---------|-------|
| Unicode Unihan | Unicode-3.0 | Character-level Mandarin fallback readings and single-character dictionaries |
| CC-CEDICT | CC BY-SA 4.0 | Core dictionary entries and Pinyin readings |
| OpenCC STPhrases | Apache-2.0 | Simplified–traditional phrase mapping |
| THUOCL | THUOCL custom open terms | Vocabulary coverage and document-frequency (DF) signals |
| jieba `dict.txt` | MIT | Base frequency ranking signal |
| FineWeb-Edu-Chinese v2.1, Ultra-FineWeb (zh), Chinese Wikipedia | Each dataset's terms; counts only | Word counts for the general word-frequency table, character counts for single-character ranking, and word-pair counts for transition tables |
| LCCC-large (Wang et al., NLPCC 2020) | MIT; counts only | Word counts for the conversation word-frequency table |
| Wiktionary zh titles (ns0) | CC BY-SA 4.0 | Everyday expressions, colloquial phrases, and conversational lexical seeds |
| Wikipedia zh titles (ns0) | CC BY-SA 4.0 | Named-entity coverage and high-confidence proper-noun seeds |
| Wikimedia Pageviews Top (zh.wikipedia) | CC BY-SA 4.0 | Wikipedia pageview popularity signal |
| Wikidata zh historical people | CC0-1.0 | Historical person names imported at conservative weights into the isolated `people_names` layer |
| Filtered `THUOCL_IT` subset | THUOCL custom open terms | Computing terminology candidates for the `computing` layer, filtered before import to stay separate from everyday/chat phrases |
| Filtered `THUOCL_chengyu` subset | THUOCL custom open terms | Idiom and allusion candidates for the `idioms_allusions` layer, filtered and weighted conservatively so full idioms stay selectable without crowding everyday phrases |
| Getty AAT zh architectural terms | ODC-By 1.0 | Authoritative architectural terminology imported conservatively into the `architecture_terms` layer |
| Wikidata zh architectural elements / styles / landmarks | CC0-1.0 | Architectural element, style, and landmark supplements imported into the isolated architecture layers |
| Wikidata zh countries / major cities / administrative territories / tourist landmarks | CC0-1.0 | Place-name supplements for countries, regions, major cities, administrative divisions, and landmarks at conservative weights |
| Wikidata zh video games / series / genres / consoles | CC0-1.0 | Primary game-title and entity sources for the isolated `gaming` layer |
| Filtered Wiktionary / Wikipedia zh gaming lexical titles | CC BY-SA 4.0 | Filtered gaming vocabulary supplements imported conservatively into the `gaming` layer |
| Godot Docs zh-cn title index | CC BY 3.0 | Primary game-development terminology source, filtered before import into the `game_dev` layer |
| Wikidata zh game engines | CC0-1.0 | Game-engine entity supplements for the `game_dev` layer |
| MeSH descriptor catalog | NLM MeSH terms and conditions | MeSH concept whitelist anchoring the `medicine` layer to recognized medical descriptors |
| Wikidata zh medical entities (MeSH-linked) | CC0-1.0 | MeSH-linked Chinese medical terms and aliases imported as the primary medical-entity source |
| Filtered `THUOCL_medical` subset | THUOCL custom open terms | Supplementary medical vocabulary filtered and weighted more conservatively than MeSH-linked entries |

### Project-maintained supplements

| Supplement | License | Usage |
|-----------|---------|-------|
| Cassotis curated daily/chat phrases | Repository license (project-authored) | High-utility everyday and chat expressions missed by open lexical sources |
| Cassotis low-frequency daily supplements | Repository license (project-authored) | Practical lower-frequency exact-match entries with capped weights so they do not crowd common words |
| Cassotis word-level pinyin overrides | Repository license (project-authored) | Word-level pronunciation overrides applied after source merging to fix erroneous character-level fallback readings for polyphonic words |
| Cassotis curated fiction entities | Repository license (project-authored) | Novel characters, work titles, and fictional entities kept separate from daily/chat phrases and general proper nouns |
| Cassotis curated proper nouns | Repository license (project-authored) | Non-person proper nouns (titles, organizations, brands, platforms, products) isolated from daily/chat priority ranking |
| Cassotis curated people names | Repository license (project-authored) | Contemporary public figures and historical names with verified Pinyin readings, isolated from daily phrases and non-person proper nouns |
| Cassotis curated place names / countries / cities / landmarks | Repository license (project-authored) | Low-priority place-name lists for the isolated `place_names` layer, with verified Pinyin readings for polyphonic domestic and international locations, countries/regions, cities, and landmarks |
| Cassotis curated idioms and allusions | Repository license (project-authored) | Common idioms and literary allusions kept separate from daily/chat phrase ranking |
| Cassotis curated computing terms | Repository license (project-authored) | Computing and technical terminology for the isolated `computing` layer |
| Cassotis curated civic terms | Repository license (project-authored) | Taxation, housing, household-registration, and public-service terminology in the isolated `civic` layer |
| Cassotis curated architecture terms | Repository license (project-authored) | Architectural terminology supplement for the isolated `architecture_terms` layer |
| Cassotis curated architecture entities | Repository license (project-authored) | Landmark buildings and architects supplement for the isolated `architecture_entities` layer |
| Cassotis curated gaming terms | Repository license (project-authored) | Gaming vocabulary supplement for the isolated `gaming` layer |
| Cassotis curated game development terms | Repository license (project-authored) | Game-development terminology supplement for the isolated `game_dev` layer |
| Cassotis curated medical terms | Repository license (project-authored) | Common medical vocabulary and pronunciation overrides for the isolated `medicine` layer |

See:
- `manifests/sources.public.yml`
- `attribution/ATTRIBUTION.md`

## Post-import optimization and filtering (external sources)
- Normalize and deduplicate entries imported from heterogeneous source formats.
- Compute balanced entry weights from base frequency, document frequency (DF), and Wikipedia pageview signals.
- Extract shorter colloquial prefixes from well-attested multi-word expressions so common sentence pivots and connectors surface earlier.
- Downweight weakly supported named entities, suspected personal names, and long-tail noise so rare proper nouns do not crowd everyday words.
- Apply IME-specific validity checks (such as glyph renderability and script constraints) for mainstream Windows applications.
- Verify ranking stability across releases through rule-based overrides and regression test suites.

## Coverage focus
- Prioritize natural everyday wording and conversational input rather than transient web buzzwords.
- Draw on open lexical sources to cover common short expressions, sentence pivots, modal particles, and spoken connectors.
- Maintain a compact project whitelist for high-utility everyday phrases missing from open sources.
- Treat named entities and pageview spikes as secondary signals so they do not dominate core typing paths.

## Layering policy
- `manifests/curated_daily_phrases.tsv`: Reserved for everyday and chat expressions that receive priority weighting in daily typing.
- `manifests/curated_daily_supplement_phrases.tsv`: Stores lower-frequency everyday supplements with capped weights so complete Pinyin matches remain selectable without inheriting daily/chat priority.
- Optional fifth-column modes in `curated_daily_supplement_phrases.tsv` apply after standard ranking and path statistics: `exact_zero` emits a zero-weight exact-match entry; `exact_rank` uses the manifest's non-negative score directly as a fixed exact-candidate weight; `no_contains` excludes the entry from the runtime substring-popularity index; `exact_rank_no_contains` combines `exact_rank` and `no_contains`; and `exact_rank_exact_only` additionally disables prefix completion (matching only when the full Pinyin is typed).
- `manifests/vertical_layers.public.json` declares isolated domain layers and their sources, while `manifests/vertical/*.tsv` stores project-maintained domain word lists. Vertical layers add domain vocabulary without inheriting daily/chat priority weighting:
  - Fiction entities (`fiction_entities`): Novel characters, titles, and fictional terms kept separate from everyday phrases and general proper nouns.
  - Proper nouns (`proper_nouns`): Non-person titles, organizations, brands, platforms, products, and other real-world named entities.
  - People names (`people_names`): Public figures and historical names isolated from fiction entities and non-person proper nouns; Wikidata-sourced names use conservative weights so full-name input works without crowding common words.
  - Place names (`place_names`): Domestic and international locations, countries/regions, major cities, scenic spots, and landmarks at conservative weights; Wikidata place supplements are weighted below curated entries so uncommon administrative divisions and landmarks appear on full input without displacing common words.
  - Idioms and allusions (`idioms_allusions`): Filtered `THUOCL_chengyu` entries combined with curated idioms and literary allusions at conservative weights.
  - Computing (`computing`): Filtered `THUOCL_IT` entries combined with curated computing terminology.
  - Civic (`civic`): Curated taxation, housing, household-registration, and public-service terminology.
  - Architecture (`architecture_terms` and `architecture_entities`): `architecture_terms` combines curated terminology, Getty AAT architectural terms, and Wikidata architectural elements/styles; `architecture_entities` combines curated landmarks/architects with conservatively weighted Wikidata landmarks.
  - Gaming (`gaming`): Curated gaming terms, Wikidata game entities, and filtered Chinese Wikipedia/Wiktionary (`zhwiki`/`zhwiktionary`) gaming entries.
  - Game development (`game_dev`): Curated game-development terms, filtered Chinese Godot documentation titles, Wikidata game engines, and filtered `zhwiki`/`zhwiktionary` entries.
  - Medicine (`medicine`): Curated medical terms, the MeSH descriptor catalog, MeSH-linked Wikidata medical entities, and a filtered `THUOCL_medical` subset.

## Directory layout
- `data/generated/`: Generated dictionary files, versioned statistical tables, completion indexes, and short-word promotion tables produced by Cassotis IME.
- `manifests/`: Source/license manifests and regression test samples.
- `manifests/pinyin_overrides.sc.tsv`, `manifests/pinyin_overrides.tc.tsv`: Project-maintained word-level pronunciation overrides, maintained separately for simplified and traditional variants without cross-applying.
- `manifests/vertical/`: Project-maintained isolated domain word lists.
- `scripts/`: Build, validation, and export scripts.
- `reports/`: Generated build reports.
- `rules/`: Export and release policy rules.

## Build and validation

```powershell
# Full rebuild (external_broad + unihan_single + regression checks)
.\rebuild_all.ps1

# Optional: generate manual-review people-name candidates; this does not import them automatically
.\scripts\build_people_names_candidates.ps1

# Build one profile directly
.\scripts\build_external_seed.ps1 -Profile external_broad
```

Standard full rebuilds keep existing Unihan single-character weights unchanged when only multi-character dictionaries are updated. Pass `-RefreshUnihanSingleCharWeights` only when intentionally recalibrating single-character ordering.

Single characters under each Pinyin reading are ordered by modern corpus frequency (`scripts/build_single_char_frequency.py`, 2026-10-27). Earlier ordering relied on Unihan frequency fields, 1980s frequency-dictionary counts, and school-grade lists, which placed rare characters ahead of everyday ones under several readings. The script redistributes each reading's existing weight pool across its characters in order of modern usage, combining total occurrences and standalone occurrences outside multi-character words in the general corpora of the character language model (`manifests/general_char_counts.tsv`, generated by `scripts/count_general_char_frequency.py`), together with private standalone character counts from chat messages. Each character is reordered only under its primary reading, preserving audited relative-order overrides and regression test constraints.

In the traditional dictionary, single characters that map to the same simplified character share identical simplified-corpus counts, and the character language model also scores traditional text via simplified characters. Under their primary reading, these shared-form characters are ordered by their observed usage share in traditional text, measured after converting the general corpora sentence by sentence with OpenCC (`manifests/traditional_char_shares.tsv`, generated by `scripts/count_traditional_char_shares.py`, and applied by `scripts/order_traditional_shared_chars.py`). Variant forms unused in Taiwan text are placed below attested forms, and a few polyphonic characters with nearly tied reading weights have their primary reading assigned manually. Standard full rebuilds preserve these weights; after running `-RefreshUnihanSingleCharWeights`, re-run both single-character ordering scripts followed by `scripts/normalize_traditional_forms.py`.

`external_broad` and `external_cedict` automatically load `manifests/vertical_layers.public.json` when present.
