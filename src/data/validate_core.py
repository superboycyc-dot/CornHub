"""Independently read and validate serialized core artifacts; no model execution."""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from pyproj import Transformer
from shapely.geometry import shape
from shapely import transform

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT/'data/processed/core'

def read_csv(name):
    with (CORE/name).open(newline='') as handle:
        return list(csv.DictReader(handle))

def check(value, message):
    if not value:
        raise ValueError(message)

def main():
    fields = json.loads((CORE/'fields.geojson').read_text())['features']
    labels, folds, ids = read_csv('labels.csv'),read_csv('validation_folds.csv'),read_csv('field_id_map.csv')
    by_id = {f['properties']['field_id']:f for f in fields}
    check(len(by_id)==len(fields)==83, 'Field keys/count')
    check(len(ids)==len({r['source_field_id'] for r in ids})==83, 'Mapping keys/count')
    keys = lambda rows: {(r['field_id'],int(r['year'])) for r in rows}
    check(len(keys(labels))==len(labels)==44, 'Label keys/count')
    check(len(keys(folds))==len(folds)==44 and keys(folds)==keys(labels), 'Fold keys/count')
    check({r['field_id'] for r in labels} <= set(by_id), 'Orphan labels')
    check(len({r['field_id'] for r in labels})==34, 'Unique labeled fields')
    check(all(r['label']==r['label_raw'].lower() and r['label'] in ('grain','silage') for r in labels), 'Label normalization')
    check(all(r['source_dataset_id']=='barc_corn_2021_2023_challenge' for r in labels), 'Label provenance')
    for row in ids:
        p=by_id[row['field_id']]['properties']
        check(p['source_field_id']==row['source_field_id'] and row['field_id']=='barc_'+row['source_field_id'], 'ID mapping mismatch')
    tx=Transformer.from_crs(4326,26918,always_xy=True)
    max_area_delta=0
    for f in fields:
        p=f['properties']; geom=shape(f['geometry'])
        check(geom.is_valid and not geom.is_empty, f"Invalid exported geometry {p['field_id']}")
        check(geom.geom_type in ('Polygon','MultiPolygon'), 'Export geometry type')
        area=transform(geom,tx.transform,interleaved=False).area/10000
        delta=abs(area-p['area_ha']);max_area_delta=max(max_area_delta,delta)
        check(p['area_ha']>0 and delta < 0.0001, 'Serialized geometry/area mismatch')
    memberships={}
    for row in folds:
        memberships.setdefault(row['field_id'],set()).add(row['fold_id'])
    check(all(len(v)==1 for v in memberships.values()), 'Cross-year field leakage')
    farm_folds={}
    for row in folds:
        farm=by_id[row['field_id']]['properties']['farm_group']
        farm_folds.setdefault(farm,set()).add(row['fold_id'])
    check(len(farm_folds)==5 and all(len(v)==1 for v in farm_folds.values()), 'Farm leakage')
    check(len({next(iter(v)) for v in farm_folds.values()})==5, 'Multiple farms per fold')
    sample=json.loads((CORE/'smoke_sample.json').read_text())
    first=sorted(labels,key=lambda r:(r['field_id'],int(r['year'])))[0]
    check((sample['field_id'],sample['year'])==(first['field_id'],int(first['year'])), 'Smoke selection')
    check(sample['window_start']=='2021-04-01' and sample['window_end_exclusive']=='2021-12-01', 'Smoke window')
    # Ensure labels and geometries are not merely self-consistent with modified source bytes.
    acceptance=json.loads((ROOT/'reports/a_data/acceptance.json').read_text())
    source=ROOT/acceptance['source_path']
    check(hashlib.sha256(source.read_bytes()).hexdigest()==acceptance['source_sha256'], 'Source hash changed')
    result=dict(status='passed',fields=len(fields),labels=len(labels),folds=len(folds),id_map=len(ids),
                unique_labeled_fields=34,duplicate_keys=0,orphan_labels=0,invalid_exported_geometries=0,
                max_serialized_area_roundtrip_delta_ha=max_area_delta,
                cross_year_field_leakage=False,cross_year_farm_leakage=False,
                smoke_sample=sample,source_hash_verified=True,
                label_counts=dict(Counter(r['label'] for r in labels)))
    print(json.dumps(result,indent=2))

if __name__=='__main__':
    main()
