"""Audit real OOF results and report feature coverage separately from predictions."""
import argparse
import csv
import hashlib
import math
import random
import re
import statistics
from collections import Counter
from pathlib import Path

from analysis import (ContractError, FEATURE_COLUMNS, LABEL_COLUMNS, PREDICTION_COLUMNS,
                      load_json, read_csv, read_fields, write_csv, write_json)


def feature_coverage(fields, features, summary):
    ids = set(summary['scope']['field_ids'])
    inventory = {r['field_id']: r for r in fields or [] if r['field_id'] in ids}
    rows = {r['field_id']: r for r in features or []
            if r['year'] == summary['year'] and r['field_id'] in ids}
    groups = {q: [] for q in ['missing_features', 'no_data', 'insufficient', 'limited', 'usable']}
    for key in sorted(ids):
        groups[rows[key]['quality_flag'] if key in rows else 'missing_features'].append(key)
    total = summary['total_area_ha']
    def area(keys):
        return math.fsum(inventory[key]['area_ha'] for key in keys) if fields is not None else None
    def fraction(value):
        return value / total if total else None
    valid = [key for key, row in rows.items() if row['valid_obs_count'] > 0]
    days = [r['valid_obs_count'] for r in rows.values()]
    gaps = [r['max_gap_days'] for r in rows.values()]
    return {'year': summary['year'], 'scope': summary['scope'], 'n_matched_features': len(rows),
            'feature_matched_area_ha': area(rows), 'feature_match_fraction': fraction(area(rows)),
            'fields_with_valid_days_area_ha': area(valid),
            'fields_with_valid_days_area_fraction': fraction(area(valid)),
            'usable_feature_area_ha': area(groups['usable']),
            'usable_feature_area_fraction': fraction(area(groups['usable'])),
            'quality_counts': {q: len(keys) for q, keys in groups.items()},
            'quality_area_ha': {q: area(keys) for q, keys in groups.items()},
            'valid_day_count_min': min(days) if days else None, 'valid_day_count_max': max(days) if days else None,
            'max_gap_days_min': min(gaps) if gaps else None, 'max_gap_days_max': max(gaps) if gaps else None,
            'notes': ['Field-level feature availability is not full seasonal/pixel coverage or model accuracy.',
                      'Quality rules are unchanged. These are selected BARC samples, not a census.']}


def close(actual, expected):
    if not math.isclose(actual, expected, rel_tol=0, abs_tol=1e-10):
        raise ContractError(f'independent result check failed: {actual} != {expected}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-root', type=Path, default=Path('data/processed'))
    parser.add_argument('--model-report', type=Path, default=Path('reports/c_model/merge_report.json'))
    parser.add_argument('--output-root', type=Path, default=Path('data/processed/analysis'))
    parser.add_argument('--report-root', type=Path, default=Path('reports/d_analysis'))
    parser.add_argument('--c-ref', required=True)
    parser.add_argument('--prediction-role', required=True, choices=['oof'])
    args = parser.parse_args()
    try:
        if not re.fullmatch('[0-9a-f]{40}', args.c_ref):
            raise ContractError('C ref must be an immutable full commit SHA')
        root = args.input_root
        fields = read_fields(root/'core/fields.geojson')
        labels = read_csv(root/'core/labels.csv', LABEL_COLUMNS, 'labels')
        folds = read_csv(root/'core/validation_folds.csv', ['field_id', 'year', 'fold_id'], 'folds')
        features = read_csv(root/'satellite/features.csv', FEATURE_COLUMNS, 'features')
        predictions = read_csv(root/'model/predictions.csv', PREDICTION_COLUMNS, 'predictions')
        if any(rows is None for rows in [fields, labels, folds, features, predictions]):
            raise ContractError('real handoff inputs required; no synthetic fallback')
        model = load_json(args.model_report)
        audit = load_json(args.report_root/'handoff_validation.json')
        if any(r['commit'] != args.c_ref for r in audit['inputs'] if r['path'].endswith('predictions.csv')):
            raise ContractError('C ref differs from integration input provenance')
        for path, sha in model['input_sha256'].items():
            if path not in {'core/labels.csv', 'core/validation_folds.csv', 'core/fields.geojson', 'satellite/features.csv'}:
                raise ContractError('unexpected model input path')
            if hashlib.sha256((root/path).read_bytes()).hexdigest() != sha:
                raise ContractError(f'C training input hash mismatch: {path}')
        expected_refs = {r['commit'] for r in audit['inputs'] if not r['path'].endswith('predictions.csv')}
        if {r['commit'] for r in model['input_provenance']['sources']} != expected_refs:
            raise ContractError('C A/B source refs differ from D inputs')
        areas = {r['field_id']: r['area_ha'] for r in fields}
        truth = {(r['field_id'], r['year']): r['label'] == 'silage' for r in labels}
        fold_map = {(r['field_id'], r['year']): r['fold_id'] for r in folds}
        quality = {(r['field_id'], r['year']): r['quality_flag'] for r in features}
        for row in predictions:
            key = row['field_id'], row['year']
            if key not in truth or key not in quality:
                raise ContractError('prediction without real label/features in this evaluation cohort')
            if row['prediction_role'] == 'oof' and row['fold_id'] != fold_map.get(key):
                raise ContractError('OOF fold differs from A')
        report = {'status': 'checked', 'model_commit': args.c_ref,
                  'role_counts': dict(Counter(r['prediction_role'] for r in predictions)),
                  'source_hashes_and_refs_match_C_training_inputs': True,
                  'model_versions': sorted({r['model_version'] for r in predictions}), 'annual_checks': [],
                  'notes': ['OOF training exclusion relies on C; D does not retrain models.',
                            'Probabilities are uncalibrated; areas are exploratory sample estimates.',
                            'Manual review assumes perfect whole-field label revelation; no field survey was performed.',
                            'An observed error increase is retained; no general ranking effectiveness is claimed.']}
        comparisons, sidecars = [], []
        outputs = [args.output_root] + [args.output_root/str(y)/'oof' for y in sorted({r['year'] for r in labels})]
        for out in outputs:
            summary = load_json(out/'summary.json')
            if summary['prediction_role'] != 'oof':
                raise ContractError('inference cannot enter real review evaluation')
            coverage = feature_coverage(fields, features, summary)
            sidecars.append((out/'feature_coverage.json', coverage))
            year, ids = summary['year'], set(summary['scope']['field_ids'])
            rows = [r for r in predictions if r['prediction_role'] == 'oof' and r['year'] == year and r['field_id'] in ids]
            if len(rows) != len(ids):
                raise ContractError('incomplete real OOF cohort')
            silage = math.fsum(areas[r['field_id']]*r['p_silage'] for r in rows)
            grain = math.fsum(areas[r['field_id']]*(1-r['p_silage']) for r in rows)
            close(silage, summary['expected_silage_area_ha'])
            close(grain, summary['expected_grain_area_ha'])
            close(silage+grain, summary['covered_area_ha'])
            if summary['scope']['cohort'] == 'smoke':
                continue
            ranked = sorted([r for r in rows if quality[(r['field_id'], year)] == 'usable'],
                key=lambda r: (-areas[r['field_id']]*4*r['p_silage']*(1-r['p_silage']), r['field_id']))
            with (out/'review_queue.csv').open() as stream:
                queue = list(csv.DictReader(stream))
            if [r['field_id'] for r in ranked] != [r['field_id'] for r in queue]:
                raise ContractError('queue does not match contract ranking')
            sim = load_json(out/'review_simulation.json')
            if (sim['budget'], sim['seed'], sim['random_repeats']) != (3, 42, 200):
                raise ContractError('unexpected budget or random seed/repeats')
            true_area = math.fsum(areas[r['field_id']] for r in rows if truth[(r['field_id'], year)])
            def error(reviewed):
                return abs(math.fsum(areas[r['field_id']] *
                    (float(truth[(r['field_id'], year)]) if r['field_id'] in reviewed else r['p_silage'])
                    for r in rows) - true_area)
            change = None
            if len(ranked) >= 3:
                heuristic_error = error({r['field_id'] for r in ranked[:3]})
                rng, pool = random.Random(42), sorted(r['field_id'] for r in ranked)
                errors = [error(set(rng.sample(pool, 3))) for _ in range(200)]
                for actual, key in [(error(set()), 'initial_absolute_error_ha'),
                        (heuristic_error, 'heuristic_absolute_error_ha'),
                        (statistics.median(errors), 'random_absolute_error_median_ha'),
                        (min(errors), 'random_absolute_error_min_ha'), (max(errors), 'random_absolute_error_max_ha')]:
                    close(actual, sim[key])
                change = heuristic_error-error(set())
            elif sim['status'] != 'pending':
                raise ContractError('insufficient usable candidates must stay pending')
            row = {'year': year, 'prediction_role': 'oof', 'status': sim['status'], 'budget': 3,
                   'seed': 42, 'random_repeats': 200, 'n_candidates': len(ranked),
                   **{k: sim[k] for k in ['initial_absolute_error_ha', 'heuristic_absolute_error_ha',
                      'random_absolute_error_median_ha', 'random_absolute_error_min_ha', 'random_absolute_error_max_ha']},
                   'change_in_absolute_error_ha': change}
            comparisons.append(row)
            report['annual_checks'].append({**row, 'area_conservation_and_rank_checked': True})
        # All checks complete before publishing supplementary artifacts.
        for path, value in sidecars:
            write_json(path, value)
        write_json(args.report_root/'prediction_handoff_review.json', report)
        write_csv(args.report_root/'review_comparison.csv', comparisons[0].keys(), comparisons)
        print('Real OOF provenance, annual areas, ranks and equal-budget simulations checked')
    except (ContractError, OSError, ValueError, KeyError) as exc:
        parser.exit(2, f'result audit failed: {exc}\n')


if __name__ == '__main__':
    main()
