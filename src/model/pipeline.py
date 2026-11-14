"""Contract-driven BARC baseline; no data or dependency required for pending mode."""
import argparse
import calendar
import csv
import json
import math
from pathlib import Path

FEATURES = ['ndvi_peak', 'peak_doy', 'max_drop_per_day', 'drop_doy', 'ndvi_late_mean', 'valid_obs_count', 'max_gap_days']
SCHEMAS = {
    'labels': ['field_id', 'year', 'label', 'label_raw', 'source_dataset_id'],
    'folds': ['field_id', 'year', 'fold_id'],
    'features': ['field_id', 'year', *FEATURES, 'quality_flag', 'missing_reason'],
}
HEADER = ['field_id', 'year', 'p_silage', 'predicted_label', 'prediction_role', 'fold_id', 'model_version']
VERSION = 'rf_v1_uncalibrated'


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def write_csv(path, header, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)


def metrics(y=None, p=None, notes=None):
    result = dict(status='pending', prediction_role='oof', n_evaluated=0,
                  class_counts={'grain': 0, 'silage': 0}, macro_f1=None,
                  silage_precision=None, silage_recall=None, brier_score=None,
                  confusion_matrix=None, notes=list(notes or []))
    if not y:
        return result
    predicted = [int(v >= .5) for v in p]
    cm = [[sum(a == i and b == j for a, b in zip(y, predicted)) for j in (0, 1)] for i in (0, 1)]
    tn, fp = cm[0]
    fn, tp = cm[1]
    counts = {name: y.count(i) for i, name in enumerate(('grain', 'silage'))}
    result.update(status='evaluated', n_evaluated=len(y), class_counts=counts,
                  confusion_matrix={name: dict(zip(('grain', 'silage'), cm[i])) for i, name in enumerate(('grain', 'silage'))},
                  silage_precision=tp / (tp + fp) if tp + fp else None,
                  silage_recall=tp / (tp + fn) if tp + fn else None,
                  brier_score=sum((a - b) ** 2 for a, b in zip(y, p)) / len(y))
    if all(counts.values()):
        result['macro_f1'] = (2 * tn / (2 * tn + fp + fn) + 2 * tp / (2 * tp + fp + fn)) / 2
    else:
        result['notes'].append('macro_f1 null: evaluation truth lacks a class; Brier remains defined.')
    if result['silage_precision'] is None:
        result['notes'].append('silage_precision null: no predicted silage.')
    if result['silage_recall'] is None:
        result['notes'].append('silage_recall null: no true silage.')
    return result


def load(path, kind, audit):
    if not path.exists():
        audit['missing_files'].append(str(path))
        return {}
    with path.open(newline='', encoding='utf-8') as stream:
        reader = csv.DictReader(stream)
        columns = reader.fieldnames or []
        if len(columns) != len(set(columns)) or not set(SCHEMAS[kind]) <= set(columns):
            audit['errors'].append(f'{kind}: duplicate or missing columns; required {SCHEMAS[kind]}')
            return {}
        rows = list(reader)
    audit['input_rows'][kind] = len(rows)
    indexed = {}
    for line, row in enumerate(rows, 2):
        try:
            if None in row or any(v is None for v in row.values()):
                raise ValueError('malformed CSV row')
            fid = row['field_id']
            if not fid.startswith('barc_') or not fid[5:] or fid != fid.strip():
                raise ValueError('invalid field_id; A must supply canonical string ID')
            if row['year'] not in ('2021', '2022', '2023'):
                raise ValueError('year outside contract or not integer')
            row['year'] = int(row['year'])
            key = (fid, row['year'])
            if key in indexed:
                audit['duplicate_keys'].append(dict(table=kind, field_id=fid, year=row['year']))
                raise ValueError('duplicate field_id+year')
            if kind == 'labels' and (row['label'] not in ('grain', 'silage') or not row['source_dataset_id'] or not row['label_raw']):
                raise ValueError('invalid label or missing provenance')
            if kind == 'folds' and not row['fold_id'].strip():
                raise ValueError('empty fold_id')
            if kind == 'features':
                for col in FEATURES:
                    value = row[col]
                    row[col] = float(value) if value else None
                    v = row[col]
                    if v is not None and not math.isfinite(v):
                        raise ValueError(f'{col}: nonfinite')
                    if v is not None:
                        if col.startswith('ndvi_') and not -1 <= v <= 1:
                            raise ValueError(f'{col}: outside [-1,1]')
                        if col.endswith('_doy') and (not v.is_integer() or not 1 <= v <= 365 + calendar.isleap(row['year'])):
                            raise ValueError(f'{col}: invalid day')
                        if col in ('valid_obs_count', 'max_gap_days') and (not v.is_integer() or not 0 <= v <= 244):
                            raise ValueError(f'{col}: invalid count/gap')
                        if col == 'max_drop_per_day' and not 0 <= v <= 2:
                            raise ValueError('invalid max_drop_per_day')
                n, gap = row['valid_obs_count'], row['max_gap_days']
                if n is None or gap is None:
                    raise ValueError('count/gap required')
                expected = 'no_data' if n == 0 else 'insufficient' if n == 1 else 'limited' if n < 6 or gap > 30 else 'usable'
                if row['quality_flag'] != expected:
                    raise ValueError('quality_flag inconsistent with count/gap')
                if n == 0 and (any(row[c] is not None for c in FEATURES[:5]) or gap != 244):
                    raise ValueError('no_data must have empty vegetation features and full-window gap')
                if expected != 'usable' and not row['missing_reason'].strip():
                    raise ValueError('missing_reason required for degraded quality')
            indexed[key] = row
        except (ValueError, TypeError) as exc:
            audit['errors'].append(f'{kind} line {line}: {exc}')
    return indexed


def run(root, out, report, train=False, inference=False):
    audit = dict(input_rows={}, missing_files=[], errors=[], duplicate_keys=[], matched_count=0,
                 unmatched=[], exclusions=[], folds=[], features=FEATURES, calibration='not performed; probabilities uncalibrated, reliability unproven')
    labels = load(root / 'core/labels.csv', 'labels', audit)
    folds = load(root / 'core/validation_folds.csv', 'folds', audit)
    features = load(root / 'satellite/features.csv', 'features', audit)
    by_field = {}
    for key, row in folds.items():
        if key[0] in by_field and by_field[key[0]] != row['fold_id']:
            audit['errors'].append(f'field crosses folds: {key[0]}')
        by_field[key[0]] = row['fold_id']
    for name, table in [('features', features), ('folds', folds)]:
        for fid, year in sorted(set(table) - set(labels)):
            audit['unmatched'].append(dict(table=name, field_id=fid, year=year, reason='no_label'))
    eligible = []
    for key, label in sorted(labels.items()):
        reasons = []
        for name, table in [('features', features), ('folds', folds)]:
            if key not in table:
                reasons.append('missing_' + name)
                audit['unmatched'].append(dict(table='labels', field_id=key[0], year=key[1], reason='missing_' + name))
        if key in features and features[key]['quality_flag'] in ('no_data', 'insufficient'):
            reasons.append(features[key]['quality_flag'] + ':' + features[key]['missing_reason'])
        if reasons:
            audit['exclusions'].append(dict(field_id=key[0], year=key[1], reasons=reasons))
        else:
            eligible.append({**label, **features[key], **folds[key]})
    audit['matched_count'] = len(set(labels) & set(features) & set(folds))
    audit['eligible_count'] = len(eligible)
    notes = ['Uncalibrated exploratory BARC baseline; no probability reliability claim.']
    predictions, truth, probs, rule_y, rule_p = [], [], [], [], []
    if audit['errors'] or audit['missing_files']:
        notes.append('Blocked by missing files or schema errors; see merge_report.json.')
    elif not train:
        notes.append('Interface-only run; pass --train after real data and authorized validation splits are ready.')
    elif not eligible:
        notes.append('No eligible labeled feature rows.')
    else:
        import numpy as np
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.impute import SimpleImputer
        from sklearn.pipeline import make_pipeline

        def fit(rows):
            model = make_pipeline(SimpleImputer(strategy='median', keep_empty_features=True),
                                  RandomForestClassifier(n_estimators=100, max_depth=4, min_samples_leaf=2, class_weight='balanced', random_state=42, n_jobs=1))
            model.fit([[r[c] if r[c] is not None else np.nan for c in FEATURES] for r in rows], [int(r['label'] == 'silage') for r in rows])
            return model

        def predict(model, rows, role, fold):
            values = model.predict_proba([[r[c] if r[c] is not None else np.nan for c in FEATURES] for r in rows])[:, list(model.classes_).index(1)]
            for row, p in zip(rows, values):
                predictions.append(dict(field_id=row['field_id'], year=row['year'], p_silage=float(p), predicted_label='silage' if p >= .5 else 'grain', prediction_role=role, fold_id=fold, model_version=VERSION))
            return list(map(float, values))

        for fold in sorted({r['fold_id'] for r in eligible}):
            training = [r for r in eligible if r['fold_id'] != fold]
            testing = [r for r in eligible if r['fold_id'] == fold]
            entry = dict(fold_id=fold, n_train=len(training), n_test=len(testing), train_class_counts={c: sum(r['label'] == c for r in training) for c in ('grain', 'silage')})
            if len({r['label'] for r in training}) < 2:
                entry['reason'] = 'training fold lacks a class; no OOF prediction'
                audit['exclusions'].extend(dict(field_id=r['field_id'], year=r['year'], reasons=[entry['reason']]) for r in testing)
            else:
                assert not {r['field_id'] for r in training} & {r['field_id'] for r in testing}
                p = predict(fit(training), testing, 'oof', fold)
                y = [int(r['label'] == 'silage') for r in testing]
                truth.extend(y)
                probs.extend(p)
                entry['metrics'] = metrics(y, p)
                for r, y_i in zip(testing, y):
                    if r['drop_doy'] is not None:
                        rule_y.append(y_i)
                        rule_p.append(float(r['drop_doy'] <= 258))
            audit['folds'].append(entry)
        if inference and len({r['label'] for r in eligible}) == 2:
            targets = [r for _, r in sorted(features.items()) if r['quality_flag'] in ('usable', 'limited')]
            # Reject unknown years of training fields from OOF already via global field-fold check.
            predict(fit(eligible), targets, 'inference', '')
        notes.append('OOF metrics cover only successfully held-out rows; inspect exclusions and per-fold counts.')
    write_csv(out / 'predictions.csv', HEADER, predictions)
    write_json(out / 'metrics.json', metrics(truth, probs, notes))
    rule = metrics(rule_y, rule_p, ['Fixed rule: drop_doy <= 258 predicts silage; missing drop day abstains.', 'Hard decisions only; Brier is not a calibrated-probability assessment. Same successful OOF cohort, subset with drop_doy.'])
    rule['brier_score'] = None
    write_json(report / 'harvest_rule_metrics.json', rule)
    write_json(report / 'merge_report.json', audit)
    return 2 if audit['errors'] else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root', type=Path, default=Path('data/processed'))
    parser.add_argument('--output', type=Path, default=Path('data/processed/model'))
    parser.add_argument('--report', type=Path, default=Path('reports/c_model'))
    parser.add_argument('--train', action='store_true')
    parser.add_argument('--inference', action='store_true')
    args = parser.parse_args()
    if args.inference and not args.train:
        parser.error('--inference requires --train')
    raise SystemExit(run(args.data_root, args.output, args.report, args.train, args.inference))


if __name__ == '__main__':
    main()
