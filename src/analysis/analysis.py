"""BARC analysis interfaces. Standard library only; no model or price defaults."""
import argparse
import csv
import json
import math
import random
import statistics
from collections import Counter
from pathlib import Path

FEATURE_COLUMNS = 'field_id year ndvi_peak peak_doy max_drop_per_day drop_doy ndvi_late_mean valid_obs_count max_gap_days quality_flag missing_reason'.split()
PREDICTION_COLUMNS = 'field_id year p_silage predicted_label prediction_role fold_id model_version'.split()
LABEL_COLUMNS = 'field_id year label label_raw source_dataset_id'.split()
QUEUE_COLUMNS = 'field_id year prediction_role rank review_score reason'.split()
MISSING_COLUMNS = 'field_id year prediction_role quality_flag missing_reason'.split()
ROLES = {'oof', 'inference'}
QUALITY = {'no_data', 'insufficient', 'limited', 'usable'}
YEARS = {2021, 2022, 2023}


class ContractError(ValueError):
    """Invalid input: abort rather than silently dropping or duplicating records."""


def number(value, name, *, lo=None, hi=None):
    if isinstance(value, bool):
        raise ContractError(f'{name}: boolean is not a number')
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ContractError(f'{name}: expected finite number') from exc
    if not math.isfinite(result) or (lo is not None and result < lo) or (hi is not None and result > hi):
        raise ContractError(f'{name}: out of range or non-finite')
    return result


def integer(value, name):
    result = number(value, name)
    if result != int(result):
        raise ContractError(f'{name}: expected integer')
    return int(result)


def validate_id(value):
    if not isinstance(value, str) or not value.startswith('barc_') or len(value) <= 5 or value != value.strip():
        raise ContractError('field_id must be the unmodified barc_ string assigned by A')


def unique(rows, keys, name):
    counts = Counter(tuple(row[k] for k in keys) for row in rows)
    duplicates = [key for key, count in counts.items() if count > 1]
    if duplicates:
        raise ContractError(f'{name}: duplicate keys {duplicates}')


def load_json(path):
    def reject_constant(value):
        raise ContractError(f'{path}: non-standard JSON constant {value}')
    return json.loads(Path(path).read_text(encoding='utf-8'), parse_constant=reject_constant)


def read_fields(path):
    if not Path(path).exists():
        return None
    data = load_json(path)
    if data.get('type') != 'FeatureCollection' or not isinstance(data.get('features'), list):
        raise ContractError('fields: expected GeoJSON FeatureCollection')
    rows = []
    for feature in data['features']:
        row = dict(feature.get('properties') or {})
        required = {'field_id', 'source_field_id', 'source_dataset_id', 'area_ha'}
        if not required.issubset(row):
            raise ContractError(f'fields: missing properties {sorted(required - row.keys())}')
        validate_id(row['field_id'])
        if not isinstance(row['source_field_id'], str) or not row['source_field_id'] or not row['source_dataset_id']:
            raise ContractError('fields: source identifiers are required strings')
        row['area_ha'] = number(row['area_ha'], 'area_ha', lo=0)
        if row['area_ha'] == 0:
            raise ContractError('area_ha must be positive and supplied by A')
        geometry = feature.get('geometry') or {}
        if geometry.get('type') not in {'Polygon', 'MultiPolygon'} or not geometry.get('coordinates'):
            raise ContractError('fields: polygon geometry is required')
        rows.append(row)
    unique(rows, ['field_id'], 'fields')
    return rows


def read_csv(path, columns, kind):
    if not Path(path).exists():
        return None
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise ContractError(f'{kind}: missing or duplicate CSV headers')
        if not set(columns).issubset(reader.fieldnames):
            raise ContractError(f'{kind}: missing columns {sorted(set(columns) - set(reader.fieldnames))}')
        rows = list(reader)
    for row in rows:
        if None in row or any(v is None for v in row.values()):
            raise ContractError(f'{kind}: malformed CSV row')
        validate_id(row['field_id'])
        row['year'] = integer(row['year'], 'year')
        if row['year'] not in YEARS:
            raise ContractError(f'{kind}: year outside contract BARC 2021-2023')
        if kind == 'features':
            if row['quality_flag'] not in QUALITY:
                raise ContractError('features: unknown quality_flag')
            for key in ['ndvi_peak', 'ndvi_late_mean']:
                if row[key] != '':
                    row[key] = number(row[key], key, lo=-1, hi=1)
            for key in ['peak_doy', 'drop_doy']:
                if row[key] != '':
                    row[key] = integer(row[key], key)
                    if not 1 <= row[key] <= 366:
                        raise ContractError(f'{key}: invalid day of year')
            if row['max_drop_per_day'] != '':
                row['max_drop_per_day'] = number(row['max_drop_per_day'], 'max_drop_per_day', lo=0)
            for key in ['valid_obs_count', 'max_gap_days']:
                row[key] = integer(row[key], key)
                if row[key] < 0:
                    raise ContractError(f'{key}: negative')
            n, gap = row['valid_obs_count'], row['max_gap_days']
            expected = 'no_data' if n == 0 else 'insufficient' if n == 1 else 'limited' if n < 6 or gap > 30 else 'usable'
            if row['quality_flag'] != expected:
                raise ContractError('features: quality_flag contradicts contract observation rules')
        elif kind == 'predictions':
            if row['prediction_role'] not in ROLES:
                raise ContractError('predictions: role must be oof or inference')
            row['p_silage'] = None if row['p_silage'] == '' else number(row['p_silage'], 'p_silage', lo=0, hi=1)
            p = row['p_silage']
            if p is None:
                if row['predicted_label']:
                    raise ContractError('predicted_label without probability')
            else:
                if not row['model_version'] or (row['prediction_role'] == 'oof' and not row['fold_id']):
                    raise ContractError('predictions: calculated probabilities require model_version and OOF fold_id')
                if row['predicted_label'] != ('silage' if p >= 0.5 else 'grain'):
                    raise ContractError('predicted_label inconsistent with probability threshold')
        elif kind == 'labels':
            if row['label'] not in {'grain', 'silage'} or not row['source_dataset_id'] or not row['label_raw']:
                raise ContractError('labels: only sourced, nonblank real labels are accepted')
        elif kind == 'folds' and not row['fold_id']:
            raise ContractError('fold_id must not be blank')
    keys = ['field_id', 'year'] + (['prediction_role'] if kind == 'predictions' else [])
    unique(rows, keys, kind)
    if kind == 'folds':
        by_field = {}
        for row in rows:
            if row['field_id'] in by_field and by_field[row['field_id']] != row['fold_id']:
                raise ContractError('folds: same field appears in different folds across years')
            by_field[row['field_id']] = row['fold_id']
    return rows


def select(rows, year, role=None):
    return [r for r in rows or [] if r['year'] == year and (role is None or r['prediction_role'] == role)]


def cohort_ids(fields, labels, *, year, cohort, smoke=None):
    """Select an explicit annual analysis cohort without generating IDs or labels."""
    if cohort == 'inventory':
        return None
    if fields is None or labels is None:
        raise ContractError('labeled/smoke cohort requires A fields and labels')
    unique(labels, ['field_id', 'year'], 'labels')
    inventory = {row['field_id'] for row in fields}
    if any(row['field_id'] not in inventory for row in labels):
        raise ContractError('labels contain orphan field IDs')
    annual = {row['field_id'] for row in labels if row['year'] == year}
    if cohort == 'labeled':
        return sorted(annual)
    if cohort != 'smoke' or not isinstance(smoke, dict):
        raise ContractError('smoke cohort requires A smoke_sample.json')
    if smoke.get('year') != year or smoke.get('field_id') not in annual:
        raise ContractError('smoke sample must match selected year and a real label')
    return [smoke['field_id']]


def analyze(fields, features, predictions, *, year, prediction_role, selected_ids=None,
            cohort='inventory'):
    if isinstance(year, bool) or not isinstance(year, int) or year not in YEARS or prediction_role not in ROLES:
        raise ContractError('explicit year (2021-2023) and prediction_role (oof/inference) required')
    if fields is not None:
        unique(fields, ['field_id'], 'fields')
    unique(features or [], ['field_id', 'year'], 'features')
    unique(predictions or [], ['field_id', 'year', 'prediction_role'], 'predictions')
    # The public computation API validates numbers too, even when called without CSV readers.
    fields = None if fields is None else [dict(row) for row in fields]
    predictions = None if predictions is None else [dict(row) for row in predictions]
    for row in fields or []:
        validate_id(row['field_id'])
        row['area_ha'] = number(row['area_ha'], 'area_ha', lo=0)
        if row['area_ha'] == 0:
            raise ContractError('area_ha must be positive')
    for row in predictions or []:
        validate_id(row['field_id'])
        if row['prediction_role'] not in ROLES or row['year'] not in YEARS:
            raise ContractError('predictions: invalid year or role')
        if row['p_silage'] is not None:
            row['p_silage'] = number(row['p_silage'], 'p_silage', lo=0, hi=1)
    chosen_features = select(features, year)
    chosen_predictions = select(predictions, year, prediction_role)
    full_inventory = {r['field_id']: r for r in fields or []}
    if selected_ids is not None:
        if len(selected_ids) != len(set(selected_ids)) or set(selected_ids) - full_inventory.keys():
            raise ContractError('selected cohort has duplicate or unknown field IDs')
    inventory = {key: row for key, row in full_inventory.items()
                 if selected_ids is None or key in set(selected_ids)}
    unknown_features = {r['field_id'] for r in features or []} - full_inventory.keys()
    unknown_predictions = {r['field_id'] for r in predictions or []} - full_inventory.keys()
    if fields is not None and (unknown_features or unknown_predictions):
        raise ContractError('orphan IDs cannot be merged: ' + json.dumps({
            'unmatched_feature_ids': sorted(unknown_features),
            'unmatched_prediction_ids': sorted(unknown_predictions)}))
    outside_features = sorted({r['field_id'] for r in chosen_features} - inventory.keys())
    outside_predictions = sorted({r['field_id'] for r in chosen_predictions} - inventory.keys())
    chosen_features = [r for r in chosen_features if r['field_id'] in inventory]
    chosen_predictions = [r for r in chosen_predictions if r['field_id'] in inventory]
    feature_map = {r['field_id']: r for r in chosen_features}
    prediction_map = {r['field_id']: r for r in chosen_predictions}
    audit = {'inputs': {'fields': None if fields is None else len(fields), 'features': None if features is None else len(features), 'predictions': None if predictions is None else len(predictions)},
             'year': year, 'prediction_role': prediction_role, 'duplicate_keys': [],
             'cohort': cohort, 'selected_field_rows': len(inventory),
             'excluded_inventory_ids': sorted(full_inventory.keys() - inventory.keys()),
             'excluded_outside_cohort_feature_ids': outside_features,
             'excluded_outside_cohort_prediction_ids': outside_predictions,
             'selected_feature_rows': len(chosen_features), 'selected_prediction_rows': len(chosen_predictions),
             'excluded_other_year_feature_rows': len(features or []) - len(select(features, year)),
             'excluded_other_year_or_role_prediction_rows': len(predictions or []) - len(select(predictions, year, prediction_role)),
             'unmatched_feature_ids': sorted(feature_map.keys() - inventory.keys()),
             'unmatched_prediction_ids': sorted(prediction_map.keys() - inventory.keys()),
             'missing_feature_ids': sorted(inventory.keys() - feature_map.keys()),
             'missing_prediction_ids': sorted(inventory.keys() - prediction_map.keys()),
             'matched_feature_rows': len(inventory.keys() & feature_map.keys()),
             'matched_prediction_rows': len(inventory.keys() & prediction_map.keys()),
             'missing_files': [name for name, rows in [('fields.geojson', fields), ('features.csv', features), ('predictions.csv', predictions)] if rows is None]}
    if fields is not None and (audit['unmatched_feature_ids'] or audit['unmatched_prediction_ids']):
        raise ContractError('orphan IDs cannot be merged: ' + json.dumps(audit, ensure_ascii=False))
    covered, queue, missing = [], [], []
    for field_id in sorted(inventory):
        field, feature, prediction = inventory[field_id], feature_map.get(field_id), prediction_map.get(field_id)
        p = None if prediction is None else prediction['p_silage']
        reasons = []
        if p is None:
            reasons.append('missing_prediction')
        if feature is None:
            reasons.append('missing_features')
        elif feature['quality_flag'] != 'usable':
            reasons.append('quality_' + feature['quality_flag'])
            if feature.get('missing_reason'):
                reasons.append(feature['missing_reason'])
        if p is not None:
            covered.append({'field_id': field_id, 'year': year, 'prediction_role': prediction_role,
                            'area_ha': field['area_ha'], 'p_silage': p,
                            'fold_id': prediction.get('fold_id', ''), 'model_version': prediction.get('model_version', '')})
        if reasons:
            missing.append({'field_id': field_id, 'year': year, 'prediction_role': prediction_role,
                            'quality_flag': '' if feature is None else feature['quality_flag'], 'missing_reason': ';'.join(reasons)})
        else:
            queue.append({'field_id': field_id, 'year': year, 'prediction_role': prediction_role,
                          'review_score': field['area_ha'] * 4 * p * (1-p),
                          'reason': 'area_ha * 4*p_silage*(1-p_silage); usable observations; unvalidated heuristic'})
    queue.sort(key=lambda r: (-r['review_score'], r['field_id']))
    for rank, row in enumerate(queue, 1):
        row['rank'] = rank
    known = fields is not None
    total = math.fsum(r['area_ha'] for r in inventory.values()) if known else None
    covered_area = math.fsum(r['area_ha'] for r in covered) if known else None
    silage = math.fsum(r['area_ha'] * r['p_silage'] for r in covered) if covered else None
    grain = math.fsum(r['area_ha'] * (1-r['p_silage']) for r in covered) if covered else None
    summary = {'status': 'computed' if covered else 'pending', 'year': year,
               'scope': {'dataset': 'BARC', 'field_ids': sorted(inventory), 'cohort': cohort,
                         'representative_of_county_or_state': False},
               'prediction_role': prediction_role, 'total_area_ha': total, 'covered_area_ha': covered_area,
               'coverage_fraction': covered_area/total if total else None,
               'expected_silage_area_ha': silage, 'expected_grain_area_ha': grain,
               'economic_scenario': None,
               'notes': ['Denominator is the explicitly selected cohort, not verified annual BARC/county/state corn acreage.',
                         'All 83 boundaries are not assumed to be corn every year. Labeled and smoke cohorts are selected samples, not a census.',
                         'Areas with predictions include low-quality observations; those records are excluded from review ranking and listed in data_needed.csv.',
                         'Missing predictions are not grain. Quality is not model accuracy. No interval or review benefit is claimed.',
                         'Missing economic inputs: regional/year-matched crop yields, prices, units, price basis, conversions and sources.']}
    audit['covered_prediction_rows'] = len(covered)
    audit['review_queue_rows'] = len(queue)
    audit['data_needed_rows'] = len(missing)
    return summary, queue, missing, audit, covered


def simulate_review(covered, queue, labels, folds, *, budget, seed=42, random_repeats=200):
    """Caller supplies sourced labels; never infer truth from a prediction."""
    if not isinstance(budget, int) or isinstance(budget, bool) or budget < 0:
        raise ContractError('budget must be a nonnegative number of whole-field reviews')
    if not isinstance(random_repeats, int) or random_repeats < 1:
        raise ContractError('random_repeats must be positive')
    pending = {'status': 'pending', 'budget': budget, 'seed': seed, 'random_repeats': random_repeats,
               'n_evaluated': 0, 'true_silage_area_ha': None, 'initial_absolute_error_ha': None,
               'heuristic_absolute_error_ha': None, 'random_absolute_error_median_ha': None,
               'random_absolute_error_min_ha': None, 'random_absolute_error_max_ha': None,
               'heuristic_review_ids': [], 'notes': []}
    if not covered or labels is None or folds is None:
        pending['notes'] = ['Requires OOF probabilities, sourced real labels, and A validation_folds.csv.']
        return pending
    if any(r['prediction_role'] != 'oof' for r in covered):
        pending['notes'] = ['Inference probabilities cannot be used to evaluate review benefit.']
        return pending
    if len({r['year'] for r in covered}) != 1:
        raise ContractError('review simulation must contain exactly one year')
    year = covered[0]['year']
    unique(covered, ['field_id', 'year'], 'covered')
    unique(labels, ['field_id', 'year'], 'labels')
    unique(folds, ['field_id', 'year'], 'folds')
    truths = {r['field_id']: r for r in labels if r['year'] == year}
    fold_map = {r['field_id']: r['fold_id'] for r in folds if r['year'] == year}
    by_id = {r['field_id']: r for r in covered}
    for row in covered:
        label = truths.get(row['field_id'])
        if (label is None or label['label'] not in {'grain', 'silage'} or not label.get('source_dataset_id')
                or not label.get('label_raw') or not row['fold_id'] or fold_map.get(row['field_id']) != row['fold_id']):
            pending['notes'] = ['Incomplete real labels or inconsistent/missing OOF fold provenance; no benefit evaluation.']
            return pending
    candidates = [r['field_id'] for r in sorted(queue, key=lambda r: r['rank'])]
    if len(set(candidates)) != len(candidates) or any(key not in by_id for key in candidates):
        raise ContractError('review queue duplicates or unknown fields')
    if budget > len(candidates):
        pending['notes'] = ['Budget exceeds available usable candidates; no silent budget reduction.']
        return pending
    truth = math.fsum(r['area_ha'] * (truths[r['field_id']]['label'] == 'silage') for r in covered)
    initial = math.fsum(r['area_ha'] * r['p_silage'] for r in covered)
    def error(ids):
        adjustment = math.fsum(by_id[key]['area_ha'] * ((truths[key]['label'] == 'silage') - by_id[key]['p_silage']) for key in ids)
        return abs(initial + adjustment - truth)
    rng = random.Random(seed)
    errors = [error(rng.sample(sorted(candidates), budget)) for _ in range(random_repeats)]
    pending.update(status='evaluated', n_evaluated=len(covered), true_silage_area_ha=truth,
                   initial_absolute_error_ha=abs(initial-truth), heuristic_absolute_error_ha=error(candidates[:budget]),
                   random_absolute_error_median_ha=statistics.median(errors), random_absolute_error_min_ha=min(errors),
                   random_absolute_error_max_ha=max(errors), heuristic_review_ids=candidates[:budget],
                   notes=['Same candidate pool and whole-field budget for both strategies. Aggregate error covers the same complete labeled OOF cohort.',
                          'OOF provenance relies on C and A; this interface cannot inspect model training history. This cohort is not a county/state representative sample.'])
    return pending


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def write_csv(path, columns, rows):
    with Path(path).open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--year', required=True, type=int, choices=sorted(YEARS))
    parser.add_argument('--prediction-role', required=True, choices=sorted(ROLES))
    parser.add_argument('--fields', type=Path, default=Path('data/processed/core/fields.geojson'))
    parser.add_argument('--features', type=Path, default=Path('data/processed/satellite/features.csv'))
    parser.add_argument('--predictions', type=Path, default=Path('data/processed/model/predictions.csv'))
    parser.add_argument('--labels', type=Path, default=Path('data/processed/core/labels.csv'))
    parser.add_argument('--folds', type=Path, default=Path('data/processed/core/validation_folds.csv'))
    parser.add_argument('--cohort', choices=['inventory', 'labeled', 'smoke'], default='inventory')
    parser.add_argument('--smoke-sample', type=Path, default=Path('data/processed/core/smoke_sample.json'))
    parser.add_argument('--review-budget', type=int)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--random-repeats', type=int, default=200)
    parser.add_argument('--output-root', type=Path, default=Path('data/processed/analysis'))
    args = parser.parse_args()
    try:
        fields = read_fields(args.fields)
        features = read_csv(args.features, FEATURE_COLUMNS, 'features')
        predictions = read_csv(args.predictions, PREDICTION_COLUMNS, 'predictions')
        labels = read_csv(args.labels, LABEL_COLUMNS, 'labels') if args.cohort != 'inventory' or args.review_budget is not None else None
        smoke = load_json(args.smoke_sample) if args.cohort == 'smoke' else None
        selected = cohort_ids(fields, labels, year=args.year, cohort=args.cohort, smoke=smoke)
        summary, queue, missing, audit, covered = analyze(fields, features, predictions, year=args.year,
            prediction_role=args.prediction_role, selected_ids=selected, cohort=args.cohort)
        simulation = None
        if args.review_budget is not None:
            folds = read_csv(args.folds, ['field_id', 'year', 'fold_id'], 'folds')
            simulation = simulate_review(covered, queue, labels, folds, budget=args.review_budget, seed=args.seed, random_repeats=args.random_repeats)
        # Compute and validate everything before changing any published output.
        out = args.output_root
        out.mkdir(parents=True, exist_ok=True)
        write_json(out / 'summary.json', summary)
        write_csv(out / 'review_queue.csv', QUEUE_COLUMNS, queue)
        write_csv(out / 'data_needed.csv', MISSING_COLUMNS, missing)
        write_json(out / 'merge_audit.json', audit)
        if simulation is not None:
            write_json(out / 'review_simulation.json', simulation)
        elif (out / 'review_simulation.json').exists():
            # Replace stale evaluation from a previous run, never leave it looking current.
            write_json(out / 'review_simulation.json', {'status': 'pending', 'notes': ['Review simulation not requested in this run.']})
        print(json.dumps({'output_dir': str(out), 'status': summary['status'], 'missing_files': audit['missing_files']}))
    except (ContractError, json.JSONDecodeError, OSError) as exc:
        parser.exit(2, f'analysis failed: {exc}\n')


if __name__ == '__main__':
    main()
