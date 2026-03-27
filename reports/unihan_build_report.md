# External Build Report

- profile: unihan_single
- generated_at_utc: 2026-03-27T08:28:21+00:00
- min_hanzi: 1
- max_entries: unlimited

## Sources
- opencc-stphrases: OpenCC STPhrases
  - license: Apache-2.0
  - risk_level: low
  - redistribution_class: permissive
  - url: https://raw.githubusercontent.com/BYVoid/OpenCC/master/data/dictionary/STPhrases.txt
- unicode-unihan-readings: Unicode Unihan_Readings
  - license: Unicode-3.0
  - risk_level: low
  - redistribution_class: permissive
  - url: https://www.unicode.org/Public/UCD/latest/ucd/Unihan.zip
- project-curated-fiction-entities: Cassotis curated fiction entities
  - license: Repository license (project-authored)
  - risk_level: low
  - redistribution_class: project_authored
  - url: repo://manifests/vertical/fiction_entities.tsv
- project-curated-proper-nouns: Cassotis curated proper nouns
  - license: Repository license (project-authored)
  - risk_level: low
  - redistribution_class: project_authored
  - url: repo://manifests/vertical/proper_nouns.tsv
- thuocl-it-vertical: THUOCL IT subset
  - license: THUOCL custom open terms
  - risk_level: medium
  - redistribution_class: attribution_required
  - url: https://github.com/thunlp/THUOCL/archive/refs/heads/master.zip#THUOCL_IT.txt
- project-curated-vertical-computing: Cassotis curated computing terms
  - license: Repository license (project-authored)
  - risk_level: low
  - redistribution_class: project_authored
  - url: repo://manifests/vertical/computing.tsv
- project-curated-vertical-medicine: Cassotis curated medical terms
  - license: Repository license (project-authored)
  - risk_level: low
  - redistribution_class: project_authored
  - url: repo://manifests/vertical/medicine.tsv
- mesh-descriptor-catalog: MeSH descriptor catalog
  - license: NLM MeSH terms and conditions
  - risk_level: low
  - redistribution_class: attribution_required
  - url: https://nlmpubs.nlm.nih.gov/projects/mesh/MESH_FILES/xmlmesh/desc2026.xml
- wikidata-medical-mesh-zh: Wikidata zh medical entities (MeSH-linked)
  - license: CC0-1.0
  - risk_level: low
  - redistribution_class: public_domain
  - url: https://query.wikidata.org/sparql
- thuocl-medical-vertical: THUOCL medical subset
  - license: THUOCL custom open terms
  - risk_level: medium
  - redistribution_class: attribution_required
  - url: https://github.com/thunlp/THUOCL/archive/refs/heads/master.zip#THUOCL_medical.txt

## Parse stats
- filtered_short: 0
- invalid_format: 0
- lexical_seed_augmented_sc_terms: 0
- lexical_seed_augmented_tc_terms: 0
- override_entries: 13
- override_hits: 0
- override_injected: 0
- parsed_lines: 49184
- sc_char_normalized_blocked_reverse_entries: 0
- sc_char_normalized_converted_entries: 23
- sc_char_normalized_total_entries: 23910
- sc_filtered_non_windows_cjk: 0
- sc_global_tail_constituent_mismatch_removed: 0
- sc_global_tail_literary_removed: 0
- sc_global_tail_modernity_risk_removed: 0
- sc_global_tail_named_removed: 0
- sc_global_tail_rare_char_removed: 0
- sc_global_tail_removed: 0
- sc_global_tail_written_removed: 0
- sc_homophone_buckets: 400
- sc_homophone_daily_number_boosted: 0
- sc_homophone_daily_phrase_boosted: 0
- sc_homophone_daily_phrase_damped: 0
- sc_homophone_daily_phrase_short_non_daily_damped: 0
- sc_homophone_dominant_common_boosted: 0
- sc_homophone_dominant_common_damped: 0
- sc_homophone_entries_adjusted: 23817
- sc_homophone_entries_boosted: 3659
- sc_homophone_entries_damped: 20158
- sc_homophone_inflated_short_penalized: 0
- sc_homophone_literary_penalized: 0
- sc_homophone_modernity_risk_penalized: 0
- sc_homophone_preferred_term_boosted: 0
- sc_homophone_preferred_term_damped: 0
- sc_homophone_rare_form_penalized: 0
- sc_homophone_short_everyday_boosted: 0
- sc_homophone_short_everyday_non_daily_damped: 0
- sc_homophone_short_popular_wiki_boosted: 0
- sc_homophone_sparse_penalized: 0
- sc_homophone_written_tail_penalized: 0
- sc_low_signal_literary_removed: 0
- sc_low_signal_named_removed: 0
- sc_low_signal_rare_buckets: 0
- sc_low_signal_rare_removed: 0
- sc_low_signal_written_removed: 0
- sc_multi_pronunciation_damped: 0
- sc_multi_pronunciation_penalty_total: 0
- sc_multi_pronunciation_terms: 0
- sc_script_filtered_entries: 0
- sc_script_filtered_total_entries: 23910
- sc_single_char_leading_adjusted: 395
- sc_single_char_leading_delta_total: 21360
- sc_single_char_reading_preference_adjusted: 1500
- sc_single_char_reading_preference_delta_total: 21326
- sc_single_char_reading_removed: 1
- tc_char_normalized_converted_entries: 18
- tc_char_normalized_total_entries: 24065
- tc_filtered_non_windows_cjk: 0
- tc_global_tail_constituent_mismatch_removed: 0
- tc_global_tail_literary_removed: 0
- tc_global_tail_modernity_risk_removed: 0
- tc_global_tail_named_removed: 0
- tc_global_tail_rare_char_removed: 0
- tc_global_tail_removed: 0
- tc_global_tail_written_removed: 0
- tc_homophone_buckets: 399
- tc_homophone_daily_number_boosted: 0
- tc_homophone_daily_phrase_boosted: 0
- tc_homophone_daily_phrase_damped: 0
- tc_homophone_daily_phrase_short_non_daily_damped: 0
- tc_homophone_dominant_common_boosted: 0
- tc_homophone_dominant_common_damped: 0
- tc_homophone_entries_adjusted: 23906
- tc_homophone_entries_boosted: 4039
- tc_homophone_entries_damped: 19867
- tc_homophone_inflated_short_penalized: 0
- tc_homophone_literary_penalized: 0
- tc_homophone_modernity_risk_penalized: 0
- tc_homophone_preferred_term_boosted: 0
- tc_homophone_preferred_term_damped: 0
- tc_homophone_rare_form_penalized: 0
- tc_homophone_sc_guided_boost_total: 0
- tc_homophone_sc_guided_boosted: 0
- tc_homophone_sc_guided_buckets: 0
- tc_homophone_sc_guided_damped: 0
- tc_homophone_sc_guided_penalty_total: 0
- tc_homophone_short_everyday_boosted: 0
- tc_homophone_short_everyday_non_daily_damped: 0
- tc_homophone_short_popular_wiki_boosted: 0
- tc_homophone_sparse_penalized: 0
- tc_homophone_written_tail_penalized: 0
- tc_low_signal_literary_removed: 0
- tc_low_signal_named_removed: 0
- tc_low_signal_rare_buckets: 0
- tc_low_signal_rare_removed: 0
- tc_low_signal_written_removed: 0
- tc_multi_pronunciation_damped: 0
- tc_multi_pronunciation_penalty_total: 0
- tc_multi_pronunciation_sc_guided_damped: 0
- tc_multi_pronunciation_sc_guided_penalty_total: 0
- tc_multi_pronunciation_sc_guided_terms: 0
- tc_multi_pronunciation_terms: 0
- tc_script_filtered_entries: 0
- tc_script_filtered_total_entries: 24065
- tc_single_char_leading_adjusted: 349
- tc_single_char_leading_delta_total: 19224
- tc_single_char_reading_preference_adjusted: 1855
- tc_single_char_reading_preference_delta_total: 34276
- tc_single_char_reading_removed: 1
- total_lines: 49191
- unihan_core_size: 18816
- unihan_family_support_boosted_sc: 5024
- unihan_family_support_boosted_tc: 5244
- unihan_family_support_terms_sc: 5842
- unihan_family_support_terms_tc: 6075
- unihan_frequency_size: 0
- unihan_grade_size: 2632
- unihan_leading_support_terms_sc: 4780
- unihan_leading_support_terms_tc: 4935
- unihan_map_size: 26711
- unihan_pinlu_size: 3799
- unihan_reading_support_terms_sc: 1543
- unihan_reading_support_terms_tc: 1986
- unihan_readings_chars: 26711
- unihan_readings_pairs: 33908
- unihan_sc_only_chars: 2766
- unihan_single_char_injected_sc: 23932
- unihan_single_char_injected_tc: 24082
- unihan_tc_only_chars: 2916
- vertical_layer_sources_loaded: 8
- vertical_layer_sources_skipped_inactive: 0
- vertical_layer_sources_skipped_unsupported: 0
- vertical_layer_sources_total: 8
- vertical_layers_active: 4
- vertical_layers_declared: 4
- vertical_layers_manifest_present: 1
- vertical_mesh_descriptors_medical: 50066
- vertical_mesh_descriptors_nonmedical: 12154
- vertical_mesh_descriptors_total: 62220
- vertical_mesh_missing_payload: 0
- vertical_support_excluded_sc: 34902
- vertical_support_excluded_tc: 36454
- vertical_term_kept: 234
- vertical_term_rows: 234
- vertical_term_skipped_malformed: 0
- vertical_term_skipped_non_cjk: 0
- vertical_term_skipped_short: 0
- vertical_terms_fallback_downloads: 0
- vertical_terms_missing_payload_source: 0
- vertical_terms_unsupported_source_type: 0
- vertical_thuocl_files_matched: 2
- vertical_thuocl_invalid_format: 0
- vertical_thuocl_kept: 20877
- vertical_thuocl_missing_member: 0
- vertical_thuocl_rows: 34749
- vertical_thuocl_skipped_filter: 10727
- vertical_thuocl_skipped_non_cjk: 3145
- vertical_thuocl_skipped_short: 0
- vertical_wikidata_kept: 16412
- vertical_wikidata_missing_mesh_payload: 0
- vertical_wikidata_missing_payload: 0
- vertical_wikidata_rows: 37607
- vertical_wikidata_skipped_duplicate: 1663
- vertical_wikidata_skipped_non_cjk: 1573
- vertical_wikidata_skipped_nonmedical_mesh: 17959
- vertical_wikidata_skipped_short: 0
- wiki_proper_augmented_sc_terms: 0
- wiki_proper_augmented_tc_terms: 0

## Output
- sc_file: data/generated/dict_unihan_sc.txt
- tc_file: data/generated/dict_unihan_tc.txt
- sc_entries: 23909
- tc_entries: 24064
- suspicious_sc_entries: 25

## Suspicious SC Reason Summary

- weak-usage: 25
- high-modernity-risk: 25

## Suspicious High-Weight SC Entries

| text | pinyin | weight | risk_score | modernity_risk | usage | jieba | pageviews | source_hits | char_score | pos | reasons |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 不 | bu | 793 | 821 | 312 | 0.000 | 0.000 | 0.000 | 0 | 0.913 | - | weak-usage,high-modernity-risk |
| 有 | you | 784 | 813 | 312 | 0.000 | 0.000 | 0.000 | 0 | 0.910 | - | weak-usage,high-modernity-risk |
| 他 | ta | 781 | 810 | 312 | 0.000 | 0.000 | 0.000 | 0 | 0.908 | - | weak-usage,high-modernity-risk |
| 大 | da | 774 | 799 | 312 | 0.000 | 0.000 | 0.000 | 0 | 0.937 | - | weak-usage,high-modernity-risk |
| 这 | zhe | 760 | 790 | 312 | 0.000 | 0.000 | 0.000 | 0 | 0.899 | - | weak-usage,high-modernity-risk |
| 一 | yi | 760 | 790 | 312 | 0.000 | 0.000 | 0.000 | 0 | 0.899 | - | weak-usage,high-modernity-risk |
| 那 | na | 755 | 785 | 312 | 0.000 | 0.000 | 0.000 | 0 | 0.897 | - | weak-usage,high-modernity-risk |
| 我 | wo | 751 | 782 | 312 | 0.000 | 0.000 | 0.000 | 0 | 0.895 | - | weak-usage,high-modernity-risk |
| 可 | ke | 748 | 779 | 312 | 0.000 | 0.000 | 0.000 | 0 | 0.894 | - | weak-usage,high-modernity-risk |
| 在 | zai | 745 | 776 | 312 | 0.000 | 0.000 | 0.000 | 0 | 0.893 | - | weak-usage,high-modernity-risk |
| 上 | shang | 731 | 763 | 312 | 0.000 | 0.000 | 0.000 | 0 | 0.887 | - | weak-usage,high-modernity-risk |
| 也 | ye | 730 | 762 | 312 | 0.000 | 0.000 | 0.000 | 0 | 0.886 | - | weak-usage,high-modernity-risk |
| 没 | mei | 731 | 760 | 312 | 0.000 | 0.000 | 0.000 | 0 | 0.908 | - | weak-usage,high-modernity-risk |
| 就 | jiu | 727 | 759 | 312 | 0.000 | 0.000 | 0.000 | 0 | 0.885 | - | weak-usage,high-modernity-risk |
| 和 | he | 721 | 750 | 312 | 0.000 | 0.000 | 0.000 | 0 | 0.910 | - | weak-usage,high-modernity-risk |
| 会 | hui | 717 | 747 | 312 | 0.000 | 0.000 | 0.000 | 0 | 0.902 | - | weak-usage,high-modernity-risk |
| 了 | le | 719 | 746 | 312 | 0.000 | 0.000 | 0.000 | 0 | 0.922 | - | weak-usage,high-modernity-risk |
| 去 | qu | 713 | 746 | 312 | 0.000 | 0.000 | 0.000 | 0 | 0.879 | - | weak-usage,high-modernity-risk |
| 出 | chu | 711 | 744 | 312 | 0.000 | 0.000 | 0.000 | 0 | 0.878 | - | weak-usage,high-modernity-risk |
| 你 | ni | 710 | 743 | 312 | 0.000 | 0.000 | 0.000 | 0 | 0.878 | - | weak-usage,high-modernity-risk |
| 以 | yi | 709 | 742 | 312 | 0.000 | 0.000 | 0.000 | 0 | 0.877 | - | weak-usage,high-modernity-risk |
| 要 | yao | 708 | 741 | 312 | 0.000 | 0.000 | 0.000 | 0 | 0.877 | - | weak-usage,high-modernity-risk |
| 都 | dou | 710 | 740 | 312 | 0.000 | 0.000 | 0.000 | 0 | 0.903 | - | weak-usage,high-modernity-risk |
| 好 | hao | 707 | 740 | 312 | 0.000 | 0.000 | 0.000 | 0 | 0.876 | - | weak-usage,high-modernity-risk |
| 能 | neng | 698 | 732 | 312 | 0.000 | 0.000 | 0.000 | 0 | 0.873 | - | weak-usage,high-modernity-risk |
