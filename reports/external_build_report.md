# External Build Report

- profile: external_cedict
- generated_at_utc: 2026-03-25T01:27:24+00:00
- min_hanzi: 2
- max_entries: unlimited

## Sources
- cc-cedict: CC-CEDICT
  - license: CC BY-SA 4.0
  - risk_level: medium
  - redistribution_class: copyleft_sharealike
  - url: https://www.mdbg.net/chinese/export/cedict/cedict_1_0_ts_utf-8_mdbg.txt.gz

## Parse stats
- filtered_short: 27355
- invalid_format: 0
- invalid_pinyin: 0
- lexical_seed_augmented_sc_terms: 0
- lexical_seed_augmented_tc_terms: 0
- parsed_lines: 124444
- sc_filtered_non_windows_cjk: 698
- sc_global_tail_constituent_mismatch_removed: 0
- sc_global_tail_literary_removed: 0
- sc_global_tail_modernity_risk_removed: 0
- sc_global_tail_named_removed: 0
- sc_global_tail_rare_char_removed: 0
- sc_global_tail_removed: 0
- sc_global_tail_written_removed: 0
- sc_homophone_buckets: 13655
- sc_homophone_daily_phrase_boosted: 0
- sc_homophone_daily_phrase_damped: 0
- sc_homophone_dominant_common_boosted: 0
- sc_homophone_dominant_common_damped: 0
- sc_homophone_entries_adjusted: 36625
- sc_homophone_entries_boosted: 17329
- sc_homophone_entries_damped: 19296
- sc_homophone_inflated_short_penalized: 0
- sc_homophone_literary_penalized: 86
- sc_homophone_modernity_risk_penalized: 0
- sc_homophone_rare_form_penalized: 0
- sc_homophone_sparse_penalized: 0
- sc_homophone_written_tail_penalized: 0
- sc_low_signal_literary_removed: 0
- sc_low_signal_named_removed: 0
- sc_low_signal_rare_buckets: 0
- sc_low_signal_rare_removed: 0
- sc_low_signal_written_removed: 0
- sc_multi_pronunciation_damped: 42
- sc_multi_pronunciation_penalty_total: 11635
- sc_multi_pronunciation_terms: 41
- tc_filtered_non_windows_cjk: 679
- tc_global_tail_constituent_mismatch_removed: 0
- tc_global_tail_literary_removed: 0
- tc_global_tail_modernity_risk_removed: 0
- tc_global_tail_named_removed: 0
- tc_global_tail_rare_char_removed: 0
- tc_global_tail_removed: 0
- tc_global_tail_written_removed: 0
- tc_homophone_buckets: 13804
- tc_homophone_daily_phrase_boosted: 0
- tc_homophone_daily_phrase_damped: 0
- tc_homophone_dominant_common_boosted: 0
- tc_homophone_dominant_common_damped: 0
- tc_homophone_entries_adjusted: 37012
- tc_homophone_entries_boosted: 17750
- tc_homophone_entries_damped: 19262
- tc_homophone_inflated_short_penalized: 0
- tc_homophone_literary_penalized: 83
- tc_homophone_modernity_risk_penalized: 0
- tc_homophone_rare_form_penalized: 0
- tc_homophone_sc_guided_boost_total: 0
- tc_homophone_sc_guided_boosted: 0
- tc_homophone_sc_guided_buckets: 0
- tc_homophone_sc_guided_damped: 0
- tc_homophone_sc_guided_penalty_total: 0
- tc_homophone_sparse_penalized: 0
- tc_homophone_written_tail_penalized: 0
- tc_low_signal_literary_removed: 0
- tc_low_signal_named_removed: 0
- tc_low_signal_rare_buckets: 0
- tc_low_signal_rare_removed: 0
- tc_low_signal_written_removed: 0
- tc_multi_pronunciation_damped: 42
- tc_multi_pronunciation_penalty_total: 11635
- tc_multi_pronunciation_sc_guided_damped: 0
- tc_multi_pronunciation_sc_guided_penalty_total: 0
- tc_multi_pronunciation_sc_guided_terms: 0
- tc_multi_pronunciation_terms: 41
- total_lines: 124474

## Output
- sc_file: data/generated/dict_clean_sc.txt
- tc_file: data/generated/dict_clean_tc.txt
- sc_entries: 109140
- tc_entries: 109461
- suspicious_sc_entries: 9

## Suspicious SC Reason Summary

- weak-usage: 9
- high-modernity-risk: 9
- likely-person-name: 1

## Suspicious High-Weight SC Entries

| text | pinyin | weight | risk_score | modernity_risk | usage | jieba | pageviews | source_hits | char_score | pos | reasons |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 明志 | mingzhi | 423 | 522 | 418 | 0.000 | 0.000 | 0.000 | 0 | 0.784 | - | likely-person-name,weak-usage,high-modernity-risk |
| 百度 | baidu | 436 | 480 | 312 | 0.000 | 0.000 | 0.000 | 0 | 0.802 | - | weak-usage,high-modernity-risk |
| 以来 | yilai | 435 | 478 | 312 | 0.000 | 0.000 | 0.000 | 0 | 0.810 | - | weak-usage,high-modernity-risk |
| 失语 | shiyu | 436 | 476 | 312 | 0.000 | 0.000 | 0.000 | 0 | 0.825 | - | weak-usage,high-modernity-risk |
| 油光 | youguang | 433 | 473 | 312 | 0.000 | 0.000 | 0.000 | 0 | 0.828 | - | weak-usage,high-modernity-risk |
| 出乎 | chuhu | 423 | 472 | 312 | 0.000 | 0.000 | 0.000 | 0 | 0.764 | - | weak-usage,high-modernity-risk |
| 鸡汤 | jitang | 420 | 471 | 312 | 0.000 | 0.000 | 0.000 | 0 | 0.746 | - | weak-usage,high-modernity-risk |
| 实意 | shiyi | 428 | 469 | 312 | 0.000 | 0.000 | 0.000 | 0 | 0.820 | - | weak-usage,high-modernity-risk |
| 诚心 | chengxin | 421 | 467 | 312 | 0.000 | 0.000 | 0.000 | 0 | 0.786 | - | weak-usage,high-modernity-risk |
