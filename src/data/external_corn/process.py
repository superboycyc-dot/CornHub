"""Stream public vector inputs to versioned, bounded GeoParquet corn shards."""
import argparse,hashlib,json,zipfile
from collections import Counter
from pathlib import Path
import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
import pyogrio
import shapely
from pyproj import CRS,Transformer

ROOT=Path(__file__).resolve().parents[3]
def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
 return h.hexdigest()

def main():
 ap=argparse.ArgumentParser();ap.add_argument('kind',choices=['csb','cropsight']);ap.add_argument('path');args=ap.parse_args()
 layers=pyogrio.list_layers(args.path);layer=layers[0][0]
 info=pyogrio.read_info(args.path,layer=layer)
 names={x.lower():x for x in info['fields']}
 if args.kind=='csb':
  cols=[names[f'cdl{y}'] for y in (2021,2022,2023)]
  where=' OR '.join(f'"{c}" = 1' for c in cols)
 else:
  cols=[names['label'],names['year']];where=f'"{cols[1]}" IN (2021,2022,2023)'
 out=ROOT/'data/processed/external_corn'/args.kind;out.mkdir(parents=True,exist_ok=True)
 if list(out.rglob('*.parquet')):raise ValueError('Refusing to overwrite existing processed shards')
 rows=0;invalid=0;year_counts=Counter();manifest=[];seen=set()
 with pyogrio.open_arrow(args.path,layer=layer,where=where,batch_size=5000,return_fids=True,use_pyarrow=True) as (meta,reader):
  for batch in reader:
   table=pa.Table.from_batches([batch]);geomname=meta['geometry_name'] or 'wkb_geometry'
   if args.kind=='csb':
    codes={y:table[names[f'cdl{y}']].to_pylist() for y in (2021,2022,2023)}
    mask=np.array([any(codes[y][i]==1 for y in codes) for i in range(len(table))])
   else:
    labels=table[cols[0]].to_pylist();mask=np.array([str(v).strip().lower() in ('corn','maize') for v in labels])
   table=table.filter(pa.array(mask))
   if not len(table):continue
   geom=shapely.from_wkb(table[geomname].to_pylist())
   crs=CRS.from_user_input(meta['crs']);t=Transformer.from_crs(crs,4326,always_xy=True)
   geo=shapely.transform(geom,t.transform,interleaved=False)
   t_area=Transformer.from_crs(crs,5070,always_xy=True)
   projected=shapely.transform(geom,t_area.transform,interleaved=False)
   valid=shapely.is_valid(geo);area=shapely.area(projected)/10000
   if np.any(shapely.is_missing(geo)) or np.any(~np.isfinite(area)) or np.any(area<=0):raise ValueError('Missing geometry or invalid area')
   invalid+=int((~valid).sum())
   fidname=meta['fid_column'] or 'OGC_FID'
   if args.kind=='csb' and 'csbid' in names:ids=[str(v) for v in table[names['csbid']].to_pylist()]
   else:ids=[str(v) for v in table[fidname].to_pylist()]
   if len(set(ids))!=len(ids) or set(ids)&seen:raise ValueError('Duplicate source IDs')
   seen.update(ids)
   data={'candidate_id':[args.kind+'_'+v for v in ids],'source_field_id':ids,'source_dataset_id':[args.kind+'_corn_2021_2023']*len(ids),'area_ha':area,'geometry_valid':valid,'geometry':shapely.to_wkb(geo).tolist()}
   if args.kind=='csb':
    for lower in ['statefips','cntyfips','cnty']:
     if lower in names:data[lower]=table[names[lower]].to_pylist()
    for y in (2021,2022,2023):
     values=table[names[f'cdl{y}']].to_pylist();data[f'cdl{y}']=values;year_counts[str(y)]+=sum(v==1 for v in values)
   else:
    years=[int(v) for v in table[cols[1]].to_pylist()];data['year']=years;data['crop_label_raw']=table[cols[0]].to_pylist();year_counts.update(map(str,years))
    for lower in ['confidence','entropy','variance','month']:
     if lower in names:data[lower]=table[names[lower]].to_pylist()
   data['harvest_type']=[None]*len(ids)
   result=pa.table(data)
   geo_meta={'version':'1.0.0','primary_column':'geometry','columns':{'geometry':{'encoding':'WKB','geometry_types':sorted(set(shapely.get_type_id(geo).astype(str))),'crs':CRS.from_epsg(4326).to_json_dict()}}}
   # GeoParquet geometry type names, not GEOS integer codes.
   geo_meta['columns']['geometry']['geometry_types']=sorted(set(shapely.get_type_id(geo).tolist()))
   type_names={0:'Point',1:'LineString',2:'LinearRing',3:'Polygon',4:'MultiPoint',5:'MultiLineString',6:'MultiPolygon',7:'GeometryCollection'}
   geo_meta['columns']['geometry']['geometry_types']=[type_names[v] for v in geo_meta['columns']['geometry']['geometry_types']]
   result=result.replace_schema_metadata({b'geo':json.dumps(geo_meta).encode()})
   path=out/f'batch-{len(manifest)//100:03d}'/f'part-{len(manifest):05d}.parquet';path.parent.mkdir(parents=True,exist_ok=True);pq.write_table(result,path,compression='zstd')
   if path.stat().st_size>50_000_000:raise ValueError('Shard exceeds intended Git file size; reduce batch_size')
   manifest.append({'path':str(path.relative_to(ROOT)),'rows':len(result),'bytes':path.stat().st_size,'sha256':digest(path)})
   rows+=len(result)
   print(args.kind,'rows',rows,'shards',len(manifest),flush=True)
 report={'kind':args.kind,'layer':layer,'source_feature_count':info['features'],'selected_rows':rows,'corn_field_year_counts':dict(year_counts),'duplicate_source_ids':0,'geometry_invalid_count_preserved':invalid,'source_crs':str(info['crs']),'output_crs':'EPSG:4326','area_crs':'EPSG:5070','geometry_policy':'No repairs or simplification; invalid geometries retained with geometry_valid=false','harvest_type':'unknown for all rows; not S/G training labels','shards':manifest}
 (ROOT/'reports/a_data/external_corn'/f'{args.kind}_processing.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
