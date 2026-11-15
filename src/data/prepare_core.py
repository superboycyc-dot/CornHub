"""Adapt the unchanged official BARC GeoPackage to the team core contract."""
from __future__ import annotations
import csv
import hashlib
import json
import math
import platform
import sqlite3
import struct
from collections import Counter
from pathlib import Path

import pyproj
import shapely
from pyproj import CRS, Transformer
from shapely import from_wkb, to_wkb
from shapely.geometry import mapping
from shapely.geometry.polygon import orient
from shapely import transform as transform_array

def transform(fn, geom):
    return transform_array(geom, fn, interleaved=False)

def polygon_parts(geom):
    if geom.geom_type == "Polygon":
        return [geom]
    return [p for g in getattr(geom, "geoms", []) for p in polygon_parts(g)]

def valid_polygon(geom, fid, crs, repairs):
    if geom.is_valid:
        return geom
    fixed = shapely.make_valid(geom)
    polygons = polygon_parts(fixed)
    require(bool(polygons), f"No polygon remains: {fid}")
    result = shapely.MultiPolygon(polygons)
    repairs.append(dict(field_id=fid, crs=crs, reason=shapely.is_valid_reason(geom),
                        method="make_valid; retain polygon parts, drop collapsed non-area components",
                        area_before=geom.area, area_after=result.area,
                        absolute_area_delta=abs(result.area-geom.area)))
    require(result.is_valid, f"Repair failed: {fid}")
    return result

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / '04_Evaluation/BARC_Corn.2021-2023.gpkg'
LEGACY = ROOT / 'data/processed/barc_field_year_labels.csv'
OUT = ROOT / 'data/processed/core'
REPORT = ROOT / 'reports/a_data'
DATASET = 'barc_corn_2021_2023_challenge'
LAYER = 'barc_silage_grain_corn20212023'
YEARS = (2021, 2022, 2023)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def write_csv(path, columns, rows):
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def decode_gpkg(blob, expected_srs):
    require(blob is not None and blob[:2] == b'GP', 'Missing/invalid GeoPackage geometry')
    require(blob[2] == 0, 'Unsupported GeoPackage geometry version')
    flags = blob[3]
    require(not flags & 0x30, 'Empty or extended GeoPackage geometry')
    srs = struct.unpack('<i' if flags & 1 else '>i', blob[4:8])[0]
    require(srs == expected_srs, 'Geometry CRS differs from layer CRS')
    envelope = (flags >> 1) & 7
    sizes = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}
    require(envelope in sizes, 'Unsupported envelope type')
    return from_wkb(blob[8 + sizes[envelope]:])


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    REPORT.mkdir(parents=True, exist_ok=True)
    source_hash = sha(SOURCE)
    with sqlite3.connect(f'file:{SOURCE}?mode=ro', uri=True) as con:
        con.row_factory = sqlite3.Row
        geom_meta = con.execute('SELECT * FROM gpkg_geometry_columns WHERE table_name=?', (LAYER,)).fetchone()
        require(geom_meta['column_name'] == 'geom', 'Unexpected geometry column')
        srs_id = geom_meta['srs_id']
        crs_row = con.execute('SELECT * FROM gpkg_spatial_ref_sys WHERE srs_id=?', (srs_id,)).fetchone()
        source_crs = CRS.from_wkt(crs_row['definition'])
        records = list(con.execute(f'SELECT * FROM "{LAYER}" ORDER BY OBJECTID'))
    require(source_crs.is_projected, 'Source CRS is not projected')
    require('survey foot' in source_crs.axis_info[0].unit_name.lower(), 'Unexpected source units')
    to_area = Transformer.from_crs(source_crs, 'EPSG:26918', always_xy=True)
    to_geo = Transformer.from_crs(source_crs, 'EPSG:4326', always_xy=True)
    fields, labels, id_map, checks, missing, unexpected = [], [], [], [], Counter(), []
    repairs = []
    seen = set()
    for row in records:
        require(row['OBJECTID'] is not None, 'Missing OBJECTID')
        raw_id = str(row['OBJECTID'])
        fid = 'barc_' + raw_id
        require(fid not in seen, f'Duplicate OBJECTID: {fid}')
        seen.add(fid)
        require(row['FARM_ID'] is not None, f'Missing FARM_ID: {fid}')
        farm_id = format(row['FARM_ID'], '.15g')
        geom = decode_gpkg(row['geom'], srs_id)
        require(geom.geom_type in ('Polygon', 'MultiPolygon') and not geom.is_empty and geom.is_valid,
                f'Invalid source polygon: {fid}: {shapely.is_valid_reason(geom)}')
        projected = valid_polygon(transform(to_area.transform, geom), fid, "EPSG:26918", repairs)
        geo = valid_polygon(transform(to_geo.transform, geom), fid, "EPSG:4326", repairs)
        require(geo.is_valid and not geo.is_empty and projected.is_valid, f'Invalid transformed geometry: {fid}')
        require(all(math.isfinite(x) for x in geo.bounds), f'Nonfinite coordinates: {fid}')
        require(-77.1 < geo.bounds[0] < geo.bounds[2] < -76.7 and 38.8 < geo.bounds[1] < geo.bounds[3] < 39.2,
                f'Unexpected BARC bounds: {fid}')
        # RFC 7946 right-hand rule without repairing or simplifying source shapes.
        if geo.geom_type == 'MultiPolygon':
            geo = shapely.MultiPolygon([orient(p, sign=1.0) for p in geo.geoms])
        else:
            geo = orient(geo, sign=1.0)
        area = projected.area / 10000
        require(math.isfinite(area) and area > 0, f'Non-positive area: {fid}')
        acres = row['ACRES']
        require(acres is not None and acres > 0, f'Missing/non-positive source ACRES: {fid}')
        features_props = dict(field_id=fid, source_field_id=raw_id, source_dataset_id=DATASET,
                              area_ha=round(area, 8), farm_group=farm_id)
        fields.append(dict(type='Feature', id=fid, properties=features_props, geometry=mapping(geo)))
        id_map.append(dict(field_id=fid, source_field_id=raw_id, source_dataset_id=DATASET,
                           source_id_column='OBJECTID', farm_group=farm_id,
                           source_acres=format(acres, '.15g'),
                           source_geometry_sha256=hashlib.sha256(to_wkb(geom)).hexdigest()))
        checks.append(dict(field_id=fid, area_ha=round(area,8), source_acres=acres,
                           source_acres_as_ha=acres*0.40468564224,
                           relative_difference=(area-acres*0.40468564224)/(acres*0.40468564224)))
        for year in YEARS:
            value = row[f'Corn_{year}']
            if value is None or (isinstance(value, str) and not value.strip()):
                missing[str(year)] += 1
            elif value in ('Grain', 'Silage'):
                labels.append(dict(field_id=fid, year=year, label=value.lower(), label_raw=value, source_dataset_id=DATASET))
            else:
                unexpected.append(dict(field_id=fid, year=year, label_raw=value))
    require(not unexpected, f'Unexpected source labels: {unexpected}')
    fields.sort(key=lambda f:f['properties']['field_id'])
    labels.sort(key=lambda r:(r['field_id'], r['year']))
    id_map.sort(key=lambda r:r['field_id'])
    keys = {(r['field_id'], r['year']) for r in labels}
    require(len(keys) == len(labels), 'Duplicate label key')
    require(all(r['field_id'] in seen for r in labels), 'Orphan label')
    # Existing mapping is a registry: never silently change an assigned ID.
    old_map = OUT / 'field_id_map.csv'
    if old_map.exists():
        with old_map.open(newline='') as f:
            old = list(csv.DictReader(f))
        require({r['source_field_id']:r['field_id'] for r in old} ==
                {r['source_field_id']:r['field_id'] for r in id_map}, 'Existing ID registry changed')
    with LEGACY.open(newline='') as f:
        legacy = list(csv.DictReader(f))
    legacy_labels = {(f"barc_{r['field_id']}", int(r['year']), r['harvest_type']) for r in legacy}
    require(len(legacy_labels) == len(legacy) and legacy_labels ==
            {(r['field_id'],r['year'],r['label_raw']) for r in labels}, 'Legacy/source label discrepancy')
    by_id = {r['field_id']:r for r in id_map}
    farm_groups = sorted({by_id[r['field_id']]['farm_group'] for r in labels})
    # One held-out farm per fold, same membership as GroupKFold(n_splits=5).
    # Fold numbering is frozen by sorted source FARM_ID, independent of sklearn versions.
    farm_to_fold = {farm:i for i,farm in enumerate(farm_groups)}
    folds = [dict(field_id=r['field_id'], year=r['year'], fold_id=farm_to_fold[by_id[r['field_id']]['farm_group']]) for r in labels]
    fold_report = []
    for farm, fold in farm_to_fold.items():
        test = [r for r in labels if by_id[r['field_id']]['farm_group'] == farm]
        train = [r for r in labels if by_id[r['field_id']]['farm_group'] != farm]
        require(set(r['label'] for r in train) == {'grain','silage'}, f'One-class training fold: {fold}')
        require(not ({r['field_id'] for r in test} & {r['field_id'] for r in train}), 'Field leakage')
        fold_report.append(dict(fold_id=fold, held_out_farm=farm, test_counts=dict(Counter(r['label'] for r in test)),
                                train_counts=dict(Counter(r['label'] for r in train)),
                                test_fields=len({r['field_id'] for r in test})))
    sample_label = labels[0]
    sample = dict(field_id=sample_label['field_id'], year=sample_label['year'],
                  window_start=f"{sample_label['year']}-04-01", window_end_exclusive=f"{sample_label['year']}-12-01",
                  selection_rule='First labeled record sorted lexicographically by normalized field_id, then numeric year.',
                  source_dataset_id=DATASET)
    write_json(OUT/'fields.geojson',dict(type='FeatureCollection',features=fields))
    write_csv(OUT/'labels.csv',['field_id','year','label','label_raw','source_dataset_id'],labels)
    write_json(OUT/'smoke_sample.json',sample)
    write_csv(OUT/'validation_folds.csv',['field_id','year','fold_id'],folds)
    write_csv(old_map,['field_id','source_field_id','source_dataset_id','source_id_column','farm_group','source_acres','source_geometry_sha256'],id_map)
    write_csv(REPORT/'area_checks.csv',list(checks[0]),sorted(checks,key=lambda r:r['field_id']))
    require(sha(SOURCE) == source_hash,'Source bytes changed')
    output_names = ['fields.geojson','labels.csv','smoke_sample.json','validation_folds.csv','field_id_map.csv']
    report = dict(source_path=str(SOURCE.relative_to(ROOT)),source_sha256=source_hash,
        source_crs_name=source_crs.name,source_srs_id=srs_id,source_crs_wkt=source_crs.to_wkt(),
        source_axis_units=[a.unit_name for a in source_crs.axis_info],area_crs='EPSG:26918',output_crs='EPSG:4326',
        transform_to_area=to_area.description,transform_to_geo=to_geo.description,
        source_fields=len(records), output_fields=len(fields), labeled_field_years=len(labels),
        unique_labeled_fields=len({r['field_id'] for r in labels}),
        by_year={str(y):dict(Counter(r['label'] for r in labels if r['year']==y)) for y in YEARS},
        missing_labels_by_year=dict(missing),unexpected_labels=unexpected,
        duplicate_field_ids=0,duplicate_label_keys=0,orphan_labels=0,legacy_labels_exact_match=True,
        geometry_valid_count=len(fields),positive_area_count=len(fields),geometry_repairs=repairs,
        area_relative_difference_min=min(r['relative_difference'] for r in checks),
        area_relative_difference_max=max(r['relative_difference'] for r in checks),
        area_relative_difference_over_1pct=sum(abs(r['relative_difference'])>0.01 for r in checks),
        total_polygon_area_ha=sum(f['properties']['area_ha'] for f in fields),
        validation_design='leave_one_farm_out; fold_id 0..4 mapped by lexically sorted FARM_ID strings',
        fold_groups=fold_report,smoke_sample=sample,smoke_label=sample_label,
        environment=dict(python=platform.python_version(),shapely=shapely.__version__,pyproj=pyproj.__version__,proj=pyproj.proj_version_str),
        output_sha256={name:sha(OUT/name) for name in output_names},
        not_executed=['Satellite extraction','Model training or metrics','Ground survey validation of geometry/labels','California validation'])
    write_json(REPORT/'acceptance.json',report)
    print(json.dumps({k:report[k] for k in ['source_fields','labeled_field_years','unique_labeled_fields','by_year','missing_labels_by_year','fold_groups','smoke_sample','smoke_label']},indent=2))

if __name__ == '__main__':
    main()
