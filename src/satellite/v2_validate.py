"""Acceptance against actual pilot inputs/observations, never simulated data."""
import json, math, re
from pathlib import Path
import xml.etree.ElementTree as ET
import pandas as pd
from global_v2 import OUT,REPORT,write_json,sha
from v2_acquire import VERSION

def main():
    s=pd.read_csv(OUT/'selection.csv');f=pd.read_csv(OUT/'features.csv');t=pd.read_csv(OUT/'timeseries.csv');labels=pd.read_csv(REPORT/'labels_for_acceptance.csv');checks={}
    assert len(s)==200 and not s.duplicated(['entity_id','year']).any()
    merged=s.merge(labels,on=['entity_id','year'],validate='one_to_one')
    counts=merged.groupby(['source_region','harvest_label']).size()
    assert len(counts)==8 and set(counts)=={25}
    assert not f.duplicated(['entity_id','year']).any() and len(f)==200
    assert len(s.merge(f,on=['entity_id','year'],validate='one_to_one'))==200
    forbidden={'harvest_label','label','label_raw','original_code','crop_code','source_crop_name','original_name','selection_reason'}
    assert not forbidden.intersection(f.columns) and not forbidden.intersection(t.columns)
    assert not t.duplicated(['entity_id','year','date','sensor','scene_id']).any()
    assert t.entity_id.isin(s.entity_id).all()
    for ix in ['ndvi','ndmi']:
        assert t[ix].dropna().between(-1,1).all()
        assert t[ix+'_valid_fraction'].between(0,1).all()
        assert (t[ix+'_valid_pixels']<=t[ix+'_total_pixels']).all()
        assert (t.loc[t[ix].notna(),ix+'_valid_pixels']>=3).all()
    checks['selection_stratification_and_unique_joins']=True;checks['no_label_derived_predictors']=True;checks['index_and_support_invariants']=True
    scene=json.loads((REPORT/'scene_manifest.json').read_text());byid={x['scene_id']:x for x in scene['scenes']}
    physical=[]
    for r in t.to_dict('records'):
        assert f"{r['year']}-04-01"<=r['date']<f"{r['year']}-12-01"
        sc=byid[r['scene_id']];assert sc['crs'] is not None
        assert sc['assets']['B04']['gsd']==10 and sc['assets']['B08']['gsd']==10 and sc['assets']['B11']['gsd']==20 and sc['assets']['SCL']['gsd']==20
        parts=sc['product_id'].split('_');physical.append((r['entity_id'],r['year'],parts[0],parts[2],parts[5]))
    assert len(physical)==len(set(physical));checks['no_duplicate_physical_products']=True;checks['date_window_crs_native_resolutions']=True
    meta_count=0
    for sc in scene['scenes']:
        cal=sc['calibration']
        if not cal:continue
        p=REPORT/'.cache/metadata'/(sc['scene_id']+'.xml');assert sha(p)==cal['xml_sha256']
        xml=ET.fromstring(p.read_bytes());values={e.tag.split('}')[-1]:e.text for e in xml.iter() if e.text}
        assert float(values['BOA_QUANTIFICATION_VALUE'])==cal['quantification']
        if 'PROCESSING_BASELINE' in values:assert values['PROCESSING_BASELINE'].strip()==sc['processing_baseline']
        offsets={int(e.attrib['band_id']):float(e.text) for e in xml.iter() if e.tag.split('}')[-1]=='BOA_ADD_OFFSET'}
        for band,n in [('B04',3),('B08',7),('B11',11)]:assert cal['offsets'][band]==offsets[n]
        meta_count+=1
    checks['product_xml_quantification_offset_baseline_hash']=meta_count
    evidence_count=0
    for p in (REPORT/'.cache/observations').glob('*.json'):
        r=json.loads(p.read_text())
        if r.get('algorithm_version')!=VERSION:continue
        cal=r['calibration']
        for pix in r['pixel_evidence']:
            for band in ['B04','B08','B11']:
                raw=pix['raw_dn'][band];value=pix['reflectance'][band]
                if value is not None:
                    assert raw!=cal['nodata'];assert math.isclose((raw+cal['offsets'][band])/cal['quantification'],value,abs_tol=1e-12)
            ref=pix['reflectance']
            assert math.isclose((ref['B08']-ref['B04'])/(ref['B08']+ref['B04']),pix['ndvi'],abs_tol=1e-12)
            if pix['ndmi'] is not None:assert math.isclose((ref['B08']-ref['B11'])/(ref['B08']+ref['B11']),pix['ndmi'],abs_tol=1e-12)
            evidence_count+=1
    checks['real_pixel_dn_to_reflectance_to_index']=evidence_count
    # Independent pandas recomputation catches joins/date selection/empty row mistakes.
    for row in f.to_dict('records'):
        daily=t[t.entity_id==row['entity_id']].sort_values(['date','ndvi_valid_fraction','scene_id'],ascending=[True,False,True]).drop_duplicates('date')
        good=daily[(daily.ndvi_valid_fraction>=.5)&daily.ndvi.notna()]
        assert len(good)==row['valid_obs_count']
        if len(good):assert math.isclose(good.ndvi.max(),row['ndvi_peak'],abs_tol=1e-12)
        else:assert pd.isna(row['ndvi_peak'])
    checks['independent_daily_count_and_peak']=True
    alignment=json.loads((REPORT/'alignment_evidence/checks.json').read_text());assert len(alignment)>=4 and all(a['independent_pixel_counts_and_medians_match'] for a in alignment)
    checks['real_array_alignment_and_median_rechecks']=len(alignment)
    secret_pattern=re.compile(r'[?&](?:sig|skoid|sktid|skt|ske|sks|skv|sv|se|sp|sr)=',re.I)
    for root in [OUT,REPORT]:
        for p in root.rglob('*'):
            if '.cache' in p.parts or p.suffix not in ['.json','.csv','.md','.txt']:continue
            assert not secret_pattern.search(p.read_text(encoding='utf-8')),f'Signed asset leak: {p.name}'
    checks['no_signed_assets_in_delivery']=True
    write_json(REPORT/'acceptance.json',dict(status='passed',checks=checks,selected_field_years=200,real_scene_rows=len(t),field_years_with_valid_ndvi=int((f.valid_obs_count>0).sum()),limitations=['initial ten-day candidate policy;not all archive scenes','Netherlands legacy remains separate with early-season and NDMI gaps','declared labels are not final-use ground truth']))
    print('PASS actual-data acceptance',checks)
if __name__=='__main__':main()
