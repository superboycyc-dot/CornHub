"""Brev-only V10 alias inference: frozen V9 plus US confidence, cached NDVI only."""
from pathlib import Path
import json,csv,gzip,sqlite3,hashlib,math,shutil
from datetime import datetime,timezone
from collections import Counter
import pyarrow.parquet as pq
from v9_us_predict import USV9Predictor
ROOT=Path(__file__).resolve().parent
RUN=ROOT/'runs'/('v10-md-existing-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
OUT=RUN/'publish/data/processed/model/v10_maryland_existing_ndvi';OUT.mkdir(parents=True)
old=ROOT/'runs/v9-ca-md-2021-2025'
with gzip.open(old/'fields.json.gz','rt') as h:fields={f['field_id']:f for f in json.load(h) if f['state']=='MD'}
source=Path((ROOT/'latest_v9.txt').read_text().strip());cal=Path((ROOT/'latest_v9_us_calibration.txt').read_text().strip())
v8=Path(json.loads((source/'protocol.json').read_text())['source_V8'])
training={(r['field_id'],r['year']) for r in pq.read_table(v8/'training_rows.parquet').to_pylist() if r['country']=='US'}
model=USV9Predictor.from_joblib(source/'models/V9_full.joblib',cal/'models/us_calibrator_full.joblib')
db=sqlite3.connect(f'file:{old}/observations.sqlite?mode=ro',uri=True)
snapshot=[(fid,yr,json.loads(p)) for fid,yr,p in db.execute('SELECT * FROM features')];db.close()
ndvi=model.predictor.bundle['components']['ndvi']['numeric_features']
records=[];excluded=Counter()
for fid,yr,r in sorted(snapshot):
 if fid not in fields or yr not in range(2021,2026):continue
 f=fields[fid];code=f['crop_codes'].get(str(yr))
 if code is not None and code!=1:excluded['not_corn']+=1;continue
 if not any(isinstance(r.get(k),(int,float)) and math.isfinite(r[k]) for k in ndvi):excluded['all_null_ndvi']+=1;continue
 records.append((fid,yr,r))
results=model.predict([{**r,'country':'US'} for _,_,r in records]);rows=[]
for (fid,yr,r),p in zip(records,results):
 f=fields[fid];confirmed=f['crop_codes'].get(str(yr))==1 or (fid,yr) in training
 row=dict(field_id=fid,state='MD',year=yr,harvest_type=p['predicted_label'],confidence_score=p['confidence_score'],raw_self_confidence=p['raw_self_confidence'],p_silage=p['p_silage'],status='predicted' if confirmed else 'conditional_prediction',corn_eligibility='confirmed_by_source' if confirmed else 'unknown',training_overlap=(fid,yr) in training,model_version='V10_alias_V9_plus_US_confidence',confidence_kind=p['confidence_kind'],calibration_status=p['calibration_status'],valid_obs_count=r.get('valid_obs_count'),quality_flag=r.get('quality_flag'),feature_missing_reason=r.get('missing_reason'))
 assert 0<=row['confidence_score']<=100 and 0<=row['p_silage']<=1
 assert row['harvest_type']==('silage' if row['p_silage']>=.5 else 'grain')
 rows.append(row)
assert rows and len({(r['field_id'],r['year']) for r in rows})==len(rows)
for year in range(2021,2026):
 with (OUT/f'{year}.csv').open('w',newline='') as h:
  w=csv.DictWriter(h,fieldnames=list(rows[0]));w.writeheader();w.writerows(r for r in rows if r['year']==year)
with (OUT/'predictions.csv').open('w',newline='') as h:
 w=csv.DictWriter(h,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
ids={r['field_id'] for r in rows}
(OUT/'fields.geojson').write_text(json.dumps(dict(type='FeatureCollection',features=[dict(type='Feature',geometry=fields[fid]['geometry'],properties=dict(field_id=fid,state='MD')) for fid in sorted(ids)])))
(OUT/'input_features.json').write_text(json.dumps([dict(field_id=fid,year=yr,features=r) for fid,yr,r in records],allow_nan=False))
manifest=dict(status='complete',scope='Maryland existing cached NDVI only; not statewide coverage',model_version='V10 is user alias for frozen V9 plus US-only confidence calibration',generated_at=datetime.now(timezone.utc).isoformat(),rows=len(rows),fields=len(ids),years={str(y):dict(Counter(r['harvest_type'] for r in rows if r['year']==y)) for y in range(2021,2026)},statuses=dict(Counter(r['status'] for r in rows)),excluded=dict(excluded),training_overlap=sum(r['training_overlap'] for r in rows),remote_run=str(RUN),model_source=str(source),calibration_source=str(cal))
(OUT/'README.md').write_text('# V10 Maryland 2021–2025 — existing NDVI only\n\nV10 is the user-confirmed alias for frozen V9 + US-only confidence calibration. No new imagery downloads or feature extraction. Includes only Maryland field-years with available cached NDVI at the input snapshot; not statewide coverage.\n\npredictions.csv combines five annual CSVs. Join fields.geojson by field_id. confidence_score is experimental estimated correctness (0–100); raw_self_confidence is uncalibrated class probability ×100. Calibration uses Maryland farm-group development validation, not independent external validation. training_overlap flags training field-years. These are inference outputs, not an accuracy benchmark. conditional_prediction means annual maize eligibility is unknown; prediction is conditional on maize. Missing context features remain missing under the frozen model.\n')
shutil.copy2(__file__,OUT/'predict_existing_md.py')
manifest['source_hashes']={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [source/'models/V9_full.joblib',cal/'models/us_calibrator_full.joblib',ROOT/'v9_predict.py',ROOT/'v9_us_predict.py']}
manifest['files']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.iterdir() if p.is_file()}
(OUT/'index.json').write_text(json.dumps(manifest,indent=2))
for name,digest in manifest['files'].items():assert hashlib.sha256((OUT/name).read_bytes()).hexdigest()==digest
(OUT/'verification.json').write_text(json.dumps(dict(status='passed',rows=len(rows),checks=['unique field-year keys','Maryland only, 2021–2025','non-null NDVI required','frozen class threshold','confidence range','file hashes verified']),indent=2))
(ROOT/'latest_v10_md_existing.txt').write_text(str(RUN));print(json.dumps(manifest,indent=2))
