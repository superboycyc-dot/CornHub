"""Process every A-owned field/year label via native-grid provider-side crops."""
import argparse,csv,hashlib,math
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import requests
from shapely.geometry import shape
from .contracts import load_json,write_json,write_csv,TIMESERIES_COLUMNS,FEATURE_COLUMNS
from .features import summarize
from .pc_fallback import observe_crop,PC
from .pipeline import utc_now,plot_observations

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--core',required=True);p.add_argument('--workers',type=int,default=6)
    args=p.parse_args()
    if not 1<=args.workers<=6:p.error('workers must be 1..6')
    root=Path(__file__).resolve().parents[2];core=Path(args.core)
    output=root/'data/processed/satellite';reports=root/'reports/b_satellite'
    fields=load_json(core/'fields.geojson');byid={f['properties']['field_id']:f for f in fields['features']}
    with (core/'labels.csv').open() as f:labels=list(csv.DictReader(f))
    keys=[(r['field_id'],int(r['year'])) for r in labels]
    if len(keys)!=len(set(keys)) or any(fid not in byid or y not in [2021,2022,2023] for fid,y in keys):raise ValueError('Invalid A keys')
    labels.sort(key=lambda r:(r['field_id'],int(r['year'])))
    samples={(r['field_id'],int(r['year'])):dict(field_id=r['field_id'],year=int(r['year']),window_start=r['year']+'-04-01',window_end_exclusive=r['year']+'-12-01',selection_rule='Existing A label key; full A list, no B-created IDs or labels',source_dataset_id=byid[r['field_id']]['properties']['source_dataset_id']) for r in labels}
    bounds=[shape(byid[fid]['geometry']).bounds for fid,y in keys]
    bbox=[min(b[0] for b in bounds),min(b[1] for b in bounds),max(b[2] for b in bounds),max(b[3] for b in bounds)]
    inventories={};errors=[]
    for year in sorted({y for fid,y in keys}):
        target=reports/f'pc_batch_inventory_{year}.json.gz'
        receipt=reports/f'pc_batch_search_{year}.json'
        query=dict(collections=['sentinel-2-l2a'],bbox=bbox,datetime=f'{year}-04-01T00:00:00Z/{year}-11-30T23:59:59Z',limit=500)
        try:
            if target.exists() and load_json(receipt)['query']==query:inventory=load_json(target)
            else:
                response=requests.post(PC+'/api/stac/v1/search',json=query,timeout=(15,75));response.raise_for_status();inventory=response.json()
                if any(link['rel']=='next' for link in inventory.get('links',[])):raise ValueError('Pagination required, refusing silent truncation')
                write_json(target,inventory);write_json(receipt,dict(query=query,source_url=PC+'/api/stac/v1/search',retrieved_at_utc=utc_now()))
            inventories[year]=inventory['features'];print('Catalog',year,len(inventory['features']),flush=True)
        except Exception as e:
            inventories[year]=[];errors.append(dict(year=year,stage='catalog',error_type=type(e).__name__))
    rows=[];provenance=[];counts={k:0 for k in keys};success={k:0 for k in keys};failures={k:[] for k in keys}
    cache=reports/'.cache/pc_crop'
    jobs=[]
    for key in sorted(keys):
        fid,year=key;geometry=byid[fid]['geometry'];g=shape(geometry)
        for item in inventories[year]:
            if shape(item['geometry']).intersects(g):jobs.append((key,item,geometry));counts[key]+=1
    print('Batch field-years',len(keys),'scene jobs',len(jobs),flush=True)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures={pool.submit(observe_crop,item,geo,cache):(key,item) for key,item,geo in jobs}
        for n,future in enumerate(as_completed(futures),1):
            key,item=futures[future];fid,year=key
            try:
                receipt=future.result();day=item['properties']['datetime'][:10]
                if not f'{year}-04-01'<=day<f'{year}-12-01':raise ValueError('Out-of-window scene')
                success[key]+=1
                rows.append(dict(field_id=fid,year=year,date=day,sensor='sentinel2_l2a',scene_id=item['id'],ndvi=receipt['stats']['ndvi'],valid_pixel_fraction=receipt['stats']['valid_pixel_fraction'],source_dataset_id='planetary_computer_sentinel2_l2a'))
                provenance.append(dict(field_id=fid,year=year,date=day,**receipt))
            except Exception as e:failures[key].append(dict(scene_id=item['id'],error_type=type(e).__name__,message=str(e)[:160]))
            if n%25==0 or n==len(jobs):print('Scenes',n,'/',len(jobs),'success',len(rows),flush=True)
    rows.sort(key=lambda r:(r['field_id'],r['year'],r['date'],r['scene_id']))
    features=[];summary=[];plots=reports/'field_timeseries';plots.mkdir(exist_ok=True)
    for key in sorted(keys):
        fid,year=key;sample=samples[key];observations=[r for r in rows if (r['field_id'],r['year'])==key]
        feature,daily=summarize(observations,sample,'catalog_failed' if not inventories[year] else 'no_successful_scene_reads')
        if failures[key]:feature['missing_reason']=';'.join(filter(None,[feature['missing_reason'],'scene_read_failures_see_report']))
        features.append(feature)
        summary.append(dict(field_id=fid,year=year,scene_count=counts[key],processed_scene_count=success[key],failed_scene_count=len(failures[key]),valid_obs_count=feature['valid_obs_count'],max_gap_days=feature['max_gap_days'],quality_flag=feature['quality_flag'],missing_reason=feature['missing_reason']))
        if feature['valid_obs_count']:plot_observations(observations,daily,sample,plots/f'{fid}_{year}.png')
    write_csv(output/'timeseries.csv',TIMESERIES_COLUMNS,rows);write_csv(output/'features.csv',FEATURE_COLUMNS,features)
    write_csv(reports/'field_year_coverage.csv',list(summary[0]),summary)
    write_json(reports/'pc_batch_provenance.json.gz',sorted(provenance,key=lambda r:(r['field_id'],r['year'],r['date'],r['scene_id'])))
    report=dict(status='partial' if errors or any(failures.values()) else 'completed',finished_at_utc=utc_now(),field_year_count=len(keys),unique_field_count=len({fid for fid,y in keys}),feature_rows=len(features),timeseries_rows=len(rows),field_years_with_observations=sum(f['valid_obs_count']>0 for f in features),scene_jobs=len(jobs),successful_scene_reads=len(rows),cache_hits=sum(r['cache_hit'] for r in provenance),quality_counts={q:sum(f['quality_flag']==q for f in features) for q in ['no_data','insufficient','limited','usable']},catalog_errors=errors,scene_errors=[dict(field_id=fid,year=y,**e) for (fid,y),es in failures.items() for e in es],core_input_sha256={name:hashlib.sha256((core/name).read_bytes()).hexdigest() for name in ['fields.geojson','labels.csv','smoke_sample.json']})
    write_json(reports/'pc_batch_report.json',report);write_json(reports/'batch_report.json',report)
    print('FINAL',report['status'],'keys',len(features),'rows',len(rows),'quality',report['quality_counts'],flush=True)
    return 2 if report['status']=='partial' else 0
if __name__=='__main__':raise SystemExit(main())
