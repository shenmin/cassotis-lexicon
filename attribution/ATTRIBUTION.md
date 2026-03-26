# Attribution (Public)

This repository may publish generated lexicon artifacts that include entries
derived from external open data sources.

## CC-CEDICT

- Name: CC-CEDICT Chinese-English Dictionary
- Homepage: https://www.mdbg.net/chinese/dictionary?page=cc-cedict
- Download: https://www.mdbg.net/chinese/export/cedict/cedict_1_0_ts_utf-8_mdbg.txt.gz
- License: CC BY-SA 4.0
- Copyright holder: MDBG and CC-CEDICT contributors

Notes:

- The raw source file is not committed in this repository.
- This repository stores transformed dictionary artifacts only.

## THUOCL

- Name: THUOCL (Tsinghua Open Chinese Lexicon)
- Homepage: https://github.com/thunlp/THUOCL
- Download: https://github.com/thunlp/THUOCL/archive/refs/heads/master.zip
- License: THUOCL custom open terms (see upstream README)
- Copyright holder: THUNLP and THUOCL contributors

Notes:

- THUOCL is used as an external broad-coverage word list with DF statistics.
- Filtered `THUOCL_IT` and `THUOCL_medical` subsets are also used as isolated
  vertical-layer candidate sources.
- The raw source archive is not committed in this repository.

## jieba dict.txt

- Name: jieba dictionary (`jieba/dict.txt`)
- Homepage: https://github.com/fxsjy/jieba
- Download: https://raw.githubusercontent.com/fxsjy/jieba/master/jieba/dict.txt
- License: MIT
- Copyright holder: Sun Junyi and jieba contributors

Notes:

- jieba word frequencies are used as ranking signal in external broad profile.
- Raw source file is not committed in this repository.

## OpenCC STPhrases

- Name: OpenCC dictionary (STPhrases)
- Homepage: https://github.com/BYVoid/OpenCC
- Download: https://raw.githubusercontent.com/BYVoid/OpenCC/master/data/dictionary/STPhrases.txt
- License: Apache-2.0
- Copyright holder: OpenCC contributors

## Unicode Unihan (Readings)

- Name: Unicode Unihan Database (`Unihan_Readings.txt`)
- Homepage: https://www.unicode.org/ucd/
- Download: https://www.unicode.org/Public/UCD/latest/ucd/Unihan.zip
- License: Unicode-3.0
- Copyright holder: Unicode Consortium

## Wiktionary zh titles (ns0)

- Name: Wikimedia zhwiktionary title dump (namespace 0)
- Homepage: https://dumps.wikimedia.org/zhwiktionary/latest/
- Download: https://dumps.wikimedia.org/zhwiktionary/latest/zhwiktionary-latest-all-titles-in-ns0.gz
- License: CC BY-SA 4.0 (as part of Wikimedia content licensing)
- Copyright holder: Wikimedia contributors

Notes:

- This repository uses titles as lexical seeds for daily wording, colloquial phrases, and chat-style expressions.
- Raw dump files are not committed in this repository.

## Wikipedia zh titles (ns0)

- Name: Wikimedia zhwiki title dump (namespace 0)
- Homepage: https://dumps.wikimedia.org/zhwiki/latest/
- Download: https://dumps.wikimedia.org/zhwiki/latest/zhwiki-latest-all-titles-in-ns0.gz
- License: CC BY-SA 4.0 (as part of Wikimedia content licensing)
- Copyright holder: Wikimedia contributors

Notes:

- This repository uses titles as external ranking/coverage signals only.
- Raw dump files are not committed in this repository.

## Wikimedia Pageviews Top (zh.wikipedia)

- Name: Wikimedia REST Pageviews Top API (zh.wikipedia)
- Homepage: https://wikitech.wikimedia.org/wiki/Analytics/AQS/Pageviews
- Endpoint: https://wikimedia.org/api/rest_v1/metrics/pageviews/top/zh.wikipedia/all-access/{year}/{month}/all-days
- License: CC BY-SA 4.0 (as part of Wikimedia content licensing)
- Copyright holder: Wikimedia contributors

Notes:

- This repository uses aggregated monthly top-pageview counts as ranking signal only.
- API responses are cached locally during build and are not committed as raw source dumps.

## MeSH descriptor catalog

- Name: Medical Subject Headings (MeSH) descriptor catalog
- Homepage: https://www.nlm.nih.gov/mesh/meshhome.html
- Download: https://nlmpubs.nlm.nih.gov/projects/mesh/MESH_FILES/xmlmesh/desc2026.xml
- License: NLM MeSH terms and conditions
- Copyright holder: U.S. National Library of Medicine

Notes:

- This repository uses MeSH descriptor records as the medical concept whitelist
  for the isolated medicine vertical layer.
- The raw XML catalog is cached locally during build and is not committed in
  this repository.

## Wikidata zh medical entities (MeSH-linked)

- Name: Wikidata Query Service medical entities (Chinese labels/aliases linked to MeSH)
- Homepage: https://www.wikidata.org/wiki/Wikidata:Main_Page
- Endpoint: https://query.wikidata.org/sparql
- License: CC0-1.0
- Copyright holder: Wikidata contributors

Notes:

- This repository queries Chinese labels and aliases for Wikidata items that
  expose a linked MeSH descriptor ID.
- Query results are filtered against the imported MeSH descriptor catalog before
  they are used in the isolated medicine vertical layer.
- Query responses are cached locally during build and are not committed as raw
  source dumps.
