"""Synthetic fixtures exist only in temporary test directories, never in published data."""
import copy
import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from analysis import (analyze, read_csv, read_fields, simulate_review, ContractError,
                      FEATURE_COLUMNS, PREDICTION_COLUMNS, cohort_ids)
from validate_handoff import validate_core
from report_results import feature_coverage


def fields():
    return [{'field_id': 'barc_001', 'area_ha': 10.0},
            {'field_id': 'barc_002', 'area_ha': 20.0},
            {'field_id': 'barc_003', 'area_ha': 30.0}]


def features():
    return [{'field_id': r['field_id'], 'year': 2022, 'quality_flag': 'usable', 'missing_reason': ''} for r in fields()]


def predictions(role='oof'):
    return [{'field_id': 'barc_001', 'year': 2022, 'prediction_role': role, 'p_silage': 0.8, 'fold_id': '0', 'model_version': 'test-only'},
            {'field_id': 'barc_002', 'year': 2022, 'prediction_role': role, 'p_silage': 0.25, 'fold_id': '1', 'model_version': 'test-only'}]


class AnalysisTests(unittest.TestCase):
    def test_2024_2025_missing_annual_cohort_is_unknown_not_zero(self):
        for year in [2024, 2025]:
            selected = cohort_ids(fields(), [{'field_id': 'barc_001', 'year': 2022}], year=year, cohort='labeled')
            summary, queue, needed, audit, covered = analyze(fields(), features(), predictions(),
                year=year, prediction_role='oof', selected_ids=selected, cohort='labeled')
            self.assertEqual(summary['status'], 'pending')
            self.assertEqual(summary['scope']['cohort_status'], 'pending_no_annual_cohort')
            for key in ['total_area_ha', 'covered_area_ha', 'coverage_fraction',
                        'expected_silage_area_ha', 'expected_grain_area_ha']:
                self.assertIsNone(summary[key])
            self.assertEqual((queue, needed, covered), ([], [], []))
            self.assertIn('missing_annual_target_cohort', audit['blocking_reasons'])
            coverage = feature_coverage(fields(), features(), summary)
            self.assertIsNone(coverage['feature_matched_area_ha'])

    def test_new_year_real_probabilities_remain_separate(self):
        pred = [{**predictions()[0], 'year': 2024, 'p_silage': 0.6}]
        feat = [{**features()[0], 'year': 2024}]
        summary = analyze(fields(), feat, predictions()+pred, year=2024, prediction_role='oof',
                          selected_ids=['barc_001'], cohort='labeled')[0]
        self.assertEqual(summary['expected_silage_area_ha'], 6)
        self.assertEqual(summary['expected_grain_area_ha'], 4)
        next_year = analyze(fields(), feat, predictions()+pred, year=2025, prediction_role='oof',
                            selected_ids=['barc_001'], cohort='labeled')[0]
        self.assertEqual(next_year['covered_area_ha'], 0)
        self.assertIsNone(next_year['expected_silage_area_ha'])


    def test_features_do_not_imply_prediction_coverage(self):
        feat = [{**r, 'valid_obs_count': 8, 'max_gap_days': 20} for r in features()]
        feat[0].update(quality_flag='limited', max_gap_days=40)
        summary = analyze(fields(), feat[:2], [], year=2022, prediction_role='oof')[0]
        coverage = feature_coverage(fields(), feat[:2], summary)
        self.assertEqual(summary['coverage_fraction'], 0)
        self.assertEqual(coverage['feature_matched_area_ha'], 30)
        self.assertEqual(coverage['usable_feature_area_ha'], 20)
        self.assertEqual(coverage['quality_area_ha']['limited'], 10)
        self.assertEqual(coverage['quality_area_ha']['missing_features'], 30)

    def test_feature_coverage_unknown_and_empty_denominators(self):
        for inventory in [None, []]:
            summary = analyze(inventory, None, None, year=2022, prediction_role='oof')[0]
            coverage = feature_coverage(inventory, None, summary)
            self.assertIsNone(coverage['feature_match_fraction'])
            self.assertEqual(coverage['n_matched_features'], 0)
    def test_explicit_annual_and_smoke_cohorts(self):
        labels = [{'field_id': 'barc_001', 'year': 2022},
                  {'field_id': 'barc_002', 'year': 2023}]
        chosen = cohort_ids(fields(), labels, year=2022, cohort='labeled')
        summary, queue, _, audit, _ = analyze(fields(), features(), predictions(), year=2022,
            prediction_role='oof', selected_ids=chosen, cohort='labeled')
        self.assertEqual(summary['total_area_ha'], 10)
        self.assertEqual(summary['expected_silage_area_ha'], 8)
        self.assertEqual(summary['scope']['field_ids'], ['barc_001'])
        self.assertEqual(audit['excluded_outside_cohort_prediction_ids'], ['barc_002'])
        self.assertEqual(audit['excluded_other_year_or_role_prediction_rows'], 0)
        smoke = {'field_id': 'barc_001', 'year': 2022}
        self.assertEqual(cohort_ids(fields(), labels, year=2022, cohort='smoke', smoke=smoke), chosen)
        with self.assertRaises(ContractError):
            cohort_ids(fields(), labels, year=2023, cohort='smoke', smoke=smoke)
        with self.assertRaises(ContractError):
            analyze(fields(), features(), predictions(), year=2022, prediction_role='oof', selected_ids=['barc_unknown'])

    def test_A_handoff_farm_folds_and_smoke(self):
        inventory = [{**r, 'farm_group': 'farm_a'} for r in fields()]
        labels = [{'field_id': 'barc_001', 'year': 2022, 'label': 'grain', 'source_dataset_id': 'test-only'},
                  {'field_id': 'barc_002', 'year': 2022, 'label': 'silage', 'source_dataset_id': 'test-only'}]
        folds = [{'field_id': r['field_id'], 'year': 2022, 'fold_id': '0'} for r in labels]
        smoke = {'field_id': 'barc_001', 'year': 2022, 'window_start': '2022-04-01',
                 'window_end_exclusive': '2022-12-01', 'source_dataset_id': 'test-only'}
        result = validate_core(inventory, labels, folds, smoke)
        self.assertEqual(result['annual_labeled_cohorts']['2022']['selected_labeled_area_ha'], 30)
        with self.assertRaises(ContractError):
            validate_core(inventory, labels, [{**r, 'fold_id': str(i)} for i, r in enumerate(folds)], smoke)
        with self.assertRaises(ContractError):
            validate_core(inventory, labels, folds[:-1], smoke)
        with self.assertRaises(ContractError):
            validate_core(inventory, labels, folds, {**smoke, 'field_id': 'barc_002'})

    def test_cohort_cannot_hide_duplicates_or_orphans(self):
        for pred in [predictions()+[predictions()[1]], predictions()+[
                {**predictions()[1], 'field_id': 'barc_unknown', 'year': 2023}]]:
            with self.assertRaises(ContractError):
                analyze(fields(), features(), pred, year=2022, prediction_role='oof',
                        selected_ids=['barc_001'], cohort='smoke')

    def run_analysis(self, f=None, p=None, year=2022, role='oof'):
        return analyze(fields(), features() if f is None else f, predictions() if p is None else p, year=year, prediction_role=role)

    def test_weighted_area_and_unknown_not_grain(self):
        summary, queue, missing, audit, _ = self.run_analysis()
        self.assertEqual(summary['total_area_ha'], 60)
        self.assertEqual(summary['covered_area_ha'], 30)
        self.assertEqual(summary['coverage_fraction'], 0.5)
        self.assertEqual(summary['expected_silage_area_ha'], 13)
        self.assertEqual(summary['expected_grain_area_ha'], 17)
        self.assertIsNone(summary['economic_scenario'])
        self.assertEqual(queue[0]['field_id'], 'barc_002')
        self.assertEqual(queue[0]['review_score'], 15)
        self.assertIn('missing_prediction', missing[0]['missing_reason'])
        self.assertEqual(audit['covered_prediction_rows'], 2)

    def test_pending_absent_and_empty_predictions(self):
        for pred in [None, []]:
            summary, queue, _, _, _ = analyze(fields(), features(), pred, year=2022, prediction_role='oof')
            self.assertEqual(summary['status'], 'pending')
            self.assertEqual(summary['covered_area_ha'], 0)
            self.assertEqual(summary['coverage_fraction'], 0)
            self.assertIsNone(summary['expected_grain_area_ha'])
            self.assertEqual(queue, [])
        summary = analyze(None, None, None, year=2022, prediction_role='inference')[0]
        self.assertIsNone(summary['total_area_ha'])
        self.assertIsNone(summary['coverage_fraction'])

    def test_year_and_role_separation(self):
        pred = predictions() + predictions('inference')
        pred += [{**r, 'year': 2023, 'p_silage': 1.0} for r in predictions()]
        self.assertEqual(self.run_analysis(p=pred)[0]['expected_silage_area_ha'], 13)
        self.assertEqual(self.run_analysis(p=pred, year=2023)[0]['expected_silage_area_ha'], 30)
        for year, role in [(None, 'oof'), (2022, None), (True, 'oof'), (2026, 'oof')]:
            with self.assertRaises(ContractError):
                self.run_analysis(year=year, role=role)

    def test_duplicates_and_orphans_fail(self):
        for pred in [predictions() + [predictions()[0]], [{**predictions()[0], 'field_id': 'barc_unknown'}]]:
            with self.assertRaises(ContractError):
                self.run_analysis(p=pred)

    def test_quality_not_confidence(self):
        feat = features()
        feat[0]['quality_flag'] = 'limited'
        summary, queue, missing, _, _ = self.run_analysis(f=feat)
        self.assertEqual(summary['covered_area_ha'], 30)
        self.assertEqual([r['field_id'] for r in queue], ['barc_002'])
        self.assertIn('quality_limited', missing[0]['missing_reason'])

    def test_computation_api_rejects_bad_numbers(self):
        for value in [float('nan'), float('inf'), -0.01, 1.01, True]:
            pred = predictions()
            pred[0]['p_silage'] = value
            with self.assertRaises(ContractError):
                self.run_analysis(p=pred)
        for value in [float('nan'), -1, 0, True]:
            inventory = fields()
            inventory[0]['area_ha'] = value
            with self.assertRaises(ContractError):
                analyze(inventory, features(), predictions(), year=2022, prediction_role='oof')

    def test_empty_inventory_and_missing_features(self):
        summary, queue, _, _, _ = analyze([], [], [], year=2022, prediction_role='oof')
        self.assertEqual(summary['total_area_ha'], 0)
        self.assertEqual(summary['covered_area_ha'], 0)
        self.assertIsNone(summary['coverage_fraction'])
        summary, queue, missing, _, _ = analyze(fields(), None, predictions(), year=2022, prediction_role='oof')
        self.assertEqual(summary['expected_silage_area_ha'], 13)
        self.assertEqual(queue, [])
        self.assertTrue(all('missing_features' in r['missing_reason'] for r in missing))

    def test_tie_break_and_probability_endpoints(self):
        pred = predictions()
        pred[0]['p_silage'] = 0
        pred[1]['p_silage'] = 1
        summary, queue, _, _, _ = self.run_analysis(p=pred)
        self.assertEqual(summary['expected_silage_area_ha'], 20)
        self.assertEqual([r['field_id'] for r in queue], ['barc_001', 'barc_002'])
        self.assertTrue(all(r['review_score'] == 0 for r in queue))

    def test_csv_rejects_nonfinite_and_out_of_range_probability(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'predictions.csv'
            for value in ['NaN', 'Infinity', '-0.01', '1.01']:
                with path.open('w', newline='') as stream:
                    writer = csv.DictWriter(stream, fieldnames=PREDICTION_COLUMNS)
                    writer.writeheader()
                    writer.writerow(dict(field_id='barc_001', year=2022, p_silage=value, predicted_label='silage', prediction_role='oof', fold_id='0', model_version='test-only'))
                with self.assertRaises(ContractError):
                    read_csv(path, PREDICTION_COLUMNS, 'predictions')

    def test_string_id_and_geojson_area_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'fields.geojson'
            feature = {'type':'Feature', 'properties':{'field_id':'barc_001','source_field_id':'001','source_dataset_id':'synthetic-test-only','area_ha':1},
                       'geometry':{'type':'Polygon','coordinates':[[[0,0],[1,0],[1,1],[0,0]]]}}
            path.write_text(json.dumps({'type':'FeatureCollection','features':[feature]}))
            self.assertEqual(read_fields(path)[0]['source_field_id'], '001')
            feature['properties']['area_ha'] = -1
            path.write_text(json.dumps({'type':'FeatureCollection','features':[feature]}))
            with self.assertRaises(ContractError):
                read_fields(path)

    def test_review_complete_budget_and_seed(self):
        _, queue, _, _, covered = self.run_analysis()
        labels = [{'field_id':'barc_001','year':2022,'label':'silage','label_raw':'test_s','source_dataset_id':'synthetic-test-only'},
                  {'field_id':'barc_002','year':2022,'label':'grain','label_raw':'test_g','source_dataset_id':'synthetic-test-only'}]
        folds = [{'field_id':r['field_id'],'year':r['year'],'fold_id':r['fold_id']} for r in covered]
        first = simulate_review(covered, queue, labels, folds, budget=1)
        self.assertEqual(first, simulate_review(covered, queue, labels, folds, budget=1))
        self.assertEqual(first['status'], 'evaluated')
        self.assertEqual(first['true_silage_area_ha'], 10)
        self.assertEqual(first['initial_absolute_error_ha'], 3)
        self.assertEqual(first['heuristic_absolute_error_ha'], 2)
        full = simulate_review(covered, queue, labels, folds, budget=2)
        self.assertEqual(full['heuristic_absolute_error_ha'], 0)
        self.assertEqual(full['random_absolute_error_max_ha'], 0)
        self.assertEqual(simulate_review(covered, queue, labels[:-1], folds, budget=1)['status'], 'pending')
        self.assertEqual(simulate_review(covered, queue, labels, folds, budget=3)['status'], 'pending')
        inferred = copy.deepcopy(covered)
        inferred[0]['prediction_role'] = 'inference'
        self.assertEqual(simulate_review(inferred, queue, labels, folds, budget=1)['status'], 'pending')

    def test_cli_pending_and_required_selectors(self):
        script = Path(__file__).with_name('analysis.py').resolve()
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run([sys.executable, str(script), '--year','2022','--prediction-role','oof','--review-budget','3'], cwd=tmp, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            out = Path(tmp)/'data/processed/analysis'
            self.assertEqual(json.loads((out/'summary.json').read_text())['status'], 'pending')
            self.assertEqual(len((out/'review_queue.csv').read_text().splitlines()), 1)
            self.assertEqual(json.loads((out/'review_simulation.json').read_text())['status'], 'pending')
            result = subprocess.run([sys.executable, str(script)], cwd=tmp, capture_output=True)
            self.assertNotEqual(result.returncode, 0)

    def test_cli_reads_and_merges_complete_files(self):
        script = Path(__file__).with_name('analysis.py').resolve()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            geo = {'type': 'FeatureCollection', 'features': [
                {'type': 'Feature', 'properties': {**row, 'source_field_id': row['field_id'][5:],
                 'source_dataset_id': 'synthetic-test-only'},
                 'geometry': {'type': 'Polygon', 'coordinates': [[[0,0],[1,0],[1,1],[0,0]]]}}
                for row in fields()]}
            (root/'fields.geojson').write_text(json.dumps(geo))
            feat = [{**row, 'ndvi_peak': 0.8, 'peak_doy': 200, 'max_drop_per_day': 0.1,
                     'drop_doy': 250, 'ndvi_late_mean': 0.3, 'valid_obs_count': 10,
                     'max_gap_days': 25} for row in features()]
            pred = [{**row, 'predicted_label': 'silage' if row['p_silage'] >= 0.5 else 'grain'}
                    for row in predictions()]
            for name, columns, rows in [('features', FEATURE_COLUMNS, feat), ('predictions', PREDICTION_COLUMNS, pred)]:
                with (root/(name+'.csv')).open('w', newline='') as stream:
                    writer = csv.DictWriter(stream, fieldnames=columns)
                    writer.writeheader()
                    writer.writerows(rows)
            result = subprocess.run([sys.executable, str(script), '--year', '2022', '--prediction-role', 'oof',
                                     '--fields', 'fields.geojson', '--features', 'features.csv',
                                     '--predictions', 'predictions.csv'], cwd=tmp, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads((root/'data/processed/analysis/summary.json').read_text())
            self.assertEqual(summary['expected_silage_area_ha'], 13)
            self.assertEqual(summary['expected_grain_area_ha'], 17)
            self.assertEqual(summary['coverage_fraction'], 0.5)


if __name__ == '__main__':
    unittest.main()
