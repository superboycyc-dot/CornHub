"""Validate real monthly outputs, archive input metadata and build handoff tables."""
import argparse
import csv
import datetime as dt
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import importlib.metadata
import numpy as np
from calculate import BANDS, SCALE, OFFSET, save


def table(path, rows, fields):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore')
        w.writeheader();w.writerows(rows)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cache',type=Path,default=Path('/tmp/cornhub_md_ndmi'))
    p.add_argument('--data',type=Path,default=Path('data/processed/analysis/ndmi'))
    p.add_argument('--report',type=Path,default=Path('reports/d_analysis/ndmi'))
    p.add_argument('--allow-incomplete',action='store_true')
    a=p.parse_args()
    rows=[]; examples=[]; scenes=[]; manifests=[]
    for y in range(2021,2026):
        for m in range(1,13):
            path=a.data/'months'/f'{y}_{m:02}.json'
            if not path.exists():
                if not a.allow_incomplete:raise ValueError(f'Missing monthly result: {y}-{m:02}')
                rows.append({'year':y,'month':m,'status':'pending'})
                continue
            r=json.loads(path.read_text());assert (r['year'],r['month'])==(y,m)
            total,n=r['corn_pixel_count'],r['valid_pixel_count']
            assert 0 <= n <= total and total>0
            assert sum(s['pixels_used'] for s in r['used_scenes'])==n
            assert abs(r['valid_area_fraction']-n/total)<1e-12
            assert abs(r['corn_area_ha']-total*.09)<1e-9
            assert len({s['scene_id'] for s in r['used_scenes']})==len(r['used_scenes'])
            if n:
                assert -1<=r['ndmi_p10']<=r['ndmi_median']<=r['ndmi_p90']<=1
                assert -1<=r['ndmi_mean']<=1
            else:assert r['ndmi_mean'] is None
            if not a.allow_incomplete:assert r['status']=='computed',f"{y}-{m:02}: {r['status']}"
            for e in r['pixel_examples']:
                rho5=e['dn_b5']*SCALE+OFFSET;rho6=e['dn_b6']*SCALE+OFFSET
                assert abs(e['ndmi']-(rho5-rho6)/(rho5+rho6))<1e-7
                assert not e['qa_pixel']&63
                assert not e['qa_radsat']&((1<<4)|(1<<5)|(1<<11))
                examples.append({'year':y,'month':m,**e})
            for s in r['used_scenes']:
                assert int(s['date'][0:4])==y and int(s['date'][5:7])==m
                scenes.append({'year':y,'month':m,**{k:v for k,v in s.items() if k!='assets'},
                    **{k+'_url':s['assets'][k] for k in BANDS}})
            rows.append({**r,'scene_error_count':len(r['scene_errors'])})
            manifests.append({'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    fields=['year','month','status','corn_pixel_count','corn_area_ha','valid_pixel_count','valid_area_ha',
            'valid_area_fraction','ndmi_mean','ndmi_median','ndmi_p10','ndmi_p90','candidate_scenes','used_scene_count','scene_error_count']
    table(a.data/'maryland_corn_ndmi_monthly_2021_2025.csv',rows,fields)
    table(a.data/'pixel_calculation_examples.csv',examples,['year','month','scene_id','row','col','x_epsg5070',
        'y_epsg5070','dn_b5','dn_b6','qa_pixel','qa_radsat','rho_b5','rho_b6','ndmi'])
    table(a.data/'used_scenes.csv',scenes,['year','month','scene_id','date','platform','pixels_used','scene_cloud_cover']+[k+'_url' for k in BANDS])
    inputs=a.data/'inputs';inputs.mkdir(parents=True,exist_ok=True)
    for name in ['grid.json','maryland_boundary.geojson','cdl_year_catalog.json']+[f'corn_{y}.json' for y in range(2021,2026)]:
        if name.endswith('.geojson'):
            (inputs/(name+'.gz')).write_bytes(gzip.compress((a.cache/name).read_bytes(),mtime=0))
            (inputs/name).unlink(missing_ok=True)
        else:shutil.copyfile(a.cache/name,inputs/name)
    candidates=[]
    for y in range(2021,2026):
        for s in json.load(gzip.open(a.cache/f'landsat_{y}.json.gz','rt')):
            candidates.append({'scene_id':s['id'],'datetime':s['properties']['datetime'],
                'platform':s['properties']['platform'],'scene_cloud_cover':s['properties'].get('eo:cloud_cover'),
                **{k+'_url':s['assets'][k]['href'] for k in BANDS}})
    table(inputs/'landsat_candidate_catalog.csv',candidates,['scene_id','datetime','platform','scene_cloud_cover']+[k+'_url' for k in BANDS])
    candidate_path=inputs/'landsat_candidate_catalog.csv'
    candidate_path.with_suffix('.csv.gz').write_bytes(gzip.compress(candidate_path.read_bytes(),mtime=0))
    candidate_path.unlink()
    validation={'validated_at_utc':dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00','Z'),
        'target_months':60,'computed_months':sum(r['status']=='computed' for r in rows),
        'pending_months':sum(r['status']=='pending' for r in rows),
        'months_with_scene_errors':sum(bool(r.get('scene_error_count')) for r in rows),
        'pixel_example_count':len(examples),'used_scene_records':len(scenes),'candidate_scenes':len(candidates),
        'software_versions':{k:importlib.metadata.version(k) for k in ['numpy','rasterio','shapely','pyproj']},
        'source_code_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('src/analysis/ndmi').glob('*.py')},
        'checks':['unique year+month','count and area bounds','scene counts sum to valid pixels',
        'month dates match','percentile ordering and index bounds','raw DN examples reproduce NDMI within 1e-7',
        'example cloud/saturation rejection bits clear'],'monthly_result_sha256':manifests}
    save(a.report/'validation.json',validation)
    lines=['# 实际运行结果：马里兰州玉米区域 NDMI','',
        f"计算完成 {validation['computed_months']}/60 月；待计算 {validation['pending_months']} 月；有场景错误 {validation['months_with_scene_errors']} 月。",'',
        '全部数值是有效像元月度拼接的空间统计，NDMI 无单位。computed 不代表覆盖率 100%。', '',
        '| 年份 | CDL Corn 网格面积 ha | 12个月有效覆盖率范围 |', '| --- | ---: | ---: |']
    for y in range(2021,2026):
        yy=[r for r in rows if r['year']==y and r.get('valid_area_fraction') is not None]
        if yy:lines.append(f"| {y} | {yy[0]['corn_area_ha']:.2f} | {min(r['valid_area_fraction'] for r in yy):.2%}–{max(r['valid_area_fraction'] for r in yy):.2%} |")
    lines += ['', '| 年月 | NDMI 均值 | 中位数 | p10 | p90 | 有效覆盖率 | 状态 |', '| --- | ---: | ---: | ---: | ---: | ---: | --- |']
    for r in rows:
        vals=[f"{r[k]:.5f}" if r.get(k) is not None else 'null' for k in ['ndmi_mean','ndmi_median','ndmi_p10','ndmi_p90']]
        coverage=f"{r['valid_area_fraction']:.2%}" if r.get('valid_area_fraction') is not None else 'null'
        lines.append(f"| {r['year']}-{r['month']:02} | "+' | '.join(vals)+f" | {coverage} | {r['status']} |")
    lines += ['', '## 一个真实像元的计算过程','']
    if examples:
        e=examples[0]
        lines += [f"产品：`{e['scene_id']}`；网格位置 row={e['row']}、col={e['col']}。",'',
            '```text',f"DN_B5={e['dn_b5']}, DN_B6={e['dn_b6']}",
            f"rho_B5={e['dn_b5']}×0.0000275−0.2={e['rho_b5']:.8f}",
            f"rho_B6={e['dn_b6']}×0.0000275−0.2={e['rho_b6']:.8f}",
            f"NDMI=({e['rho_b5']:.8f}−{e['rho_b6']:.8f})/({e['rho_b5']:.8f}+{e['rho_b6']:.8f})={e['ndmi']:.8f}",
            f"QA_PIXEL={e['qa_pixel']}, QA_RADSAT={e['qa_radsat']}",'```', '',
            '其余真实示例及来源坐标见 pixel_calculation_examples.csv。']
    lines += ['', '## 检查与限制','',
        '5 项数值/QA 检查通过；导出程序核查唯一键、面积与覆盖率、场景贡献数、月份、指数范围及真实 DN 示例的公式。逐文件哈希和实际检查见 validation.json。', '',
        '不能只凭曲线把变化归因于干旱或收获：年度玉米区域、源分辨率、月内观测日期、云雪缺测及物候都可能变化。冬季是年度玉米区域的地表状态，非冬季活玉米含水率。', '',
        '本次没有补造 2024/2025 的 BARC 标签或预测，原有分类数据阻塞仍然独立存在。详细步骤、命令和来源见 README.md 及 sources.csv。']
    (a.report/'run_summary_zh.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({k:v for k,v in validation.items() if k not in ['monthly_result_sha256','checks']}))

if __name__=='__main__':main()
