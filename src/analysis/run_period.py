"""Run the requested annual period without inventing missing-year data."""
import argparse
import csv
import hashlib
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

from analysis import (ContractError, FEATURE_COLUMNS, LABEL_COLUMNS, PREDICTION_COLUMNS,
                      YEARS, load_json, read_csv, read_fields, write_csv, write_json)
from report_results import feature_coverage


def table(path):
    with Path(path).open(newline='', encoding='utf-8') as stream:
        return list(csv.DictReader(stream))


def run(args):
    if args.start_year not in YEARS or args.end_year not in YEARS or args.start_year > args.end_year:
        raise ContractError('invalid requested period')
    years = list(range(args.start_year, args.end_year+1))
    root, out, report = args.input_root, args.output_root, args.report_root
    fields = read_fields(root/'core/fields.geojson')
    labels = read_csv(root/'core/labels.csv', LABEL_COLUMNS, 'labels')
    features = read_csv(root/'satellite/features.csv', FEATURE_COLUMNS, 'features')
    predictions = read_csv(root/'model/predictions.csv', PREDICTION_COLUMNS, 'predictions')
    folds = read_csv(root/'core/validation_folds.csv', ['field_id', 'year', 'fold_id'], 'folds')
    if any(rows is None for rows in [fields, labels, features, predictions, folds]):
        raise ContractError('source handoff files required; an individual year may have no rows')
    provenance = load_json(report/'handoff_validation.json')
    for item in provenance['inputs']:
        source = root/item['path'].removeprefix('data/processed/')
        if hashlib.sha256(source.read_bytes()).hexdigest() != item['sha256']:
            raise ContractError('source changed: validate updated provenance first: '+source.name)
    areas = {r['field_id']: r['area_ha'] for r in fields}
    truth = {(r['field_id'], r['year']): r['label'] == 'silage' for r in labels}
    status = {'requested_years': years, 'prediction_role': args.prediction_role,
              'active_root_year': years[0], 'source_inputs': provenance['inputs'], 'years': [],
              'notes': ['Historical 2021 inputs remain readable but are excluded from the active 2022-2025 window.',
                        'Interface support does not create observations, labels or forecasts.',
                        'Unknown annual cohort areas/coverage are null, never zero or copied from another year.']}
    annual, corrections, comparisons = [], [], []
    for year in years:
        target = out/str(year)/args.prediction_role
        cmd = [sys.executable, str(Path(__file__).with_name('analysis.py')), '--year', str(year),
               '--prediction-role', args.prediction_role, '--cohort', 'labeled',
               '--fields', str(root/'core/fields.geojson'), '--labels', str(root/'core/labels.csv'),
               '--features', str(root/'satellite/features.csv'), '--predictions', str(root/'model/predictions.csv'),
               '--folds', str(root/'core/validation_folds.csv'), '--review-budget', '3',
               '--seed', '42', '--random-repeats', '200', '--output-root', str(target)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode:
            raise ContractError(result.stderr.strip())
        summary = load_json(target/'summary.json')
        write_json(target/'feature_coverage.json', feature_coverage(fields, features, summary))
        unresolved = summary['scope'].get('cohort_status') == 'pending_no_annual_cohort'
        yr_labels = [r for r in labels if r['year'] == year]
        yr_features = [r for r in features if r['year'] == year]
        yr_preds = [r for r in predictions if r['year'] == year and
                    r['prediction_role'] == args.prediction_role and r['p_silage'] is not None]
        yr_folds = [r for r in folds if r['year'] == year]
        blockers = [reason for missing, reason in [
            (unresolved, 'missing_annual_target_cohort'), (not yr_features, 'missing_features_for_year'),
            (not yr_preds, 'missing_predictions_for_year'),
            (not yr_labels or not yr_folds, 'missing_labels_and_folds_for_oof_evaluation')] if missing]
        ids = summary['scope']['field_ids']
        status['years'].append({'year': year, 'status': summary['status'],
            'n_selected_fields': None if unresolved else len(ids),
            'annual_label_rows_in_source': len(yr_labels), 'feature_rows_in_source': len(yr_features),
            'real_prediction_rows_in_source': len(yr_preds), 'blockers': blockers})
        true_area = math.fsum(areas[key] for key in ids if truth[(key, year)]) if not unresolved else None
        estimated = summary['expected_silage_area_ha']
        annual.append({'year': year, 'prediction_role': args.prediction_role, 'status': summary['status'],
            'n_fields': None if unresolved else len(ids), 'selected_area_ha': summary['total_area_ha'],
            'covered_area_ha': summary['covered_area_ha'], 'coverage_fraction': summary['coverage_fraction'],
            'expected_silage_area_ha': estimated, 'expected_grain_area_ha': summary['expected_grain_area_ha'],
            'label_silage_area_ha': true_area,
            'signed_silage_error_ha': estimated-true_area if estimated is not None and true_area is not None else None,
            'blockers': ';'.join(blockers)})
        sim = load_json(target/'review_simulation.json')
        queue = table(target/'review_queue.csv')
        comparisons.append({'year': year, 'prediction_role': args.prediction_role, 'status': sim['status'],
            'budget': 3, 'seed': 42, 'random_repeats': 200, 'n_candidates': None if unresolved else len(queue),
            **{key: sim[key] for key in ['initial_absolute_error_ha', 'heuristic_absolute_error_ha',
              'random_absolute_error_median_ha', 'random_absolute_error_min_ha', 'random_absolute_error_max_ha']},
            'change_in_absolute_error_ha': sim['heuristic_absolute_error_ha']-sim['initial_absolute_error_ha']
                if sim['status'] == 'evaluated' else None})
        if sim['status'] == 'evaluated':
            probs = {r['field_id']: r['p_silage'] for r in yr_preds}
            for row in queue[:3]:
                key = row['field_id']
                corrections.append({'year': year, 'prediction_role': args.prediction_role, 'rank': row['rank'],
                    'field_id': key, 'area_ha': areas[key], 'p_silage': probs[key],
                    'true_label': 'silage' if truth[(key, year)] else 'grain',
                    'predicted_silage_area_ha': areas[key]*probs[key],
                    'revealed_silage_area_ha': areas[key]*truth[(key, year)],
                    'correction_ha': areas[key]*(truth[(key, year)]-probs[key])})
    status['status'] = 'computed' if all(r['status'] == 'computed' for r in status['years']) else 'partial_pending'
    write_json(out/'period_status.json', status)
    write_csv(out/'annual_data_summary.csv', annual[0].keys(), annual)
    changes = []
    for a, b in zip(annual, annual[1:]):
        ready = a['expected_silage_area_ha'] is not None and b['expected_silage_area_ha'] is not None
        ra = a['expected_silage_area_ha']/a['selected_area_ha'] if ready else None
        rb = b['expected_silage_area_ha']/b['selected_area_ha'] if ready else None
        changes.append({'from_year': a['year'], 'to_year': b['year'], 'status': 'computed' if ready else 'pending',
            'expected_silage_change_ha': b['expected_silage_area_ha']-a['expected_silage_area_ha'] if ready else None,
            'selected_area_component_ha': (b['selected_area_ha']-a['selected_area_ha'])*ra if ready else None,
            'weighted_probability_share_component_ha': b['selected_area_ha']*(rb-ra) if ready else None,
            'interpretation': 'Different selected cohorts; not causal land-use change' if ready else
                              'Missing annual estimate; no interpolation/extrapolation'})
    write_csv(out/'year_change_decomposition.csv', changes[0].keys() if changes else ['from_year','to_year','status'], changes)
    cols = 'year prediction_role rank field_id area_ha p_silage true_label predicted_silage_area_ha revealed_silage_area_ha correction_ha'.split()
    write_csv(out/'review_field_corrections.csv', cols, corrections)
    write_csv(report/'review_comparison.csv', comparisons[0].keys(), comparisons)
    for name in ['summary.json','merge_audit.json','feature_coverage.json','review_queue.csv','data_needed.csv','review_simulation.json']:
        shutil.copyfile(out/str(years[0])/args.prediction_role/name, out/name)
    archive = report/'archive'
    archive.mkdir(parents=True, exist_ok=True)
    historical = archive/'barc_2021_2023_all_data_summary_zh.md'
    if (report/'all_data_summary_zh.md').exists() and not historical.exists():
        shutil.copyfile(report/'all_data_summary_zh.md', historical)
    lines = [f'# CornHub 当前分析范围：{years[0]}–{years[-1]}', '',
             '按用户指令扩大 D 输出窗口；不修改 A/B/C、模型或前端，不伪造新年度数据。', '',
             '| 年份 | 状态 | 样本数 | 样本面积 ha | 预期青贮 ha | 预期籽粒 ha | 覆盖率 |',
             '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
    for row in annual:
        vals = [row[k] for k in ['year','status','n_fields','selected_area_ha',
                                'expected_silage_area_ha','expected_grain_area_ha','coverage_fraction']]
        lines.append('| '+' | '.join('null（待数据）' if v is None else str(v) for v in vals)+' |')
    lines += ['', '空年度目标集合的面积和覆盖率为 null，不是零。100% 只代表选定样本。',
              '年份/角色分别统计；相邻年份缺项时不计算趋势，不借用旧年份概率。',
              '核查预算 3 块、种子 42、随机重复 200 次；负结果不删除。概率未校准，经济结果 null。',
              '2021/oof 和历史中文报告保留；根目录为明确选定的首年 labeled 队列，不改 A 的 smoke sample。', '',
              '## 待补输入']
    for row in status['years']:
        if row['blockers']:
            lines.append(f"- {row['year']}："+'；'.join(row['blockers']))
    lines += ['', '来源及每年状态见 period_status.json；旧 83 块边界和加州 CDL 不代表新增年度 BARC 玉米范围。']
    (report/'all_data_summary_zh.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    return status


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--start-year', type=int, default=2022)
    p.add_argument('--end-year', type=int, default=2025)
    p.add_argument('--prediction-role', required=True, choices=['oof'])
    p.add_argument('--input-root', type=Path, default=Path('data/processed'))
    p.add_argument('--output-root', type=Path, default=Path('data/processed/analysis'))
    p.add_argument('--report-root', type=Path, default=Path('reports/d_analysis'))
    args = p.parse_args()
    try:
        result = run(args)
        print(json.dumps({'status': result['status'], 'years': result['years']}))
    except (ContractError, OSError, ValueError, KeyError) as exc:
        p.exit(2, f'period analysis failed: {exc}\n')


if __name__ == '__main__':
    main()
