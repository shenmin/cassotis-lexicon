# Cassotis Lexicon

<p align="center">
  <img src="cassotis_ime_yanquan.png" alt="Cassotis IME logo" width="280">
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-CC%20BY--SA%204.0-blue" alt="License: CC BY-SA 4.0"></a>
</p>

English | [简体中文](README.CN.md)

Open-source lexicon artifacts and build pipeline for Cassotis IME.

## Dictionaries (2026-03-06 build)

| File | Variant | Entries |
|------|---------|---------|
| `data/generated/dict_clean_sc.txt` | Simplified Chinese | 112,606 |
| `data/generated/dict_clean_tc.txt` | Traditional Chinese | 97,248 |
| `data/generated/dict_unihan_sc.txt` | Simplified single-char (Unihan) | 30,397 |
| `data/generated/dict_unihan_tc.txt` | Traditional single-char (Unihan) | 31,009 |

## Format

Each dictionary file is UTF-8 TSV (no header):

```text
pinyin<TAB>text<TAB>weight
```

Example:

```text
zhongguo	中国	666
rengongzhineng	人工智能	590
```

- `pinyin`: tone-stripped ASCII pinyin key
- `text`: Chinese candidate (single character or multi-character term)
- `weight`: ranking score (higher means higher priority)

## Build profiles

Defined in `manifests/profiles.public.yml`:

| Profile | Description |
|---------|-------------|
| `external_broad` (default) | CC-CEDICT + THUOCL + OpenCC + jieba + Unihan + zh titles + pageviews |
| `external_cedict` | CC-CEDICT only |
| `clean_permissive` | OpenCC STPhrases + Unihan only |

## Data sources (`external_broad`)

| Source | License | Usage |
|--------|---------|-------|
| CC-CEDICT | CC BY-SA 4.0 | Core entries and pinyin |
| THUOCL | THUOCL custom open terms | Coverage and DF signal |
| OpenCC STPhrases | Apache-2.0 | SC-TC phrase mapping |
| jieba `dict.txt` | MIT | Frequency signal |
| Unicode Unihan | Unicode-3.0 | Character-level reading fallback |
| Wikipedia zh titles (ns0) | CC BY-SA 4.0 | Named-entity coverage |
| Wikimedia Pageviews Top (zh.wikipedia) | CC BY-SA 4.0 | Real-world popularity signal |

See details in:
- `manifests/sources.public.yml`
- `attribution/ATTRIBUTION.md`

## Post-import optimization and filtering
- Normalize and de-duplicate imported entries from heterogeneous external sources.
- Build ranking weights from combined signals (base frequency, DF/frequency side signals, and pageview heat) with balanced scaling.
- Dampen low-signal named entities and long-tail noise so rare proper nouns do not crowd common terms.
- Apply IME-oriented validity filters (for example renderability and script constraints) to keep candidates practical on mainstream Windows clients.
- Stabilize ranking behavior through rule-based corrections plus regression sample checks.

## Build

Prerequisites: Python 3.8+, PowerShell 7+

```powershell
# Full rebuild (external_broad + unihan_single + regression checks)
.\rebuild_all.ps1

# Or build a single profile
.\scripts\build_external_seed.ps1 -Profile external_broad
.\scripts\build_external_seed.ps1 -Profile external_cedict
.\scripts\build_external_seed.ps1 -Profile clean_permissive
```

## License

This repository is licensed under **CC BY-SA 4.0**. See [LICENSE](LICENSE).
