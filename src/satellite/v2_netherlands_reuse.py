"""Reuse the real legacy Netherlands observations without pretending they are v2 pixels."""
import argparse,json
from pathlib import Path
import pandas as pd
from global_v2 import OUT,REPORT,write_csv,write_json,sha
from v2_export import summarize,TS

def main(source):
    base=source/'data/global_maize/netherlands_2025';idx=pd.read_csv(base/'field_index.csv',dtype={'field_id':str});raw=pd.read_csv(base/'ndvi_all.csv',dtype={'field_id':str})
    folder=OUT/'netherlands_legacy';rows=[];features=[];coverage=[];selection=[]
    for p in raw.to_dict('records'):
        total=int(p['interior_pixels']);valid=int(p['valid_pixels']);ndvi=None if pd.isna(p['ndvi_median']) or valid<3 else float(p['ndvi_median'])
        rows.append(dict(entity_id='nl_rvo_brp_2025_'+p['field_id'],year=2025,date=p['date'],sensor='sentinel2_l2a',scene_id=p['scene'],ndvi=ndvi,ndmi=None,ndvi_valid_pixels=valid,ndvi_total_pixels=total,ndvi_valid_fraction=valid/total if total else None,ndmi_valid_pixels=None,ndmi_total_pixels=None,ndmi_valid_fraction=None,source_dataset_id='earthsearch_sentinel2_l2a_legacy_nl'))
    for i in idx.to_dict('records'):
        eid='nl_rvo_brp_2025_'+i['field_id'];obs=[r for r in rows if r['entity_id']==eid]
        usable=[dict(field_id=eid,year=2025,date=r['date'],sensor=r['sensor'],scene_id=r['scene_id'],ndvi=r['ndvi'],valid_pixel_fraction=r['ndvi_valid_fraction'],source_dataset_id=r['source_dataset_id']) for r in obs if r['ndvi_total_pixels']>=3]
        f,daily=summarize(usable,dict(field_id=eid,year=2025,window_start='2025-04-01',window_end_exclusive='2025-12-01'),'unobservable_after_10m_erosion_or_legacy_missing')
        f['entity_id']=f.pop('field_id');f={'entity_id':eid,**f};f['missing_reason']=';'.join(filter(None,[f['missing_reason'],'legacy_8_dates_only;ndmi_not_acquired;scl45_legacy_policy']))
        features.append(f);selection.append(dict(entity_id=eid,source_dataset_id='nl_rvo_brp_2025',source_region='nl_southeast',year=2025,source_field_id=i['field_id'],selection_reason='reuse_all_134_existing_fields;legacy_pixel_policy_separate'))
        coverage.append(dict(entity_id=eid,year=2025,valid_obs_count=f['valid_obs_count'],max_gap_days=f['max_gap_days'],late_valid_days=sum(r['date']>='2025-09-01' and r['ndvi'] is not None and r['valid_pixel_fraction']>=.5 for r in daily),quality_flag=f['quality_flag'],missing_reason=f['missing_reason']))
    write_csv(folder/'timeseries.csv',rows,TS);write_csv(folder/'features.csv',features);write_csv(folder/'selection.csv',selection);write_csv(folder/'coverage.csv',coverage)
    labs=[dict(entity_id='nl_rvo_brp_2025_'+r['field_id'],year=2025,harvest_label=r['harvest_label'],label_nature='annual_declared_use',source_field_id=r['field_id']) for r in idx.to_dict('records')]
    write_csv(REPORT/'netherlands_labels_for_acceptance.csv',labs)
    summary=pd.DataFrame(features).merge(pd.DataFrame(labs),on=['entity_id','year'],validate='one_to_one').groupby('harvest_label').agg(selected=('entity_id','size'),with_valid_ndvi=('valid_obs_count',lambda s:int((s>0).sum())),median_valid_days=('valid_obs_count','median')).reset_index().to_dict('records')
    write_csv(REPORT/'netherlands_legacy_coverage_by_label.csv',summary)
    write_json(REPORT/'netherlands_gapfill_queue.json',dict(status='pending_harmonized_gapfill',legacy_reused_field_years=134,legacy_real_observations=1072,with_valid_ndvi=sum(f['valid_obs_count']>0 for f in features),no_new_pixels_downloaded=True,required_gaps=['April-May absent','longest per-field gaps in netherlands_legacy/coverage.csv','NDMI unavailable','recheck legacy SCL4,5 vs v2 SCL4,5,6,7 before combining'],legacy_scene_manifest_sha256=sha(base/'scenes.json'),cross_catalog_dedupe_rule='match satellite+sensing timestamp+MGRS tile;prefer latest processing baseline and generation;never append same physical observation from both catalogs',note='Legacy pixels kept separate;not counted in the European 200 pilot'))
    write_json(REPORT/'netherlands_legacy_scene_manifest.json',json.loads((base/'scenes.json').read_text()))
    print('Reused Netherlands',len(features),'field-years',len(rows),'real scene rows;',summary)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);main(p.parse_args().input)
