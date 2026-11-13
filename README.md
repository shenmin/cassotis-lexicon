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

Lexicon build and release repository for Cassotis IME (言泉输入法): its simplified and traditional dictionaries and the statistical tables it ranks candidates with. Every installer of Cassotis IME includes them, so users need not download anything from here.

## Repository role
- Builds the simplified and traditional base dictionaries from open sources and project-maintained lists: the build scripts, the manifests and the generated files.
- Publishes, with each version, the statistical tables Cassotis IME imports beside the dictionaries: path priors, word transitions, character n-grams, completion indexes, word frequencies of general text and of everyday conversation, and the short-word promotion table.
- Rebuilds reproducibly from the external sources (`external_broad`).
- Keeps attribution and license files aligned with what is generated.

## Current dictionary snapshot (2026-11-13 build)

| File | Variant | Entries |
|------|---------|---------|
| `data/generated/dict_clean_sc.txt` | Simplified Chinese | 240,251 |
| `data/generated/dict_clean_tc.txt` | Traditional Chinese | 243,086 |
| `data/generated/dict_unihan_sc.txt` | Simplified single-char (Unihan) | 23,917 |
| `data/generated/dict_unihan_tc.txt` | Traditional single-char (Unihan) | 24,180 |

The traditional dictionary writes Taiwan's character forms (為, 裡, 著, 群, 吃) in every word of two characters or more; single characters keep their variants, so that they can still be typed on purpose. See the [form list](manifests/traditional_taiwan_forms.tsv).

Specialist coverage is added at low weights without raising existing word or character weights. Complete Pinyin can select uncommon technical terms, but catalogue-only entries do not participate in short-prefix or Tab predictions. Reviewed general-use expressions remain eligible for completion. See the [admission records](manifests/vertical/thuocl_specialist_admissions.tsv) and the separate [familiarity review](manifests/specialist_common_terms.tsv).

The dictionaries also hold 7,747 lines of classical verse: the school curriculum, 唐诗三百首, 千家诗 and 宋词三百首 (`manifests/curated_daily_supplement_phrases.tsv`). From two syllables on a line can be the one-key completion, typed in full it is the first candidate, and the continuation index then offers the next line (`manifests/classical_poetry_next_lines.tsv`).

## Ranking data for Cassotis IME

Beside the dictionaries, Cassotis Lexicon publishes the statistical tables that Cassotis IME imports into its local SQLite dictionaries. They are not directly inputable entries and are not counted in the snapshot above. They hold counts, word pairs and character n-grams, never sentences of the corpora, and the IME's benchmark cases are kept out of their sources. The IME's own models (its character language model, decision policies and structural rankers) are trained and shipped by the IME project and are described in its [Models and Ranking](https://github.com/shenmin/cassotis-ime#models-and-ranking).

Version ranges indicate identical published artifacts in the listed categories. Counts exclude file headers.

### Path statistics

| Version | Query-path priors (SC / TC) | Word-path transitions (SC / TC) | Forward character n-gram parameters (SC / TC) | Reverse character n-gram parameters (SC / TC) |
|---|---:|---:|---:|---:|
| `v2.7.0` | 23,603 / 22,749 | 904,762 / 833,694 | 698,694 / 697,033 | 2,538,336 / 2,538,261 |
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

The query-path priors and the word transitions (word bigrams and trigrams) are generated by the Lexicon build pipeline. Cassotis IME scores the word paths of long sentences with them, and its short-word and phrase paths read the transitions of a key. The forward and reverse smoothed character n-gram models were generated by the IME training tools and are versioned and distributed from this repository; the IME still imports them and reads them as statistical features beside its language model, for example in completion ranking and in the short-word promotion table.

How these tables grew:
- **v1.1.0** published the first corpus-trained statistical language-model data: word transitions and forward character n-grams.
- **v1.10.0** added conservative exact 1+2 and 2+1 word transitions backed by corpus evidence, improving three-syllable short-word continuation without admitting unsupported combinations.
- **v1.11.0** kept all existing transition weights and expanded independently counted exact 1+2, 2+1, 2+2, 2+3 and 3+2 transitions from cleaned novel, chat and large-scale Chinese corpora. Source support, competing paths and observed homophones are checked before an addition is retained.
- **v1.12.0** further expanded productive word transitions and added corpus-backed 1+1 relations between adjacent single-character segments. Existing exact two-character words are excluded; retained 1+1 relations require common readings and support from multiple independent sources.
- **v1.13.0** added reverse character n-gram models for bidirectional path scoring.
- **v1.14.0** refreshed the query-path priors for the exact-anchor and phrase-continuation paths of the IME.
- **v2.3.0** rewrote the traditional tables in Taiwan's character forms; rows that met their twin were merged.
- **v2.5.0** added pairs of words counted in 120 million characters of the general Chinese text the character model was trained on (FineWeb-Edu-Chinese, Ultra-FineWeb and Chinese Wikipedia; counts only), keeping every existing transition and its weight: 289,955 → 904,767 (SC) and 257,124 → 833,707 (TC). Only paths of two words of two characters or more were added, and six pairs of single characters. Added paths with a word of one character glued single characters to words as general text writes them and cost long-sentence first choices on fiction; most added pairs of single characters were fragments of general text that would have stood first on two-syllable keys; paths of three words changed almost nothing.
- **v2.6.0** and **v2.7.0** changed a few rows, mostly traditional ones, with the corrections of readings and of traditional character forms.

### Short-word promotion and word frequencies

| Version | Short-word promotion (SC / TC) | Word frequency (SC / TC) | Conversation frequency (SC / TC) |
|---|---:|---:|---:|
| `v2.7.0` | 1,529 / 1,781 | 201,868 / 204,020 | 106,115 / 107,002 |
| `v2.6.0` | 1,520 / 1,715 | 199,532 / 199,118 | — |
| `v2.5.0` | 1,498 / 1,692 | 199,072 / 198,640 | — |
| `v2.4.0` | 1,489 / 1,672 | — | — |
| `v2.3.0` | 1,488 / 1,668 | — | — |
| `v2.2.0` | 1,487 / 2,020 | — | — |
| `v2.1.0` | 1,466 / 2,002 | — | — |
| `v2.0.0` | 1,454 / 1,989 | — | — |

The short-word promotion table (`data/generated/dict_short_promotion_{sc,tc}.txt`) records, for queries of two to four syllables, which exact word goes above the dictionary's first when nothing but the dictionary decides. Cassotis IME writes it from each built dictionary with the one program that still carries the model it replaces (`out/rebuild_short_promotion.ps1` in the IME repository). A row records the words and weights it was decided among and applies only while they are unchanged, so a row left from an older dictionary is skipped, not wrong.

A word-frequency table for each variant (`data/generated/dict_word_frequency_{sc,tc}.txt`) records how often general Chinese text holds each word of two characters or more as a word, as `100 * log10(1 + occurrences)`; a traditional word takes the count of its simplified form. The counts (`manifests/general_word_counts.tsv`, made by `scripts/count_general_word_frequency.py`) come from the general corpora of the Cassotis IME character language model; a word counts where the text is cut into the fewest dictionary words, so a word inside a longer dictionary word is not counted. Words added to the dictionary later are counted on their own, only where they stand as words, and the other words keep their counts. Cassotis IME uses the table when it chooses among the words of one reading without context.

A conversation frequency table for each variant (`data/generated/dict_conversation_frequency_{sc,tc}.txt`) is made the same way from everyday conversation: the utterances of LCCC-large (Wang et al., "A Large-Scale Chinese Short-Text Conversation Dataset", NLPCC 2020; MIT License), counted as the general text is (`manifests/conversation_word_counts.tsv`, counts only). Without context, Cassotis IME uses it to keep the dictionary's first word in place where conversation writes that word far more often and the general text prefers the other word only slightly. LCCC filtered sensitive words, so a word it lacks is no evidence.

The IME's dictionary build fails on a database without any of these three tables: without them, short words would quietly be ranked worse.

### One-key completion data

| Version | Completion popularity priors (SC / TC) | Prefix lookup records (SC / TC) | Transition-completion index (SC / TC) |
|---|---:|---:|---:|
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

v1.16.0 added corpus-derived popularity priors and a precomputed Top-K prefix lookup index, allowing IME to distinguish popular completions from cold specialist terms without enumerating combinations at runtime. Popularity priors form an independently built snapshot, so their count need not match the current main dictionary. Prior records are not a count of eligible suggestions: rare specialist terms remain subject to separate short-prefix and Tab eligibility checks.

The build also derives a separate offline transition-completion index from strongly supported exact-word paths. It retains up to six vetted alternatives for each typed prefix. User completions remain the first priority; base-dictionary and transition suggestions are compared using popularity, context, and corpus evidence.

Additional static data for completion ranking and local continuation:

| Version | Completion competition priors (SC / TC) | Pairwise switch-audit records (SC / TC) | Long-sentence continuation index (SC / TC) |
|---|---:|---:|---:|
| `v2.3.0` - `v2.7.0` | 42,453 / 42,448 | 4,379 / 4,379 | 103,410 / 98,277 |
| `v2.2.0` | 42,453 / 42,448 | 4,379 / 4,379 | 103,410 / 98,278 |
| `v1.18.0` - `v2.1.0` | 42,453 / 42,448 | 4,379 / 4,379 | 97,589 / 92,457 |
| `v1.17.0` | 42,453 / 42,448 | 4,379 / 4,379 | 35,423 / 32,481 |

Since v1.17.0, competition priors and pairwise audits have supported completion selection and abstention, while a separate index supplies short continuations after stable word anchors; since v2.2.0 it also holds which line of a poem follows which. These are static lookup records, not additional dictionary entries or neural-network parameter counts.

## External sources and project-maintained supplements (`external_broad`)

### External sources

| Source | License | Usage |
|--------|---------|-------|
| Unicode Unihan | Unicode-3.0 | Character-level Mandarin fallback and single-char dictionaries |
| CC-CEDICT | CC BY-SA 4.0 | Core dictionary entries and pinyin |
| OpenCC STPhrases | Apache-2.0 | SC-TC phrase mapping |
| THUOCL | THUOCL custom open terms | Broad coverage and DF statistics |
| jieba `dict.txt` | MIT | Frequency ranking signal |
| FineWeb-Edu-Chinese v2.1, Ultra-FineWeb (zh), Chinese Wikipedia | Each dataset's terms; counts only | Word occurrence counts for the word-frequency table; character counts for the single-character order; word-pair counts for the word transitions |
| LCCC-large (Wang et al., NLPCC 2020) | MIT; counts only | Word occurrence counts for the conversation frequency table |
| Wiktionary zh titles (ns0) | CC BY-SA 4.0 | Daily wording, colloquial phrases, and chat-style lexical seeds |
| Wikipedia zh titles (ns0) | CC BY-SA 4.0 | Named-entity coverage and high-confidence proper-noun seeds |
| Wikimedia Pageviews Top (zh.wikipedia) | CC BY-SA 4.0 | Real-world usage heat signal |
| Wikidata zh historical people | CC0-1.0 | Conservative historical people-name supplements imported into the isolated people-name layer |
| Filtered `THUOCL_IT` subset | THUOCL custom open terms | Computing vertical-layer candidate source, filtered before import so it does not behave like the everyday/chat phrase layer |
| Filtered `THUOCL_chengyu` subset | THUOCL custom open terms | Idiom/allusion vertical-layer candidate source, filtered and weighted conservatively so idioms stay inputable without crowding everyday phrases |
| Getty AAT zh architectural terms | ODC-By 1.0 | Official architecture-term source imported conservatively into the isolated architecture-terms layer |
| Wikidata zh architectural elements / styles / landmarks | CC0-1.0 | Architecture-term and landmark-entity supplements imported into isolated architecture vertical layers |
| Wikidata zh countries / major cities / administrative territories / tourist landmarks | CC0-1.0 | Conservative place-name supplements for countries, regions, world cities, administrative places, scenic spots, and landmarks |
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
| Cassotis low-frequency daily supplements | Repository license (project-authored) | Useful exact-match daily-adjacent terms kept visible with a capped low-frequency weight so they do not crowd stronger common words |
| Cassotis word-level pinyin overrides | Repository license (project-authored) | Project-maintained pronunciation overrides used after source fusion to suppress noisy character-level fallback readings for polyphonic words across all layers |
| Cassotis curated fiction entities | Repository license (project-authored) | Project-maintained fiction entity list for novel characters, titles, and in-world named entities, kept separate from daily/chat phrasing and from general proper nouns |
| Cassotis curated proper nouns | Repository license (project-authored) | Project-maintained general non-person proper-noun list for titles, organizations, brands, platforms, products, and other real-world named entities that should not share the daily/chat preferred-term path |
| Cassotis curated people names | Repository license (project-authored) | Project-maintained contemporary public-figure and historical people-name list with explicit pinyin corrections, isolated from daily/chat phrasing and from non-person proper nouns |
| Cassotis curated place names / countries / cities / landmarks | Repository license (project-authored) | Project-maintained low-priority place-name lists used by the isolated `place_names` vertical layer, with explicit pinyin corrections for ambiguous domestic and international locations, countries/regions, world cities, and landmarks |
| Cassotis curated idioms and allusions | Repository license (project-authored) | Project-maintained high-value idiom and literary-allusion list kept separate from daily/chat phrase ranking |
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
- `manifests/curated_daily_supplement_phrases.tsv` stores useful exact-match supplements with capped low-frequency weights; entries in this layer should remain selectable but should not inherit daily/chat priority.
- Its optional fifth-column modes are applied after ranking and path statistics: `exact_zero` emits a true zero-weight exact row, `exact_rank` uses the non-negative manifest score as a fixed exact-candidate weight, `no_contains` leaves the word out of the runtime substring-popularity index, `exact_rank_no_contains` does both of the last two, and `exact_rank_exact_only` also gives the row no completions (it is found only when its whole reading is typed).
- `manifests/vertical_layers.public.json` declares isolated vertical terminology layers.
- `manifests/vertical/*.tsv` stores project-authored vertical term lists such as fiction entities, proper nouns, people names, place names, countries/regions, world cities, landmarks, idioms/allusions, computing vocabulary, civic/public-service terminology, architecture terminology/entities, gaming terminology, and game-development terminology.
- Vertical layers can add domain vocabulary without inheriting the same preferred-term bias used for daily/chat phrases.
- The fiction layer keeps novel characters, titles, and in-world named entities separate from everyday/chat phrasing and from general proper nouns.
- The active project-maintained proper-noun layer keeps non-person titles, organizations, brands, platforms, products, and general real-world named entities separate from everyday/chat phrasing.
- The people-name layer keeps public and historical human names separate from daily/chat phrasing, fiction entities, and non-person proper nouns; Wikidata-backed people-name entries are deliberately weighted conservatively so full-name input works without crowding common words.
- The place-name layer keeps common domestic and international locations, countries/regions, world cities, scenic spots, and landmarks inputable with conservative weights, so complete place-name input works without crowding everyday candidates.
- Wikidata-backed place supplements are intentionally weighted lower than curated entries; cold administrative places and landmarks should remain available on full input but should not dominate common words.
- The idioms/allusions layer currently combines a filtered `THUOCL_chengyu` subset with project-curated idioms and literary allusions, using conservative ranking so full idiom input works without inheriting daily/chat phrase priority.
- The computing layer currently combines a filtered `THUOCL_IT` subset with project-curated computing terminology.
- The civic layer currently contains project-curated taxation, housing, household-registration, and other public-service terminology.
- The architecture-terms layer currently combines project-curated terminology, Getty AAT architectural terms, and Wikidata architectural elements/styles.
- The architecture-entities layer currently combines project-curated architecture entities with a conservative Wikidata architectural-landmark supplement.
- The gaming layer currently combines project-curated gaming terms, Wikidata gaming entities, and filtered zhwiki/zhwiktionary gaming lexical titles.
- The game-development layer currently combines project-curated game-development terms, filtered Godot docs titles, a Wikidata game-engine supplement, and filtered zhwiki/zhwiktionary game-development lexical titles.
- The medicine layer currently combines project-curated medical terms, the MeSH descriptor catalog, MeSH-linked Wikidata entities, and a filtered `THUOCL_medical` subset while staying isolated from the daily/chat preferred-term path.

## Directory layout
- `data/generated/`: generated lexicon files, versioned statistical tables, the completion indexes, and the short-word promotion tables written by Cassotis IME.
- `manifests/`: source/license manifests and regression samples.
- `manifests/pinyin_overrides.sc.tsv`, `manifests/pinyin_overrides.tc.tsv`: project-authored word-level pronunciation overrides, one file per variant; neither applies to the other's texts.
- `manifests/vertical/`: project-authored isolated vertical term lists.
- `scripts/`: build/validation/export helper scripts.
- `reports/`: generated build reports.
- `rules/`: export/release rules.

## Build and validation

```powershell
# Full rebuild (external_broad + unihan_single + regression checks)
.\rebuild_all.ps1

# Optional: generate manual-review people-name candidates; this does not import them automatically
.\scripts\build_people_names_candidates.ps1

# Build one profile directly
.\scripts\build_external_seed.ps1 -Profile external_broad
```

Full rebuilds keep existing Unihan single-character weights stable when only
phrase dictionaries change. Use `-RefreshUnihanSingleCharWeights` only when
deliberately recalibrating the single-character ranking layer.

The single characters of each reading are ordered by how often modern text
uses them (`scripts/build_single_char_frequency.py`, 2026-10-27). Unihan's
frequencies, the Xiandai Hanyu Pinlu counts of the 1980s and school grades
had put rare characters above common ones under some readings. The step gives the weights a
reading already has to its characters again, the largest to the character
used most: in the general corpora of the character language model, counted
overall and standing alone outside dictionary words
(`manifests/general_char_counts.tsv`, made by
`scripts/count_general_char_frequency.py`), and standing alone in typed chat
messages, whose counts are not published. A character moves only under its
main reading, and the audited relative order and the regression samples
hold. Full rebuilds keep these weights; after
`-RefreshUnihanSingleCharWeights`, run the step again, then
`scripts/normalize_traditional_forms.py`.

`external_broad` and `external_cedict` automatically load
`manifests/vertical_layers.public.json` when present.
