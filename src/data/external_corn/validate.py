"""Read every published shard and verify manifests, keys, selection and geometry metadata."""
import hashlib,json
from collections import Counter
from pathlib import Path
import pyarrow.parquet as pq
import shapely
import numpy as np
from pyproj import Transformer
area_transform=Transformer.from_crs(4326,5070,always_xy=True)
ROOT=Path(__file__).resolve().parents[3]
results={}
for kind in ['csb','cropsight']:
 report=json.loads((ROOT/'reports/a_data/external_corn'/f'{kind}_processing.json').read_text())
 seen=set();counts=Counter();invalid=0;rows=0
 for entry in report['shards']:
  p=ROOT/entry['path'];assert p.stat().st_size==entry['bytes']
  assert hashlib.sha256(p.read_bytes()).hexdigest()==entry['sha256']
  t=pq.read_table(p);assert len(t)==entry['rows'];geo=json.loads(t.schema.metadata[b'geo'])
  assert geo['columns']['geometry']['crs']['id']['code']==4326
  ids=t['candidate_id'].to_pylist();assert len(set(ids))==len(ids) and not seen.intersection(ids);seen.update(ids)
  assert t['harvest_type'].null_count==len(t)
  assert all(x>0 for x in t['area_ha'].to_pylist())
  geometries=shapely.from_wkb(t['geometry'].to_pylist());valid=shapely.is_valid(geometries)
  assert np.array_equal(valid,np.array(t['geometry_valid'].to_pylist()));invalid+=int((~valid).sum())
  assert not np.any(shapely.is_empty(geometries))
  assert np.isfinite(shapely.bounds(geometries)).all()
  sample_area=shapely.area(shapely.transform(geometries[:1],area_transform.transform,interleaved=False))[0]/10000
  assert abs(sample_area-t['area_ha'][0].as_py())<0.001, 'Area roundtrip sample mismatch'
  if kind=='csb':
   mask=np.zeros(len(t),dtype=bool)
   for y in [2021,2022,2023]:
    corn=np.array([x==1 for x in t[f'cdl{y}'].to_pylist()]);counts[str(y)]+=int(corn.sum());mask|=corn
   assert mask.all()
  else:
   assert all(str(v).lower() in ['corn','maize'] for v in t['crop_label_raw'].to_pylist())
   assert all(y in [2021,2022,2023] for y in t['year'].to_pylist());counts.update(map(str,t['year'].to_pylist()))
  rows+=len(t)
 assert rows==report['selected_rows'] and dict(counts)==report['corn_field_year_counts']
 if kind=='csb':
  source=json.loads((ROOT/'reports/a_data/external_corn/csb_source_counts.json').read_text())
  assert source['union_corn_polygons']==rows and source['corn_field_year_counts']==dict(counts)
 results[kind]={'status':'passed','shards':len(report['shards']),'rows':rows,'corn_field_year_counts':dict(counts),'duplicate_ids':0,'all_harvest_types_unknown':True,'invalid_geometries_flagged':invalid,'area_roundtrip_samples':len(report['shards']),'area_tolerance_ha':0.001}
 print(kind,results[kind],flush=True)
(ROOT/'reports/a_data/external_corn/validation.json').write_text(json.dumps(results,indent=2)+'\n')
