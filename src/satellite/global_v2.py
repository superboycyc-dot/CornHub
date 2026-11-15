"""Versioned global pilot. No labels are passed to imagery or feature algorithms."""
import argparse, csv, hashlib, json, math, subprocess, time
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from pyproj import CRS, Transformer
from shapely import from_wkb
from shapely.geometry import shape, mapping
from shapely.ops import transform

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/processed/v2/satellite'
REPORT=ROOT/'reports/b_satellite/v2'
INPUT_SHA='a8ccadff2fa3a2e53c1469e2c243d7dab98d7466'
SEED=20261114
def write_json(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8',newline='\n')
    temporary.replace(path)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write_csv(path,rows,columns=None):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=columns or list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
def prepare(source):
    actual=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD']).decode().strip()
    if actual!=INPUT_SHA:raise ValueError('Input checkout SHA differs')
    base=source/'data/global_maize'; inventory=[];hashes={};pools={}; crs_records=[]
    for partition in sorted((base/'eurocrops/parcels').iterdir()):
        frames=[]
        for p in sorted(partition.glob('*.parquet')):
            hashes[str(p.relative_to(source))]=sha(p)
            schema=pq.read_schema(p);geo=json.loads(schema.metadata[b'geo']);col=geo['primary_column']
            crs=CRS(geo['columns'][col]['crs'])
            if crs.to_epsg()!=3035:raise ValueError('Unexpected EuroCrops CRS')
            t=pq.read_table(p).to_pandas(); t['input_file']=str(p.relative_to(source)); frames.append(t)
        frame=pd.concat(frames,ignore_index=True)
        dup=int(frame.duplicated(['cropfield','source_year']).sum())
        if dup:raise ValueError(f'Duplicate source key {partition.name}')
        crs_records.append(dict(partition=partition.name,crs=crs.to_string(),id_column='cropfield',original_id_column='off_id'))
        for label,g in frame.groupby('harvest_label'):
            inventory.append(dict(region=partition.name,year=2023,label=label,count=len(g),crs=crs.to_string()))
        if set(frame.harvest_label)=={'grain','silage'}:pools[partition.name]=frame
    selected=[]; labels=[];features=[];area_checks=[];rng=np.random.default_rng(SEED)
    for partition,frame in pools.items():
        for label in ['grain','silage']:
            g=frame[frame.harvest_label==label].sort_values(['area_ha','cropfield']).reset_index(drop=True)
            # Rank quintiles ensure small and large fields are included; 5 per quintile.
            for q,indices in enumerate(np.array_split(np.arange(len(g)),5)):
                picks=rng.choice(indices,5,replace=False)
                for ix in picks:
                    row=g.iloc[int(ix)];geom=from_wkb(row.geometry)
                    if geom.is_empty or not geom.is_valid:raise ValueError('Selected invalid geometry; no silent repair')
                    area_checks.append(abs(geom.area/10000-float(row.area_ha)))
                    geom=transform(Transformer.from_crs(3035,4326,always_xy=True).transform,geom)
                    fid=str(row.cropfield);eid=f'eurocrops_gpqtv202_{partition}_{fid}'
                    selected.append(dict(entity_id=eid,source_dataset_id='eurocrops_v2_gpqtv202',source_region=row.source_region,year=int(row.source_year),source_field_id=fid,selection_reason=f'seed_{SEED};region_label_area_quintile_{q+1};5_per_stratum'))
                    labels.append(dict(entity_id=eid,year=2023,harvest_label=label,label_nature='annual_declared_use',source_field_id=fid,source_original_id=str(row.off_id),source_file=row.input_file,area_ha=float(row.area_ha)))
                    features.append(dict(type='Feature',properties=dict(entity_id=eid,year=2023,area_ha=float(row.area_ha)),geometry=mapping(geom)))
    if len(selected)!=200:raise ValueError('Expected 200 pilot records')
    write_csv(OUT/'selection.csv',selected);write_csv(REPORT/'labels_for_acceptance.csv',labels)
    write_json(REPORT/'selected_fields.geojson',dict(type='FeatureCollection',features=features))
    nl=base/'netherlands_2025';nd=pd.read_csv(nl/'ndvi_all.csv');idx=pd.read_csv(nl/'field_index.csv')
    nl_audit=dict(field_count=len(idx),label_counts=idx.harvest_label.value_counts().to_dict(),rows=len(nd),unique_dates=sorted(nd.date.unique().tolist()),scene_count=int(nd.scene.nunique()),zero_interior_rows=int((nd.interior_pixels==0).sum()),null_ndvi_rows=int(nd.ndvi_median.isna().sum()),legacy_policy='10m erosion;SCL4,5;selected scenes;not v2 comparable without reprocessing',decision='preserve legacy;reuse scene inventory and boundary;recompute comparable pixels and fill seasonal gaps')
    write_json(REPORT/'netherlands_legacy_audit.json',nl_audit)
    for p in nl.iterdir():
        if p.is_file():hashes[str(p.relative_to(source))]=sha(p)
    # Inventory Quebec without using its grain-only labels for selection.
    qc=[]
    for p in (base/'quebec').rglob('*.parquet'):
        schema=pq.read_schema(p);geo=json.loads(schema.metadata[b'geo']);col=geo['primary_column'];crs=CRS(geo['columns'][col]['crs'])
        crs_records.append(dict(partition=str(p.relative_to(base)),crs=crs.to_string(),columns=schema.names,row_count=pq.ParquetFile(p).metadata.num_rows))
        hashes[str(p.relative_to(source))]=sha(p)
        qc.append(pq.read_table(p,columns=['AN','IDANPAR','IDPAR','harvest_label','CODPRO1','NBPRO','PRCSUPPR1']).to_pandas())
    q=pd.concat(qc,ignore_index=True)
    assert not q.duplicated(['IDANPAR','AN']).any()
    assert set(q.AN)=={2025} and set(q.harvest_label)=={'grain'} and set(q.CODPRO1)=={'MGR'}
    assert ((q.NBPRO==1)&(q.PRCSUPPR1==100)).all()
    nlf=json.loads((nl/'fields.geojson').read_text());assert nlf.get('crs') is None
    assert len({str(f['id']) for f in nlf['features']})==len(idx)==134 and set(idx.field_id)=={str(f['id']) for f in nlf['features']}
    assert not nd.duplicated(['field_id','date','scene']).any()
    write_json(REPORT/'input_schema_audit.json',dict(europe_field_years=sum(r['count'] for r in inventory),europe_years=[2023],europe_crs='EPSG:3035',europe_source_id='cropfield within region/year/version',europe_original_id='off_id preserved separately',selected_area_ha_max_absolute_error_vs_3035_geometry=max(area_checks),netherlands=dict(field_years=134,year=2025,crs='RFC7946 CRS84 longitude/latitude;no foreign CRS member',id='GeoJSON id = field_index.field_id UUID',labels={'grain':13,'silage':121},unique_scene_keys=True),quebec=dict(field_years=len(q),years=[2025],crs='EPSG:4269 NAD83;not relabelled EPSG4326;not queried',annual_source_key='IDANPAR+AN',persistent_source_id='IDPAR',duplicate_annual_keys=0,labels={'grain':len(q)},single_crop_100pct=True,excluded_reason='grain_only')))
    write_csv(REPORT/'input_inventory.csv',inventory)
    write_json(REPORT/'crs_audit.json',crs_records)
    write_json(REPORT/'input_manifest.json',dict(input_branch='data/global-maize-fields',input_sha=actual,main_sha='a7d843f5047a8fb86510a6139c086a5ed01efb61',v1_code_sha='05a81a7d1634c80d3c56b66cf9eb9acb9527fc9b',seed=SEED,input_files_sha256=hashes,selection_sha256=sha(OUT/'selection.csv'),parameters=dict(window='[04-01,12-01)',target_grid='B04 native 10m',erosion_m=10,min_pixels=3,valid_scl=[4,5,6,7],min_fraction=.5,b11_resampling='nearest',scl_resampling='nearest',reflectance='product XML only;no date/baseline inference',daily_rule='max NDVI fraction then scene_id',extra_ndmi_features='none'),created_at_utc=datetime.now(timezone.utc).isoformat()))
    print('Prepared',len(selected),'Netherlands audit',nl_audit,flush=True)

def main():
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['prepare']);p.add_argument('--input',type=Path,required=True);a=p.parse_args();prepare(a.input)
if __name__=='__main__':main()
