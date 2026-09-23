"""Reviewed specialist admission must not masquerade as general usage evidence."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
import prepare_thuocl_specialists as specialist


class SpecialistTermsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sources, _ = builder._load_vertical_layer_sources(ROOT / "manifests/vertical_layers.public.json")
        cls.source = next(s for s in sources if s["id"] == "thuocl-reviewed-animal-terms")
        cls.entries, cls.stats = builder._load_vertical_source_entries(cls.source, {}, {}, 2, ROOT)
        cls.maps = ({}, {})
        cls.keys = builder._inject_specialist_exact_entries(*cls.maps, cls.entries)

    def test_source_is_isolated_and_has_no_synthetic_cross_domain_evidence(self):
        self.assertEqual("specialist_terms", self.source["vertical_layer_id"])
        self.assertEqual(57, len(self.entries))
        self.assertEqual(57, self.stats["vertical_term_kept"])
        self.assertTrue(self.source["attribution_required"])
        self.assertTrue((ROOT / "attribution/THUOCL-LICENSE.txt").is_file())
        self.assertEqual({}, builder._build_thuocl_frequency_map({"specialist": 9371}, {"specialist": 1}))

    def test_explicit_readings_match_each_character_in_both_scripts(self):
        for variant, mapping in zip(("sc", "tc"), self.maps):
            readings = {}
            for line in (ROOT / f"data/generated/dict_unihan_{variant}.txt").read_text(encoding="utf-8").splitlines():
                pinyin, text, *_ = line.split("\t")
                readings.setdefault(text, set()).add(pinyin)
            for pinyin, text in mapping:
                syllables = builder._runtime_parse_compact_pinyin(pinyin)
                self.assertEqual(len(text), len(syllables), text)
                for char, syllable in zip(text, syllables):
                    self.assertIn(syllable, readings[char], (text, char, syllable))

    def test_add_only_idempotent_and_preserves_all_existing_weights(self):
        key_sc = next(iter(self.maps[0]))
        key_tc = next(iter(self.maps[1]))
        for old_weight in (0, 35, 1000):
            maps = ({key_sc: old_weight}, {key_tc: old_weight})
            added = builder._inject_specialist_exact_entries(*maps, self.entries)
            self.assertEqual((56, 56), tuple(map(len, added)))
            self.assertEqual(old_weight, maps[0][key_sc])
            self.assertEqual(old_weight, maps[1][key_tc])
            self.assertEqual((set(), set()), builder._inject_specialist_exact_entries(*maps, self.entries))

    def test_invalid_admission_fails_before_mutating_either_map(self):
        record = list(self.entries[0])
        for field, bad in ((2, 0.8), (2, -0.1), (3, "lmzn"), (3, ""), (1, "")):
            broken = record.copy()
            broken[field] = bad
            maps = ({}, {})
            with self.assertRaises(ValueError):
                builder._inject_specialist_exact_entries(*maps, [self.entries[1], tuple(broken)])
            self.assertEqual(({}, {}), maps)

    def test_weights_and_prefix_priors_stay_low_in_generated_artifacts(self):
        for variant, mapping in zip(("sc", "tc"), self.maps):
            found = {}
            for line in (ROOT / f"data/generated/dict_clean_{variant}.txt").read_text(encoding="utf-8").splitlines():
                row = line.split("\t")
                if tuple(row[:2]) in mapping:
                    self.assertNotIn(tuple(row[:2]), found)
                    found[tuple(row[:2])] = (int(row[2]), row[3:])
            self.assertEqual({k: (v, ["no_contains"]) for k, v in mapping.items()}, found)
            prior = {}
            for line in (ROOT / f"data/generated/dict_completion_prior_{variant}.txt").read_text(encoding="utf-8").splitlines():
                row = line.split("\t")
                if tuple(row[:2]) in mapping:
                    prior[tuple(row[:2])] = tuple(map(int, row[2:]))
            self.assertEqual({k: builder._specialist_completion_prior() for k in mapping}, prior)
            self.assertTrue(all(1 <= weight <= 120 for weight in mapping.values()))

    def test_writer_keeps_order_and_popularity_exclusions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dict.txt"
            path.write_text("zzz\tplaceholder\t900\n", encoding="utf-8")
            mapping = {("zzz", "placeholder"): 900, **self.maps[0]}
            builder._write_dict(path, mapping, preserve_pinyin_keys=set(mapping),
                                contains_popularity_excluded_terms={t for _, t in self.maps[0]})
            first = path.read_bytes()
            self.assertTrue(first.startswith(b"zzz\tplaceholder\t900\n"))
            builder._write_dict(path, mapping, preserve_pinyin_keys=set(mapping),
                                contains_popularity_excluded_terms={t for _, t in self.maps[0]})
            self.assertEqual(first, path.read_bytes())

    def test_catalogue_layer_never_occupies_completion_slots_or_anchors(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'dict.txt'
            ordinary = 'limu\t立木\t800\nlimuzhuo\t立木桌\t100\n'
            path.write_text(ordinary, encoding='utf-8')
            prior = {('limuzhuo', '立木桌'): (100, 40, 0, 1, 0, 0, 0)}
            before, _ = builder._build_completion_exact_lookup(path, prior, stats_prefix='test')
            path.write_text(ordinary + 'limuzanniu\t利木赞牛\t1000\n', encoding='utf-8')
            key = ('limuzanniu', '利木赞牛')
            prior[key] = builder._specialist_completion_prior()
            after, _ = builder._build_completion_exact_lookup(path, prior, stats_prefix='test')
            self.assertEqual(before, after)
            values, stats = builder._build_completion_popularity_prior(
                path, usage_score_map={'利木赞牛': 1.0}, corpus_frequency_map={},
                document_frequency_map={'利木赞牛': 1.0}, persistence_map={},
                source_hits_map={}, vertical_layer_map={}, curated_hot_terms=set(),
                curated_low_terms=set(), path_score_map={}, stats_prefix='test',
                exact_only_keys={key})
            self.assertEqual(builder._specialist_completion_prior(), values[key])
            self.assertEqual(1, stats['test_completion_prior_cold_vertical_rows'])

    def test_broad_manifest_has_valid_readings_and_provenance(self):
        rows = list(specialist.load_rows(ROOT / specialist.OUTPUT))
        self.assertGreater(len(rows), 30000)
        self.assertEqual(len(rows), len({row[0] for row in rows}))
        allowed = set(specialist.CATEGORIES)
        readings = []
        for variant in ('sc', 'tc'):
            table = {}
            for py, text, *_ in specialist.load_rows(ROOT / f'data/generated/dict_unihan_{variant}.txt'):
                table.setdefault(text, set()).add(py)
            readings.append(table)
        for sc, tc, usage, py, provenance in rows:
            self.assertTrue(3 <= len(sc) <= 10)
            self.assertEqual(len(sc), len(tc))
            self.assertIn(float(usage), (0.02, 0.04))
            syllables = builder._runtime_parse_compact_pinyin(py)
            self.assertEqual(len(sc), len(syllables))
            for variant, text in enumerate((sc, tc)):
                for char, syllable in zip(text, syllables):
                    self.assertIn(syllable, readings[variant][char], (text, char, syllable))
            for item in provenance.split(';'):
                category, df = item.split(':')
                self.assertIn(category, allowed)
                self.assertGreaterEqual(int(df), 0)
                self.assertEqual('', specialist.rejection_reason(sc, category))

    def test_admission_filters_are_not_frequency_or_person_boosts(self):
        for word, category in (('利木赞牛', 'animal'), ('三叉神经', 'medical'),
                               ('加法器', 'IT'), ('有限责任公司', 'law')):
            self.assertEqual('', specialist.rejection_reason(word, category))
        for word, category in (('张三丰', 'caijing'), ('操作体统', 'IT'),
                               ('这些动物', 'animal'), ('魔法牛', 'animal'), ('牛', 'animal')):
            self.assertTrue(specialist.rejection_reason(word, category))

    def test_common_technical_terms_are_not_blanket_prediction_excluded(self):
        sources, _ = builder._load_vertical_layer_sources(ROOT / 'manifests/vertical_layers.public.json')
        entries = []
        for source in sources:
            if source['vertical_layer_id'] == 'specialist_terms':
                loaded, _ = builder._load_vertical_source_entries(source, {}, {}, 2, ROOT)
                entries.extend(loaded)
        common = builder._load_specialist_common_terms(ROOT / 'manifests/specialist_common_terms.tsv', entries)
        for text in ('有限责任公司', '有限責任公司', '文件系统', '文件系統', '绿豆汤', '綠豆湯'):
            prior = builder._specialist_completion_prior(text, common)
            self.assertGreaterEqual(prior[0], 158)
            self.assertLessEqual(prior[0], 183)
            self.assertEqual(0, prior[5])
            self.assertEqual((0, 0, 0), (prior[1], prior[2], prior[6]))
        self.assertEqual(4, builder._specialist_completion_prior('利木赞牛', common)[5])

    def test_editorial_eligibility_does_not_displace_attested_broad_prefixes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'dict.txt'
            path.write_text('wenben\t文本\t800\nwenbenbianji\t文本编辑\t700\n'
                            'wenbenwenjian\t文本文件\t40\n', encoding='utf-8')
            key = ('wenbenwenjian', '文本文件')
            prior = {('wenbenbianji', '文本编辑'): (300, 50, 0, 3, 0, 0, 0),
                     key: builder._specialist_completion_prior('文本文件', {'文本文件': 580})}
            lookup, _ = builder._build_completion_exact_lookup(
                path, prior, stats_prefix='test', reviewed_specialist_keys={key})
            self.assertIn(('wenben', 'wenbenbianji', '文本编辑'), lookup)
            self.assertNotIn(('wenben', *key), lookup)
            self.assertIn(('wenbenwen', *key), lookup)


if __name__ == "__main__":
    unittest.main()
