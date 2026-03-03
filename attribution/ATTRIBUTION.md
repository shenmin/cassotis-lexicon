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

## Wikipedia zh titles (ns0)

- Name: Wikimedia zhwiki title dump (namespace 0)
- Homepage: https://dumps.wikimedia.org/zhwiki/latest/
- Download: https://dumps.wikimedia.org/zhwiki/latest/zhwiki-latest-all-titles-in-ns0.gz
- License: CC BY-SA 4.0 (as part of Wikimedia content licensing)
- Copyright holder: Wikimedia contributors

Notes:

- This repository uses titles as external ranking/coverage signals only.
- Raw dump files are not committed in this repository.
