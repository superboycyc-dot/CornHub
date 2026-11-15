"""Summarize pinned CornHub data and explain arithmetic changes, without causal claims."""
import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

from analysis import (FEATURE_COLUMNS, LABEL_COLUMNS, PREDICTION_COLUMNS, ContractError,
                      load_json, read_csv, read_fields, write_csv, write_json)


def plain_csv(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input-root', type=Path, default=Path('data/processed'))
    p.add_argument('--aux-root', type=Path, default=Path('.'))
    p.add_argument('--analysis-root', type=Path, default=Path('data/processed/analysis'))
    p.add_argument('--report-root', type=Path, default=Path('reports/d_analysis'))
    p.add_argument('--main-ref', required=True)
    args = p.parse_args()
    try:
        root, aux, out, report = args.input_root, args.aux_root, args.analysis_root, args.report_root
        if (out/'period_status.json').exists():
            raise ContractError('Active period outputs must use run_period.py; this historical-source summarizer must not overwrite the requested period')
        fields = read_fields(root/'core/fields.geojson')
        labels = read_csv(root/'core/labels.csv', LABEL_COLUMNS, 'labels')
        features = read_csv(root/'satellite/features.csv', FEATURE_COLUMNS, 'features')
        predictions = read_csv(root/'model/predictions.csv', PREDICTION_COLUMNS, 'predictions')
        if any(value is None for value in [fields, labels, features, predictions]):
            raise ContractError('all real A/B/C inputs required')
        audit = load_json(report/'handoff_validation.json')
        refs = {kind: next(r['commit'] for r in audit['inputs'] if r['path'].endswith(name))
                for kind, name in [('A', 'fields.geojson'), ('B', 'features.csv'), ('C', 'predictions.csv')]}
        sources = []
        def context(path, ref, is_csv=False):
            file = aux/path
            data = file.read_bytes()
            sources.append({'path': path, 'commit': ref, 'sha256': hashlib.sha256(data).hexdigest(),
                'git_blob_sha': hashlib.sha1(f'blob {len(data)}\0'.encode()+data).hexdigest(),
                'url': f'https://github.com/superboycyc-dot/CornHub/blob/{ref}/{path}'})
            return plain_csv(file) if is_csv else load_json(file)
        metrics = context('data/processed/model/metrics.json', refs['C'])
        rule = context('reports/c_model/harvest_rule_metrics.json', refs['C'])
        batch = context('reports/b_satellite/batch_report.json', refs['B'])
        timeseries = context('data/processed/satellite/timeseries.csv', refs['B'], True)
        cdl = context('data/usda_nass_cdl/california/manifest.json', args.main_ref)
        benchmarks = context('data/processed/usda_nass/corn_state_benchmarks_2025.csv', args.main_ref, True)
        quickstats = context('data/processed/usda_nass/california_corn_acreage_annual_reference_2012_2025.csv', args.main_ref, True)
        areas = {r['field_id']: r['area_ha'] for r in fields}
        truth = {(r['field_id'], r['year']): r['label'] for r in labels}
        ps = {(r['field_id'], r['year'], r['prediction_role']): r['p_silage'] for r in predictions}
        annual, corrections, changes = [], [], []
        summaries, sims, quality = {}, {}, {}
        for year in sorted({r['year'] for r in labels}):
            folder = out/str(year)/'oof'
            summary = summaries[year] = load_json(folder/'summary.json')
            sim = sims[year] = load_json(folder/'review_simulation.json')
            cov = quality[year] = load_json(folder/'feature_coverage.json')
            ids = summary['scope']['field_ids']
            if summary['prediction_role'] != 'oof' or any((key, year) not in truth for key in ids):
                raise ContractError('summary must use the real labeled OOF cohort')
            total = math.fsum(areas[key] for key in ids)
            predicted = math.fsum(areas[key]*ps[(key, year, 'oof')] for key in ids)
            true_area = math.fsum(areas[key] for key in ids if truth[(key, year)] == 'silage')
            if not math.isclose(predicted, summary['expected_silage_area_ha'], abs_tol=1e-10):
                raise ContractError('published summary differs from source predictions')
            inference = math.fsum(areas[key]*ps[(key, year, 'inference')] for key in ids)
            counts = Counter(truth[(key, year)] for key in ids)
            annual.append({'year': year, 'prediction_role': 'oof', 'n_fields': len(ids),
                'grain_labels': counts['grain'], 'silage_labels': counts['silage'],
                'selected_area_ha': total, 'expected_silage_area_ha': predicted,
                'expected_grain_area_ha': total-predicted, 'label_silage_area_ha': true_area,
                'label_grain_area_ha': total-true_area, 'predicted_silage_fraction': predicted/total,
                'label_silage_fraction': true_area/total, 'signed_silage_error_ha': predicted-true_area,
                'absolute_silage_error_ha': abs(predicted-true_area),
                'usable_count': cov['quality_counts']['usable'], 'limited_count': cov['quality_counts']['limited'],
                'inference_silage_area_ha_not_for_validation': inference})
            delta = 0.0
            for row in plain_csv(folder/'review_queue.csv')[:sim['budget']]:
                key, prob = row['field_id'], ps[(row['field_id'], year, 'oof')]
                label_value = int(truth[(key, year)] == 'silage')
                correction = areas[key]*(label_value-prob)
                delta += correction
                corrections.append({'year': year, 'prediction_role': 'oof', 'rank': int(row['rank']),
                    'field_id': key, 'area_ha': areas[key], 'p_silage': prob, 'true_label': truth[(key, year)],
                    'predicted_silage_area_ha': areas[key]*prob, 'revealed_silage_area_ha': areas[key]*label_value,
                    'correction_ha': correction})
            if sim['status'] == 'evaluated' and not math.isclose(abs(predicted+delta-true_area), sim['heuristic_absolute_error_ha'], abs_tol=1e-10):
                raise ContractError('field corrections do not explain simulation result')
        for before, after in zip(annual, annual[1:]):
            area_effect = (after['selected_area_ha']-before['selected_area_ha'])*before['predicted_silage_fraction']
            share_effect = after['selected_area_ha']*(after['predicted_silage_fraction']-before['predicted_silage_fraction'])
            actual = after['expected_silage_area_ha']-before['expected_silage_area_ha']
            if not math.isclose(area_effect+share_effect, actual, abs_tol=1e-10):
                raise ContractError('year-change decomposition fails conservation')
            changes.append({'from_year': before['year'], 'to_year': after['year'],
                'expected_silage_change_ha': actual, 'selected_area_component_ha': area_effect,
                'weighted_probability_share_component_ha': share_effect,
                'interpretation': 'Arithmetic decomposition of different selected cohorts; not a causal land-use trend'})
        inventory = {'scope': 'BARC A/B/C/D plus separate California/US reference files', 'refs': refs,
            'reference_main_ref': args.main_ref, 'boundary_fields': len(fields),
            'static_boundary_area_ha_not_annual_corn': math.fsum(areas.values()),
            'label_rows': len(labels), 'unique_labeled_fields': len({r['field_id'] for r in labels}),
            'feature_rows': len(features), 'quality_counts': dict(Counter(r['quality_flag'] for r in features)),
            'timeseries_rows': len(timeseries), 'distinct_scene_ids': len({r['scene_id'] for r in timeseries}),
            'prediction_roles': dict(Counter(r['prediction_role'] for r in predictions)),
            'quickstats_rows': len(quickstats), 'quickstats_suppressed_D': sum(r['value'].strip() == '(D)' for r in quickstats),
            'cdl_years': [r['year'] for r in cdl['files']],
            'cdl_archive_size_bytes': sum(r['size_bytes'] for r in cdl['files']),
            'notes': ['Scene rows repeat a scene across fields; rows are not distinct images.',
                      'All years/roles/regions and reference products remain separate.']}
        text = '# CornHub 全部数据汇总与变化解释\n\n'
        text += '结论：当前已完成马里兰州 BARC 2021–2023 年真实数据链路。年度面积差异首先涉及不同的有标签样本集合，不能当作地区种植趋势；核查也不保证总量误差下降。概率未校准，经济结果仍为空。\n\n'
        text += '## 1. 数据清单与口径\n\n| 数据 | 数量/范围 | 用途和限制 |\n| --- | --- | --- |\n'
        text += f"| A 边界 | {len(fields)} 块，静态面积 {inventory['static_boundary_area_ha_not_annual_corn']:.5f} ha | 不代表每年全部种玉米；面积沿用 A 投影计算 |\n"
        text += f"| A 标签 | {len(labels)} 个田块年度、{inventory['unique_labeled_fields']} 块独立田、5 个农场 | grain 32 / silage 12；同田跨年重复出现，空白标签不是 grain |\n"
        text += f"| B 特征 | {len(features)} 行；limited 18 / usable 26 | 与标签键全部匹配；质量不是模型正确率 |\n"
        text += f"| B 卫星时序 | {len(timeseries)} 条田块—场景记录、{inventory['distinct_scene_ids']} 个不同 scene_id | Sentinel-2 L2A；同一影像可对应多块田，不能称为 4524 张独立影像 |\n"
        text += '| C 预测 | 44 OOF + 44 inference | 下文验证、核查只用 OOF，不混入训练样本推断 |\n| D 分析 | 共同样本 + 3 个年度样本 | 年份分别保存，不跨年相加；经济结果 null |\n'
        text += f"| USDA Quick Stats 参考表 | 2012–2025，{len(quickstats)} 行，含 {inventory['quickstats_suppressed_D']} 条 (D) | 混合州/县、Survey/Census；保密值不能当零，不能直接拼接成同口径州级趋势 |\n"
        text += '| USDA 2025 报告摘录 | 美国/加州，2 行 | 总量/单位参考，不是田块标签或当前供给 |\n'
        text += f"| 加州 CDL | 2022–2025，4 个 ZIP，合计 {inventory['cdl_archive_size_bytes']/1e9:.6f} GB | 按现有清单记录为 30 m 缓存产品；不是 S/G 标签，也不是 NDVI 时序 |\n\n"
        text += '2026 CDL 在现有清单中为未找到；本报告沿用该检索记录，没有重新验证最新官方发布。原始报告、CDL、BARC 原件、历史 partial 和前端发布副本不是额外独立样本，不重复累计。主线当前没有加州田块级 S/G 验证结果。\n\n'
        text += '## 2. 年度样本、真实标签面积和 OOF 预期面积\n\n| 年份 | grain/silage 标签数 | 选定面积 ha | OOF 预期青贮 ha | OOF 预期籽粒 ha | 标签青贮面积 ha | 预期青贮占比 | 标签青贮占比 |\n| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |\n'
        for r in annual:
            text += f"| {r['year']} | {r['grain_labels']}/{r['silage_labels']} | {r['selected_area_ha']:.5f} | {r['expected_silage_area_ha']:.5f} | {r['expected_grain_area_ha']:.5f} | {r['label_silage_area_ha']:.5f} | {r['predicted_silage_fraction']:.2%} | {r['label_silage_fraction']:.2%} |\n"
        text += '\n“标签面积”是用真实用途标签计算的样本参考值，只用于评估，不是预测。所有年度的预测覆盖率均为所选样本的 100%，不是全部 83 块、全 BARC 或加州的覆盖率。每年恰有 4 条青贮标签是数据事实；为何如此，需要采样/标注说明，不能据此认定随机抽样或真实比例固定。\n\n'
        text += '## 3. 面积为何变化：交付状态和年度差异必须分开\n\n过去 pending→现在 computed，是 C 真实预测到齐后的计算状态变化；原来 130.11/44.65/123.09 ha 是样本边界面积，不是先前的青贮预测，也不表示土地面积突然增减。\n\n年度之间，样本数量为 18→7→19，田块集合并不相同。公式为预期青贮面积 S=T×r，其中 T 是所选面积，r 是面积加权青贮概率。以下仅为按“先面积、后占比”顺序的算术分解，不能解释真实因果：\n\n| 年份变化 | 青贮估计变化 ha | 样本面积分量 ha | 加权概率占比分量 ha |\n| --- | ---: | ---: | ---: |\n'
        for r in changes:
            text += f"| {r['from_year']}→{r['to_year']} | {r['expected_silage_change_ha']:+.5f} | {r['selected_area_component_ha']:+.5f} | {r['weighted_probability_share_component_ha']:+.5f} |\n"
        text += '\n计算：ΔS=(T₂−T₁)r₁+T₂(r₂−r₁)。2022 绝对面积较小但预期青贮占比较高，所以不能只看绝对面积说青贮种植减少。没有完整年度种植范围、天气/管理和地面收获证据，不能把这些差异归因为气候、播期、轮作或市场价格。\n\n'
        text += '## 4. 卫星观测和质量为何不同\n\n| 年份 | 田块—场景记录 | 不同 scene_id | 有效日数范围/田 | 最长缺口范围（天） | limited/usable |\n| --- | ---: | ---: | --- | --- | --- |\n'
        for r in annual:
            y = r['year']; ts = [v for v in timeseries if int(v['year']) == y]; q = quality[y]
            text += f"| {y} | {len(ts)} | {len({v['scene_id'] for v in ts})} | {q['valid_day_count_min']}–{q['valid_day_count_max']} | {q['max_gap_days_min']}–{q['max_gap_days_max']} | {r['limited_count']}/{r['usable_count']} |\n"
        text += '\n2021 虽有 21–52 个有效日，但最长缺口都超过合同的 30 天门槛，因此 18 行全部 limited；2022/2023 同时满足有效日数和缺口规则，所以可为 usable。质量规则没有放宽。较多场景记录也受年份、田块数和重复覆盖影响，不等于更高分类准确率；缺口的具体物理原因仍需逐景质量/掩膜证据，不能笼统认定全部由云造成。\n\n2021 的 OOF 青贮总量绝对误差仅约 1.71 ha，也不能说明 limited 预测可靠：总量误差可能相互抵消。早春峰值或骤降只是合同定义的全窗口特征，不等于已确认收获日；没有地面事件标签就不能直接称为收割证据。\n\n'
        text += '## 5. 模型结果和可能的限制\n\n| 指标 | Random Forest OOF | 固定收获时间规则 |\n| --- | ---: | ---: |\n'
        for key, title in [('macro_f1', 'Macro F1'), ('silage_precision', '青贮 Precision'), ('silage_recall', '青贮 Recall'), ('brier_score', 'Brier')]:
            a, b = metrics[key], rule[key]
            text += f"| {title} | {a:.6f} | {b:.6f}"+' |\n' if b is not None else f"| {title} | {a:.6f} | null（无概率输出） |\n"
        text += '\nRF：32 条 grain 中判对 30、误判 2；12 条 silage 中判对 4、漏掉 8。固定规则虽然识别 11/12 条 silage，但把 24/32 条 grain 错判为 silage。高 recall 不能单独代表整体更好。\n\n按 C 记录，fold 2 的训练部分只有 1 条青贮，却承担 11 条青贮测试；其余部分测试折没有青贮，单折指标可能无定义。加上 34 块独立田、5 个农场、概率未校准，这些是已知限制；它们可能影响泛化和少数类学习，但不能据此证明某次误判的具体原因。D 未改模型、重训、调参或更换划分。\n\n'
        text += '### OOF 与 inference 为什么不能混用\n\n| 年份 | OOF 预期青贮 ha（验证用） | inference 预期青贮 ha（非验证展示） |\n| --- | ---: | ---: |\n'
        for r in annual:
            text += f"| {r['year']} | {r['expected_silage_area_ha']:.5f} | {r['inference_silage_area_ha_not_for_validation']:.5f} |\n"
        text += '\nOOF 该行所属农场被留出；inference 来自包含这些标签的全量模型。训练样本不同可导致概率不同，不能挑更接近真值的 inference 冒充验证，也不能把两种角色相加。\n\n'
        text += '## 6. 人工核查为何有时变差\n\n固定每年预算 3 块，种子 42，随机重复 200 次；同一候选池、同一 OOF 样本，假设核查完美揭示整田标签。2021 没有 usable 候选，模拟 pending；可以描述其已有标签总量误差，但不能声称完成了 3 块核查。\n\n| 年份 | 初始绝对误差 ha | 排序核查后 ha | 随机中位数 ha | 随机最小–最大 ha |\n| --- | ---: | ---: | ---: | --- |\n'
        for y, s in sims.items():
            if s['status'] != 'evaluated':
                text += f'| {y} | null（模拟未执行） | null | null | null |\n'
            else:
                text += f"| {y} | {s['initial_absolute_error_ha']:.5f} | {s['heuristic_absolute_error_ha']:.5f} | {s['random_absolute_error_median_ha']:.5f} | {s['random_absolute_error_min_ha']:.5f}–{s['random_absolute_error_max_ha']:.5f} |\n"
        text += '\n逐田修正量 = A×(真实青贮标签−p)，正数上调、负数下调。排序只使用面积和概率，不使用真实标签；标签只在模拟揭示后用于修正。\n\n| 年份 | 核查田块 | 真实标签 | 青贮概率 | 修正量 ha |\n| --- | --- | --- | ---: | ---: |\n'
        for r in corrections:
            text += f"| {r['year']} | {r['field_id']} | {r['true_label']} | {r['p_silage']:.6f} | {r['correction_ha']:+.6f} |\n"
        text += '\n2022：原先少估 11.46035 ha，三田合计上调 8.84241 ha，剩余少估 2.61794 ha。2023：原先少估 3.05772 ha，三田合计上调 7.06703 ha，变为多估 4.00931 ha。后者是可由实际数值验证的“误差抵消被移除/总量跨过真值”，不是标签改错。正确修正个别田块，不保证有限预算下的总量误差单调下降。两年排序结果低于随机中位数也不是显著性检验或普遍有效性的证明，不按结果改门槛和预算。\n\n'
        text += '## 7. USDA/CDL 参考资料与经济空缺\n\n现有两份加州 2025 年统计的口径/来源批次存在差异（下表统一为英亩）：\n\n| 来源 | 全用途种植面积 | 籽粒收获面积 | 青贮收获面积 |\n| --- | ---: | ---: | ---: |\n| January 2026 Crop Production 摘录 | 420,000 | 50,000 | 365,000 |\n| 现有 Quick Stats 州级记录 | 450,000 | 75,000 | 370,000 |\n\n这些是不同来源快照的现存数值，尚未核实具体差异来自定义、统计批次还是后续修订，不能擅自认定哪份“更新正确”，也不平均或静默替换。更不能拿加州 2025 年总量去标定马里兰 BARC 2021–2023 年有标签小样本。Quick Stats 中 2012/2017/2022 使用县/Census，其余多为州/Survey；(D) 保持未知，不作零值或缺县补零。CDL 能辅助确定玉米区域，不能区分最终青贮/籽粒用途。\n\n报告摘录的加州籽粒单产为 173 bushels/acre、青贮为 27 tons/acre；产品部分、含水量和单位不同，不能直接比大小或移作 BARC 固定单产。缺少本地对应年份的单产、价格、价格口径、含水基准、转换和来源；经济参数及结果仍为 null，不把总产值叫利润。\n\n'
        text += '补充列出 2025 报告两地区全部数值，保留原表单位：\n\n| 地区 | 全用途种植（千英亩） | 籽粒收获（千英亩） | 籽粒单产（蒲式耳/英亩） | 籽粒产量（千蒲式耳） |\n| --- | ---: | ---: | ---: | ---: |\n'
        for r in benchmarks:
            text += '| '+' | '.join(r[k] for k in ['geography', 'corn_planted_all_purpose_thousand_acres', 'corn_harvested_for_grain_thousand_acres', 'corn_grain_yield_bushels_per_acre', 'corn_grain_production_thousand_bushels'])+' |\n'
        text += '\n| 地区 | 青贮收获（千英亩） | 青贮单产（吨/英亩） | 青贮产量（千吨） |\n| --- | ---: | ---: | ---: |\n'
        for r in benchmarks:
            text += '| '+' | '.join(r[k] for k in ['geography', 'corn_harvested_for_silage_thousand_acres', 'corn_silage_yield_tons_per_acre', 'corn_silage_production_thousand_tons'])+' |\n'
        text += '\n'
        text += '## 8. 可以确认、仍不能解释的事项\n\n- 可确认：交付到齐导致 pending→computed；年度样本范围不同；2021 的质量门槛由缺口触发；2023 总量误差增加可逐田分解。\n- 仍待核实：每年恰好 4 条青贮标签的采样原因、具体观测缺口的物理原因、每次模型误判的农学原因、USDA 两份统计差异的准确成因。\n- 不能宣称：加州泛化、完整地区面积趋势、概率已可靠校准、核查必然改善、真实地面核查效果或经济利润。\n\n'
        text += '## 9. 来源、运行和文件\n\n'
        for role, ref in refs.items():
            text += f'- {role} 输入固定提交：`{ref}`。\n'
        text += f'- D 分析来源见 handoff_validation.json；参考资料 main 提交：`{args.main_ref}`。\n'
        text += '- 全部本次附加输入的来源、SHA-256 和 Git blob SHA 见 summary_input_manifest.json；没有重跑影像处理或模型训练。\n\n'
        text += '复现：先按 README 的真实接口生成 OOF 年度结果和 feature_coverage.json，再运行：\n\n```sh\npython3 src/analysis/summarize_data.py --main-ref '+args.main_ref+'\n```\n\n实际运行通过 --input-root/--aux-root 指向固定提交的只读暂存文件；默认路径适用于上游全部集成后的仓库。输出：本中文报告、data_inventory.json、summary_input_manifest.json，以及 analysis 下 annual_data_summary.csv、review_field_corrections.csv、year_change_decomposition.csv。主线只改 D 目录，不改模型/前端，不把参考数据当田块真值。\n'
        report.mkdir(parents=True, exist_ok=True)
        write_json(report/'data_inventory.json', inventory)
        write_json(report/'summary_input_manifest.json', {'sources': sources, 'core_inputs': audit['inputs']})
        write_csv(out/'annual_data_summary.csv', annual[0].keys(), annual)
        write_csv(out/'review_field_corrections.csv', corrections[0].keys(), corrections)
        write_csv(out/'year_change_decomposition.csv', changes[0].keys(), changes)
        (report/'all_data_summary_zh.md').write_text(text, encoding='utf-8')
        print(json.dumps({'annual_rows': len(annual), 'review_correction_rows': len(corrections),
                          'year_change_rows': len(changes), 'report': str(report/'all_data_summary_zh.md')}, ensure_ascii=False))
    except (ContractError, OSError, ValueError, KeyError) as exc:
        p.exit(2, f'data summary failed: {exc}\n')


if __name__ == '__main__':
    main()
