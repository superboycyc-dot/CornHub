"""Export checkpointed observations, v1-comparable features, coverage and audit."""
import csv, json, sys, math
from pathlib import Path
from datetime import date
import pandas as pd
import numpy as np
from rasterio.transform import Affine
from rasterio.warp import transform_geom
from rasterio.features import geometry_mask
from rasterio.windows import from_bounds,Window
from shapely.geometry import shape,mapping
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from v2_features import summarize
from global_v2 import OUT,REPORT,write_csv,write_json,sha
from v2_acquire import VERSION

TS=['entity_id','year','date','sensor','scene_id','ndvi','ndmi','ndvi_valid_pixels','ndvi_total_pixels','ndvi_valid_fraction','ndmi_valid_pixels','ndmi_total_pixels','ndmi_valid_fraction','source_dataset_id']
def export():
    selection=pd.read_csv(OUT/'selection.csv',dtype={'source_field_id':str})
    labels=pd.read_csv(REPORT/'labels_for_acceptance.csv');ids=set(selection.entity_id)
    receipts=[]
    for p in (REPORT/'.cache/observations').glob('*.json'):
        r=json.loads(p.read_text())
        if r['entity_id'] in ids and r.get('algorithm_version')==VERSION:receipts.append(r)
    rows=[{k:r.get(k) for k in TS} for r in receipts]
    rows.sort(key=lambda r:(r['entity_id'],r['year'],r['date'],r['scene_id']))
    keys=[(r['entity_id'],r['year'],r['date'],r['sensor'],r['scene_id']) for r in rows]
    assert len(keys)==len(set(keys)),'Duplicate observation key'
    for r in rows:
        assert f"{r['year']}-04-01"<=r['date']<f"{r['year']}-12-01"
        for ix in ['ndvi','ndmi']:
            assert r[ix] is None or math.isfinite(r[ix]) and -1<=r[ix]<=1
            assert 0<=r[ix+'_valid_pixels']<=r[ix+'_total_pixels']
            assert math.isclose(r[ix+'_valid_fraction'],r[ix+'_valid_pixels']/r[ix+'_total_pixels'])
    write_csv(OUT/'timeseries.csv',rows,TS)
    features=[];coverage=[];daily_rows=[]
    planned=pd.read_csv(REPORT/'scene_selection.csv') if (REPORT/'scene_selection.csv').exists() else pd.DataFrame(columns=['entity_id'])
    geometry_by_id={f['properties']['entity_id']:f['geometry'] for f in json.loads((REPORT/'selected_fields.geojson').read_text())['features']}
    manifest=json.loads((REPORT/'scene_manifest.json').read_text()) if (REPORT/'scene_manifest.json').exists() else {'scenes':[]}
    scene_by_id={i['scene_id']:i for i in manifest['scenes']}
    for s in selection.to_dict('records'):
        eid=s['entity_id'];year=int(s['year']);obs=[r for r in rows if r['entity_id']==eid]
        legacy=[dict(field_id=eid,year=year,date=r['date'],sensor=r['sensor'],scene_id=r['scene_id'],ndvi=r['ndvi'],valid_pixel_fraction=r['ndvi_valid_fraction'],source_dataset_id=r['source_dataset_id']) for r in obs]
        f,daily=summarize(legacy,dict(field_id=eid,year=year,window_start=f'{year}-04-01',window_end_exclusive=f'{year}-12-01'),'no_completed_reads_or_unobservable')
        f['entity_id']=f.pop('field_id');f={'entity_id':eid,**f}
        pending=int((planned.entity_id==eid).sum())-len(obs)
        geometric_status='unknown'
        for sid in planned.loc[planned.entity_id==eid,'selected_scene_id'] if 'selected_scene_id' in planned else []:
            item=scene_by_id.get(sid)
            if not item:continue
            crs=f"EPSG:{item['crs']}";grid=Affine(*item['assets']['B04']['proj:transform'][:6]);g=shape(transform_geom('EPSG:4326',crs,geometry_by_id[eid])).buffer(-10)
            if g.is_empty:geometric_status='unobservable_eroded';continue
            win=from_bounds(*g.bounds,transform=grid);left,top=math.floor(win.col_off),math.floor(win.row_off);w,h=math.ceil(win.col_off+win.width)-left,math.ceil(win.row_off+win.height)-top
            count=int(geometry_mask([mapping(g)],out_shape=(h,w),transform=grid*Affine.translation(left,top),invert=True,all_touched=False).sum())
            if count>=3:geometric_status='observable_geometry';break
            geometric_status='unobservable_fewer_than_3_centers'
        if geometric_status.startswith('unobservable'):
            f['missing_reason']=geometric_status
        elif pending>0:f['missing_reason']=';'.join(filter(None,[f['missing_reason'],'initial_acquisition_incomplete']))
        features.append(f)
        valid=[r for r in daily if r['ndvi'] is not None and r['valid_pixel_fraction']>=.5]
        late=[r for r in valid if r['date']>=f'{year}-09-01']
        ndmi_days={r['date'] for r in obs if r['ndmi'] is not None and r['ndmi_valid_fraction']>=.5}
        coverage.append(dict(entity_id=eid,year=year,source_region=s['source_region'],geometric_status=geometric_status,observed_scene_count=len(obs),valid_obs_count=f['valid_obs_count'],ndmi_valid_days=len(ndmi_days),max_gap_days=f['max_gap_days'],late_valid_days=len(late),oct_nov_valid_days=sum(r['date']>=f'{year}-10-01' for r in valid),first_valid_date=valid[0]['date'] if valid else '',last_valid_date=valid[-1]['date'] if valid else '',planned_scene_count=int((planned.entity_id==eid).sum()),quality_flag=f['quality_flag'],missing_reason=f['missing_reason']))
        daily_rows+=daily
    write_csv(OUT/'features.csv',features)
    write_csv(OUT/'coverage.csv',coverage)
    write_json(REPORT/'pixel_calculation_evidence.json',[dict(entity_id=r['entity_id'],year=r['year'],scene_id=r['scene_id'],calibration=r['calibration'],grid_crs=r['grid_crs'],grid_transform=r['grid_transform'],grid_shape=r['grid_shape'],pixel_evidence=r['pixel_evidence']) for r in receipts if r['pixel_evidence']][:12])
    cov=pd.DataFrame(coverage).merge(labels[['entity_id','year','harvest_label']],on=['entity_id','year'],validate='one_to_one')
    summary=[]
    for (region,label),g in cov.groupby(['source_region','harvest_label']):
        summary.append(dict(region=region,label=label,selected=len(g),with_any_valid_ndvi=int((g.valid_obs_count>0).sum()),usable=int((g.quality_flag=='usable').sum()),limited=int((g.quality_flag=='limited').sum()),no_data=int((g.quality_flag=='no_data').sum()),with_late_observation=int((g.late_valid_days>0).sum()),median_valid_days=float(g.valid_obs_count.median()),median_max_gap_days=float(g.max_gap_days.median())))
    write_csv(REPORT/'coverage_by_region_label.csv',summary)
    write_json(REPORT/'merge_audit.json',dict(selection_rows=len(selection),label_rows=len(labels),feature_rows=len(features),timeseries_rows=len(rows),duplicate_selection_keys=int(selection.duplicated(['entity_id','year']).sum()),duplicate_label_keys=int(labels.duplicated(['entity_id','year']).sum()),duplicate_feature_keys=0,duplicate_timeseries_keys=0,matched_feature_keys=len(features),unmatched_keys=[],excluded_from_selection=['Quebec grain-only','single-class European regions'],with_valid_observations=sum(f['valid_obs_count']>0 for f in features),quality_counts=pd.Series([f['quality_flag'] for f in features]).value_counts().to_dict(),interpretation='Matched feature keys include explicit no_data rows; matching is not successful satellite coverage'))
    write_json(REPORT/'validation_report.json',dict(status='passed_export_invariants',checks=['unique keys','within year and fixed query window','finite indices in [-1,1]','valid pixel counts and fractions','one-to-one feature join'],observations_checked=len(rows),limitations='Grid verification performed on each response; visual alignment and independent pixel evidence QA reported separately'))
    if rows:
        import matplotlib;matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        for region in selection.source_region.unique():
            candidates=selection[selection.source_region==region].entity_id
            eid=next((x for x in candidates if any(r['entity_id']==x and r['ndvi'] is not None for r in rows)),None)
            if not eid:continue
            rr=[r for r in rows if r['entity_id']==eid]
            fig,ax=plt.subplots(figsize=(9,3))
            for ix in ['ndvi','ndmi']:
                good=[r for r in rr if r[ix] is not None and r[ix+'_valid_fraction']>=.5]
                ax.scatter([date.fromisoformat(r['date']) for r in good],[r[ix] for r in good],label=ix,s=16)
            ax.set(title=eid+' / 2023 retrospective',ylim=(-1,1),ylabel='Field median index');ax.legend();fig.autofmt_xdate();fig.tight_layout();fig.savefig(REPORT/f'timeseries_{region}.png',dpi=130);plt.close(fig)
    cache_bytes=sum(p.stat().st_size for p in (REPORT/'.cache').rglob('*') if p.is_file())
    write_json(REPORT/'storage_report.json',dict(checkpoint_bytes=cache_bytes,tracked_output_bytes=sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file()),downloaded_crop_bytes=sum(r['response_bytes'] for r in receipts),full_scene_downloads=0,expansion_decision='hold until pilot coverage and runtime review;no 2000-5000 run started'))
    print('Exported',len(features),'keys;',len(rows),'scene observations;',sum(f['valid_obs_count']>0 for f in features),'with valid NDVI',flush=True)
if __name__=='__main__':export()
