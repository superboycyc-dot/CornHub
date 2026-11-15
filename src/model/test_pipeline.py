"""Internal fixtures exist only in TemporaryDirectory; never publish fixture outputs."""
import csv
import json
import tempfile
import unittest
from pathlib import Path
from src.model.pipeline import FEATURES, SCHEMAS, metrics, run, write_csv, write_json


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='cornhub-internal-only-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.data = self.root / 'input'
        self.out = self.root / 'private-output'
        self.report = self.root / 'private-report'

    def fixture(self):
        labels, folds, features = [], [], []
        for i in range(12):
            fid = f'barc_internal_{i:03d}'
            for year in (2021, 2022):
                labels.append(dict(field_id=fid, year=year, label='silage' if i % 2 else 'grain', label_raw='INTERNAL', source_dataset_id='INTERNAL_NOT_REAL'))
                folds.append(dict(field_id=fid, year=year, fold_id=str(i % 3)))
                values = [.8, 200, .03, 240 if i % 2 else 280, .3, 10, 25]
                features.append(dict(field_id=fid, year=year, **dict(zip(FEATURES, values)), quality_flag='usable', missing_reason=''))
        for kind, rows, path in [('labels', labels, 'core/labels.csv'), ('folds', folds, 'core/validation_folds.csv'), ('features', features, 'satellite/features.csv')]:
            write_csv(self.data / path, SCHEMAS[kind], rows)
        return labels, folds, features

    def test_pending_no_fake_rows(self):
        self.assertEqual(run(self.data, self.out, self.report), 0)
        with (self.out / 'predictions.csv').open() as f:
            self.assertEqual(list(csv.DictReader(f)), [])
        m = json.loads((self.out / 'metrics.json').read_text())
        self.assertEqual(m['status'], 'pending')
        self.assertIsNone(m['macro_f1'])
        self.assertEqual(len(json.loads((self.report / 'merge_report.json').read_text())['missing_files']), 3)

    def test_duplicate_and_field_leakage_rejected(self):
        _, folds, features = self.fixture()
        folds[1]['fold_id'] = 'different'
        write_csv(self.data / 'core/validation_folds.csv', SCHEMAS['folds'], folds)
        write_csv(self.data / 'satellite/features.csv', SCHEMAS['features'], features + [features[0]])
        self.assertEqual(run(self.data, self.out, self.report, train=True), 2)
        audit = json.loads((self.report / 'merge_report.json').read_text())
        self.assertTrue(audit['duplicate_keys'])
        self.assertTrue(any('crosses folds' in e for e in audit['errors']))
        self.assertEqual(json.loads((self.out / 'metrics.json').read_text())['status'], 'pending')

    def test_unmatched_and_quality_exclusions(self):
        _, _, features = self.fixture()
        features.pop()
        features[0].update(quality_flag='no_data', valid_obs_count=0, max_gap_days=244, missing_reason='internal cloud fixture')
        for col in FEATURES[:5]:
            features[0][col] = ''
        write_csv(self.data / 'satellite/features.csv', SCHEMAS['features'], features)
        self.assertEqual(run(self.data, self.out, self.report), 0)
        audit = json.loads((self.report / 'merge_report.json').read_text())
        self.assertEqual(audit['matched_count'], 23)
        self.assertEqual(audit['eligible_count'], 22)
        self.assertEqual(len(audit['exclusions']), 2)
        self.assertEqual(len(audit['unmatched']), 1)

    def test_farm_leakage_rejected_before_training(self):
        self.fixture()
        fields = [dict(type='Feature', properties=dict(field_id=f'barc_internal_{i:03d}', farm_group='same_farm'), geometry=None) for i in range(12)]
        write_json(self.data / 'core/fields.geojson', dict(type='FeatureCollection', features=fields))
        self.assertEqual(run(self.data, self.out, self.report, train=True), 2)
        audit = json.loads((self.report / 'merge_report.json').read_text())
        self.assertEqual(audit['farm_group_check']['status'], 'failed')
        self.assertEqual(audit['label_fold_matched_count'], 24)
        self.assertEqual(audit['label_summary']['n_fields'], 12)
        self.assertEqual(len(audit['planned_folds']), 3)
        self.assertEqual(json.loads((self.out / 'metrics.json').read_text())['status'], 'pending')

    def test_farm_plan_and_unknown_feature_id(self):
        _, _, features = self.fixture()
        fields = [dict(type='Feature', properties=dict(field_id=f'barc_internal_{i:03d}', farm_group=f'farm_{i % 3}'), geometry=None) for i in range(12)]
        write_json(self.data / 'core/fields.geojson', dict(type='FeatureCollection', features=fields))
        self.assertEqual(run(self.data, self.out, self.report), 0)
        audit = json.loads((self.report / 'merge_report.json').read_text())
        self.assertEqual(audit['farm_group_check']['n_labeled_farms'], 3)
        self.assertTrue(all(len(f['test_farm_groups']) == 1 for f in audit['planned_folds']))
        features[0]['field_id'] = 'barc_unknown'
        write_csv(self.data / 'satellite/features.csv', SCHEMAS['features'], features)
        self.assertEqual(run(self.data, self.out, self.report, train=True), 2)
        audit = json.loads((self.report / 'merge_report.json').read_text())
        self.assertTrue(any('barc_unknown' in e for e in audit['errors']))

    def test_undefined_metrics(self):
        m = metrics([0, 0], [.1, .2])
        for key in ('macro_f1', 'silage_precision', 'silage_recall'):
            self.assertIsNone(m[key])
        self.assertAlmostEqual(m['brier_score'], .025)

    def test_training_roles_and_fold_imputation(self):
        from unittest.mock import patch
        from sklearn.impute import SimpleImputer
        _, _, features = self.fixture()
        features[0]['ndvi_peak'] = ''
        write_csv(self.data / 'satellite/features.csv', SCHEMAS['features'], features)
        original = SimpleImputer.fit
        sizes = []
        def spy(obj, X, *args, **kwargs):
            sizes.append(len(X))
            return original(obj, X, *args, **kwargs)
        with patch.object(SimpleImputer, 'fit', spy):
            self.assertEqual(run(self.data, self.out, self.report, train=True, inference=True), 0)
        self.assertEqual(sizes, [16, 16, 16, 24])
        with (self.out / 'predictions.csv').open() as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 48)
        self.assertEqual(len({(r['field_id'], r['year'], r['prediction_role']) for r in rows}), 48)
        self.assertTrue(all(0 <= float(r['p_silage']) <= 1 for r in rows))
        self.assertEqual(json.loads((self.out / 'metrics.json').read_text())['n_evaluated'], 24)
        self.assertTrue(all(r['fold_id'] == '' for r in rows if r['prediction_role'] == 'inference'))

    def test_one_realistic_feature_row_cannot_train_or_infer(self):
        _, _, features = self.fixture()
        # Partial-season shape only; synthetic values stay in TemporaryDirectory.
        features[0].update(ndvi_late_mean='', max_gap_days=177, quality_flag='limited', missing_reason='internal partial season')
        write_csv(self.data / 'satellite/features.csv', SCHEMAS['features'], features[:1])
        self.assertEqual(run(self.data, self.out, self.report, train=True, inference=True), 0)
        audit = json.loads((self.report / 'merge_report.json').read_text())
        self.assertEqual(audit['matched_count'], 1)
        self.assertEqual(audit['eligible_count'], 1)
        self.assertEqual(audit['eligible_summary']['class_counts'], {'grain': 1, 'silage': 0})
        self.assertEqual(audit['model_fit_count'], 0)
        self.assertEqual(audit['output_rows'], {'oof': 0, 'inference': 0})
        self.assertEqual(audit['folds'][0]['n_train'], 0)
        self.assertEqual(len(audit['exclusions']), 24)
        result = json.loads((self.out / 'metrics.json').read_text())
        self.assertEqual(result['status'], 'pending')
        self.assertIsNone(result['brier_score'])
        self.assertTrue(any('Inference not fitted' in note for note in result['notes']))

    def test_extra_feature_columns_cannot_replace_truth(self):
        _, _, features = self.fixture()
        for row in features:
            row['label'] = 'grain'
            row['fold_id'] = 'untrusted_extra'
        write_csv(self.data / 'satellite/features.csv', [*SCHEMAS['features'], 'label', 'fold_id'], features)
        self.assertEqual(run(self.data, self.out, self.report, train=True), 0)
        result = json.loads((self.out / 'metrics.json').read_text())
        self.assertEqual(result['class_counts'], {'grain': 12, 'silage': 12})
        self.assertEqual(result['n_evaluated'], 24)

    def test_missing_training_class_abstains(self):
        labels, _, _ = self.fixture()
        for r in labels:
            r['label'] = 'grain'
        write_csv(self.data / 'core/labels.csv', SCHEMAS['labels'], labels)
        run(self.data, self.out, self.report, train=True)
        self.assertEqual(json.loads((self.out / 'metrics.json').read_text())['status'], 'pending')
        self.assertEqual(len(json.loads((self.report / 'merge_report.json').read_text())['exclusions']), 24)


if __name__ == '__main__':
    unittest.main()
