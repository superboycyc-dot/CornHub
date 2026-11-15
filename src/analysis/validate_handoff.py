"""Read-only validation of A's core handoff and annual analysis integration run."""
import argparse
import hashlib
import json
import math
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from analysis import (ContractError, FEATURE_COLUMNS, LABEL_COLUMNS, PREDICTION_COLUMNS,
                      cohort_ids, load_json, read_csv, read_fields, write_json)


def validate_core(fields, labels, folds, smoke):
    if fields is None or labels is None or folds is None:
        raise ContractError('A core handoff is incomplete')
    inventory = {row['field_id']: row for row in fields}
    label_keys = {(row['field_id'], row['year']) for row in labels}
    fold_keys = {(row['field_id'], row['year']) for row in folds}
    if label_keys != fold_keys:
        raise ContractError('label and fold keys must match exactly')
    if any(key[0] not in inventory for key in label_keys):
        raise ContractError('labels contain orphan IDs')
    if not labels:
        raise ContractError('no real labels supplied')
    first = min(labels, key=lambda row: (row['field_id'], row['year']))
    if (smoke.get('field_id'), smoke.get('year')) != (first['field_id'], first['year']):
        raise ContractError('smoke sample differs from A first labeled record')
    year = smoke['year']
    if smoke.get('window_start') != f'{year}-04-01' or smoke.get('window_end_exclusive') != f'{year}-12-01':
        raise ContractError('smoke sample differs from contract time window')
    if smoke.get('source_dataset_id') != first['source_dataset_id']:
        raise ContractError('smoke sample source differs from label source')
    cohort_ids(fields, labels, year=year, cohort='smoke', smoke=smoke)
    by_farm, by_field = {}, {}
    for row in folds:
        key, fold = row['field_id'], row['fold_id']
        farm = inventory[key].get('farm_group')
        if not farm:
            raise ContractError('A farm_group is required to validate farm separation')
        for groups, group in [(by_field, key), (by_farm, farm)]:
            if group in groups and groups[group] != fold:
                raise ContractError('same field/farm crosses validation folds')
            groups[group] = fold
    annual = {}
    for year in sorted({row['year'] for row in labels}):
        rows = [row for row in labels if row['year'] == year]
        annual[str(year)] = {
            'n_labeled_fields': len(rows), 'class_counts': dict(Counter(row['label'] for row in rows)),
            'selected_labeled_area_ha': math.fsum(inventory[row['field_id']]['area_ha'] for row in rows)}
    return {
        'status': 'validated', 'n_boundary_fields': len(fields), 'n_label_rows': len(labels),
        'n_labeled_fields': len({row['field_id'] for row in labels}), 'n_fold_rows': len(folds),
        'n_farms_with_labels': len(by_farm), 'fold_ids': sorted(set(by_farm.values())),
        'static_boundary_inventory_area_ha': math.fsum(row['area_ha'] for row in fields),
        'annual_labeled_cohorts': annual, 'smoke_sample': smoke,
        'checks': ['unique field and annual keys', 'positive finite source areas', 'no orphan labels',
                   'label/fold keys match', 'same field and farm never cross folds',
                   'canonical smoke sample and window'],
        'limitations': ['Static boundary inventory is not annual corn acreage.',
                       'Annual labeled cohorts and the smoke sample are selected BARC samples, not a census.',
                       'No independent geometry reprojection or ground truth verification by D.',
                       'A documents five farm folds as an explicit exception to the older three-field-fold contract.',
                       'A documents restricted class support and one training fold with one silage label.',
                       'OOF training exclusion remains C responsibility; no model or ranking effectiveness claimed.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--core-root', type=Path, default=Path('data/processed/core'))
    parser.add_argument('--features', type=Path, default=Path('data/processed/satellite/features.csv'))
    parser.add_argument('--predictions', type=Path, default=Path('data/processed/model/predictions.csv'))
    parser.add_argument('--acceptance', type=Path)
    parser.add_argument('--a-ref', required=True)
    parser.add_argument('--b-ref')
    parser.add_argument('--c-ref')
    parser.add_argument('--prediction-role', required=True, choices=['oof', 'inference'])
    parser.add_argument('--output-root', type=Path, default=Path('data/processed/analysis'))
    parser.add_argument('--report-root', type=Path, default=Path('reports/d_analysis'))
    args = parser.parse_args()
    try:
        for ref in [args.a_ref, args.b_ref, args.c_ref]:
            if ref is not None and not re.fullmatch(r'[0-9a-f]{40}', ref):
                raise ContractError('source refs must be immutable full commit SHAs')
        core = args.core_root
        fields = read_fields(core/'fields.geojson')
        labels = read_csv(core/'labels.csv', LABEL_COLUMNS, 'labels')
        folds = read_csv(core/'validation_folds.csv', ['field_id', 'year', 'fold_id'], 'folds')
        smoke = load_json(core/'smoke_sample.json')
        report = validate_core(fields, labels, folds, smoke)
        # Validate all B/C rows before any outputs are written, even outside the smoke cohort.
        features = read_csv(args.features, FEATURE_COLUMNS, 'features')
        predictions = read_csv(args.predictions, PREDICTION_COLUMNS, 'predictions')
        sources = [(f'data/processed/core/{name}', core/name, args.a_ref) for name in
                   ['fields.geojson', 'labels.csv', 'validation_folds.csv', 'smoke_sample.json']]
        sources += [('data/processed/satellite/features.csv', args.features, args.b_ref),
                    ('data/processed/model/predictions.csv', args.predictions, args.c_ref)]
        report['inputs'] = []
        expected = load_json(args.acceptance)['output_sha256'] if args.acceptance else {}
        for logical, path, ref in sources:
            entry = {'path': logical, 'commit': ref, 'exists': path.exists(), 'sha256': None, 'git_blob_sha': None}
            if path.exists():
                content = path.read_bytes()
                entry['sha256'] = hashlib.sha256(content).hexdigest()
                entry['git_blob_sha'] = hashlib.sha1(f'blob {len(content)}\0'.encode()+content).hexdigest()
                if logical.startswith('data/processed/core/') and path.name in expected:
                    if entry['sha256'] != expected[path.name]:
                        raise ContractError(f'A acceptance checksum mismatch: {path.name}')
                    entry['matches_A_acceptance_sha256'] = True
            report['inputs'].append(entry)
        report['upstream_rows'] = {'features': None if features is None else len(features),
                                   'predictions': None if predictions is None else len(predictions)}
        report['checked_at_utc'] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        report['analysis_runs'] = []
        script = Path(__file__).with_name('analysis.py')
        runs = [('smoke', smoke['year'], args.output_root)]
        runs += [('labeled', int(year), args.output_root/year/args.prediction_role)
                 for year in report['annual_labeled_cohorts']]
        for cohort, year, out in runs:
            cmd = [sys.executable, str(script), '--year', str(year), '--prediction-role', args.prediction_role,
                   '--cohort', cohort, '--fields', str(core/'fields.geojson'), '--labels', str(core/'labels.csv'),
                   '--folds', str(core/'validation_folds.csv'), '--smoke-sample', str(core/'smoke_sample.json'),
                   '--features', str(args.features), '--predictions', str(args.predictions),
                   '--review-budget', '1' if cohort == 'smoke' else '3', '--output-root', str(out)]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode:
                raise ContractError(result.stderr.strip())
            summary = load_json(out/'summary.json')
            report['analysis_runs'].append({'cohort': cohort, 'year': year, 'prediction_role': args.prediction_role,
                'n_fields': len(summary['scope']['field_ids']), 'status': summary['status'],
                'selected_area_ha': summary['total_area_ha'], 'covered_area_ha': summary['covered_area_ha']})
        args.report_root.mkdir(parents=True, exist_ok=True)
        write_json(args.report_root/'handoff_validation.json', report)
        print(json.dumps({'status': report['status'], 'n_fields': len(fields), 'n_labels': len(labels),
                          'analysis_runs': report['analysis_runs']}))
    except (ContractError, OSError, json.JSONDecodeError) as exc:
        parser.exit(2, f'handoff validation failed: {exc}\n')


if __name__ == '__main__':
    main()
