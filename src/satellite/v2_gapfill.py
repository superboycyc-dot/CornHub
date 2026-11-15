"""One bounded, label-independent pass for >30-day accepted-NDVI gaps."""
import json,shutil,time
from datetime import date,timedelta
from concurrent.futures import ThreadPoolExecutor,as_completed
import pandas as pd
from shapely.geometry import shape
from global_v2 import OUT,REPORT,write_json,write_csv
from v2_acquire import CACHE,VERSION,CAT,catalog,calibration,observe,clean,now
from v2_export import TS

def physical(item):
    p=item['properties']['s2:product_uri'].split('_');return (p[0],p[2],p[5])
def main():
    start=time.time();policy=dict(version='quality_gapfill_v1',window='[Apr1,Dec1)',criterion='geometrically observable field with accepted NDVI gap strictly >30 days including boundaries',candidate_dates='middle third of each long gap',ranking='largest true footprint overlap;lowest catalog cloud;closest gap midpoint;scene_id',budget='one unread physical product per long gap;one pass only',label_usage='none;no label file read',local_acceptance='unchanged v2 pixel/SCL/valid fraction rule')
    write_json(REPORT/'gapfill_policy.json',policy)
    for name in ['coverage_by_region_label.csv','storage_report.json']:
        target=REPORT/('initial_'+name)
        if not target.exists():shutil.copyfile(REPORT/name,target)
    target=REPORT/'initial_coverage.csv'
    if not target.exists():shutil.copyfile(OUT/'coverage.csv',target)
    t=pd.read_csv(OUT/'timeseries.csv');coverage=pd.read_csv(OUT/'coverage.csv');fields=json.loads((REPORT/'selected_fields.geojson').read_text())['features'];byid={f['properties']['entity_id']:f for f in fields}
    manifest=json.loads((REPORT/'scene_manifest.json').read_text());existing={x['scene_id']:x for x in manifest['scenes']};jobs=[];selection=[]
    locked=pd.read_csv(REPORT/'gapfill_selection.csv').to_dict('records') if (REPORT/'gapfill_selection.csv').exists() else None
    for row in coverage.to_dict('records'):
        if row['geometric_status']!='observable_geometry' or row['max_gap_days']<=30:continue
        eid=row['entity_id'];year=int(row['year']);f=byid[eid];obs=t[t.entity_id==eid];good=obs[(obs.ndvi_valid_fraction>=.5)&obs.ndvi.notna()]
        days=sorted({date.fromisoformat(d) for d in good.date});bounds=[date(year,4,1)]+days+[date(year,12,1)]
        items=catalog(f)['features'];used={physical({'properties':{'s2:product_uri':existing[s]['product_id']}}) for s in obs.scene_id}
        for a,b in zip(bounds,bounds[1:]):
            gap=(b-a).days
            if gap<=30:continue
            lo=a+timedelta(days=gap//3);hi=b-timedelta(days=gap//3);mid=a+timedelta(days=gap//2)
            candidates=[i for i in items if lo<=date.fromisoformat(i['properties']['datetime'][:10])<=hi and physical(i) not in used]
            if not candidates:continue
            geometry=shape(f['geometry'])
            item=min(candidates,key=lambda i:(-shape(i['geometry']).intersection(geometry).area/geometry.area,i['properties'].get('eo:cloud_cover',100),abs((date.fromisoformat(i['properties']['datetime'][:10])-mid).days),i['id']))
            used.add(physical(item));jobs.append((item,f));selection.append(dict(entity_id=eid,gap_start=a.isoformat(),gap_end=b.isoformat(),gap_days=gap,scene_id=item['id'],date=item['properties']['datetime'][:10],candidate_count=len(candidates)))
    if locked is not None:
        selection=locked;jobs=[]
        for r in selection:
            f=byid[r['entity_id']];item=next(i for i in catalog(f)['features'] if i['id']==r['scene_id']);jobs.append((item,f))
    elif selection:write_csv(REPORT/'gapfill_selection.csv',selection)
    print('GAPFILL planned',len(jobs),'fields',len({f['properties']['entity_id'] for i,f in jobs}),flush=True)
    items={i['id']:i for i,f in jobs};cal={};errors=[]
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures={pool.submit(calibration,i):sid for sid,i in items.items()}
        for future in as_completed(futures):
            sid=futures[future]
            try:cal[sid]=future.result()
            except Exception as e:errors.append(dict(scene_id=sid,stage='metadata',error_type=type(e).__name__,message=str(e).split('?')[0][:160]))
    results=[]
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures={pool.submit(observe,i,f,cal[i['id']]):(i,f) for i,f in jobs if i['id'] in cal}
        for n,future in enumerate(as_completed(futures),1):
            i,f=futures[future]
            try:results.append(future.result())
            except Exception as e:errors.append(dict(entity_id=f['properties']['entity_id'],scene_id=i['id'],stage='pixels',error_type=type(e).__name__,message=str(e).split('?')[0][:160]))
            if n%20==0 or n==len(futures):print('GAPFILL',n,len(futures),flush=True)
    for sid,i in items.items():
        if sid not in existing:existing[sid]=dict(scene_id=sid,product_id=i['properties'].get('s2:product_uri'),datetime=i['properties']['datetime'],processing_baseline=i['properties'].get('s2:processing_baseline'),crs=i['properties'].get('proj:epsg'),assets={b:{kk:vv for kk,vv in i['assets'][b].items() if kk!='href'}|{'href':clean(i['assets'][b]['href'])} for b in ['B04','B08','B11','SCL','product-metadata']},calibration=cal.get(sid))
    manifest['scenes']=list(existing.values());write_json(REPORT/'scene_manifest.json',manifest)
    plan=pd.read_csv(REPORT/'scene_selection.csv').to_dict('records');keys={(r['entity_id'],r['selected_scene_id']) for r in plan}
    for r in selection:
        if (r['entity_id'],r['scene_id']) not in keys:plan.append(dict(entity_id=r['entity_id'],bin_index=(date.fromisoformat(r['date'])-date(2023,4,1)).days//10,selected_scene_id=r['scene_id'],catalog_candidates=r['candidate_count']))
    write_csv(REPORT/'scene_selection.csv',plan)
    write_json(REPORT/'gapfill_report.json',dict(status='completed' if not errors else 'partial',policy_version=policy['version'],planned_jobs=len(jobs),observed_jobs=sum(r['status']=='observed' for r in results),unique_products=len(items),metadata_success=len(cal),elapsed_seconds=time.time()-start,errors=errors,completed_at_utc=now(),label_file_read=False))
    m=json.loads((REPORT/'input_manifest.json').read_text());m['gapfill_policy']=policy;write_json(REPORT/'input_manifest.json',m)
    print('GAPFILL finished',len(results),'seconds',time.time()-start,flush=True)
if __name__=='__main__':main()
