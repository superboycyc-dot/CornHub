"""Build an on-demand display-point index from A's exact national handoff.
Does not create field_id, model predictions, or surveyed parcel boundaries.
"""
import argparse,gzip,hashlib,io,json,math,shutil,struct,subprocess,time
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
import pyarrow.parquet as pq
import shapely
ROOT=Path(__file__).resolve().parents[2]
REF='83fc31f4a6f1fcd3555935c9fb4b286665b8b9ee'
ZOOM=7;SIZE=2**ZOOM
DTYPE=np.dtype([('id','<u8'),('x','<u2'),('y','<u2'),('flags','u1'),('length','u1')])
assert DTYPE.itemsize==14
parser=argparse.ArgumentParser();parser.add_argument('--output',default=str(ROOT/'web/national'));parser.add_argument('--scratch',default=str(ROOT.parent/'work/national-spool'));args=parser.parse_args()
out=Path(args.output);spool=Path(args.scratch);spool.mkdir(parents=True,exist_ok=True)
if list(spool.glob('*.raw')):raise RuntimeError('Scratch is not empty; use a new scratch directory')
(out/'tiles').mkdir(parents=True,exist_ok=True)
git=subprocess.Popen(['git','cat-file','--batch'],cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE)
def blob(name):
 git.stdin.write(f'{REF}:{name}\n'.encode());git.stdin.flush();head=git.stdout.readline().decode().strip().split()
 if len(head)!=3 or head[1]!='blob':raise RuntimeError('Missing source '+name)
 data=git.stdout.read(int(head[2]));assert git.stdout.read(1)==b'\n';return data
stats={};sources=[];started=time.monotonic();total=0
for kind in ['csb','cropsight']:
 report=json.loads(blob(f'reports/a_data/external_corn/{kind}_processing.json'))
 n_source=0;source_counts=[0,0,0];invalid=0
 for i,shard in enumerate(report['shards']):
  raw=blob(shard['path']);assert hashlib.sha256(raw).hexdigest()==shard['sha256'],shard['path']
  table=pq.read_table(io.BytesIO(raw));assert table.num_rows==shard['rows'];n=table.num_rows
  ids=table['source_field_id'].to_pylist();candidate=table['candidate_id'].to_pylist()
  if any(not v.isascii() or not v.isdigit() or not 1<=len(v)<=20 for v in ids):raise ValueError('Source ID cannot be losslessly packed')
  if any(candidate[j]!=kind+'_'+v for j,v in enumerate(ids)):raise ValueError('A candidate ID mapping differs')
  integers=np.array([int(v) for v in ids],dtype='<u8');lengths=np.array([len(v) for v in ids],dtype='u1')
  assert all(str(int(integers[j])).zfill(int(lengths[j]))==v for j,v in enumerate(ids))
  valid=np.array(table['geometry_valid'].to_pylist(),dtype=bool);invalid+=int((~valid).sum())
  bounds=shapely.bounds(shapely.from_wkb(table['geometry'].to_pylist()));lon=(bounds[:,0]+bounds[:,2])/2;lat=(bounds[:,1]+bounds[:,3])/2
  if not np.isfinite(bounds).all() or np.any(np.abs(lon)>180) or np.any(np.abs(lat)>85):raise ValueError('Invalid display-point coordinates')
  flags=valid.astype('u1')*8+(16 if kind=='cropsight' else 0)
  for j,year in enumerate([2021,2022,2023]):
   annual=np.array(table[f'cdl{year}'].to_pylist())==1 if kind=='csb' else np.array(table['year'].to_pylist())==year
   flags |= annual.astype('u1')*(1<<j);source_counts[j]+=int(annual.sum())
  assert np.all(flags&7)
  mx=(lon+180)/360*SIZE;my=(1-np.arcsinh(np.tan(np.radians(lat)))/np.pi)/2*SIZE
  tx=np.floor(mx).astype(int);ty=np.floor(my).astype(int)
  records=np.empty(n,dtype=DTYPE);records['id']=integers;records['length']=lengths;records['flags']=flags
  records['x']=np.rint((mx-tx)*65535).astype('<u2');records['y']=np.rint((my-ty)*65535).astype('<u2')
  codes=tx+SIZE*ty
  for code in np.unique(codes):
   mask=codes==code;part=records[mask];x=int(code%SIZE);y=int(code//SIZE);key=f'{x}-{y}'
   with (spool/(key+'.raw')).open('ab') as f:f.write(part.tobytes())
   stat=stats.setdefault(key,{'x':x,'y':y,'count':0,'year_counts':{'2021':0,'2022':0,'2023':0},'sum_lon':0.,'sum_lat':0.,'geometry_invalid_count':0})
   stat['count']+=len(part);stat['sum_lon']+=float(lon[mask].sum());stat['sum_lat']+=float(lat[mask].sum());stat['geometry_invalid_count']+=int(((part['flags']&8)==0).sum())
   for j,year in enumerate(['2021','2022','2023']):stat['year_counts'][year]+=int(((part['flags']&(1<<j))!=0).sum())
  n_source+=n;total+=n
  if i%50==0:print(json.dumps({'source':kind,'shard':i+1,'of':len(report['shards']),'indexed':total,'seconds':round(time.monotonic()-started)}),flush=True)
 assert n_source==report['selected_rows']
 sources.append({'source_dataset_id':kind+'_corn_2021_2023','candidate_prefix':kind+'_','objects':n_source,'geometry_invalid_count':invalid,'year_counts':dict(zip(['2021','2022','2023'],source_counts)),'upstream_processing_report':f'reports/a_data/external_corn/{kind}_processing.json'})
git.stdin.close();git.wait()
tiles=[];compressed=0
for key,stat in sorted(stats.items()):
 raw=(spool/(key+'.raw')).read_bytes();rows=np.frombuffer(raw,dtype=DTYPE);order=np.lexsort((rows['id'],rows['flags']&16));rows=rows[order]
 packed=b'NFD1'+struct.pack('<I',len(rows))+rows.tobytes();encoded=gzip.compress(packed,compresslevel=9,mtime=0)
 assert gzip.decompress(encoded)==packed
 dest=out/'tiles'/str(stat['x'])/(str(stat['y'])+'.bin.gz');dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(encoded)
 stat['center']=[stat.pop('sum_lat')/stat['count'],stat.pop('sum_lon')/stat['count']];stat['bytes']=len(encoded);stat['sha256']=hashlib.sha256(encoded).hexdigest();stat['path']=f"tiles/{stat['x']}/{stat['y']}.bin.gz";tiles.append(stat);compressed+=len(encoded)
assert sum(t['count'] for t in tiles)==total
metadata={'format':'NFD1','record_bytes':14,'tile_zoom':ZOOM,'source_commit':REF,'source_repository':'superboycyc-dot/CornHub','object_count':total,'sources':sources,'tiles':tiles,'compressed_bytes':compressed,'created_at_utc':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'geometry_representation':'Quantized bounding-box center display points, not polygon outlines or surveyed field centers. Up to about 2.4 m coordinate quantization error at the equator. Original geometry_valid flag retained.','scope':'CSB contiguous US candidate polygons and CropSight corn observation objects, 2021–2023; sources may overlap and are not merged. No silage/grain ground truth or national predictions.','prediction_key':['source_dataset_id','candidate_id','year','prediction_role','model_version'],'attribution':['USDA NASS Crop Sequence Boundaries 2016–2023 rev23, U.S. Public Domain','Zhou, Liu & Diao, CropSight-US v1.0.1, CC-BY-4.0, https://doi.org/10.5194/essd-18-3069-2026']}
(out/'index.json').write_text(json.dumps(metadata,separators=(',',':'))+'\n')
(ROOT/'reports/e_web/national-index-validation.json').write_text(json.dumps({'status':'verified','objects':total,'sources':sources,'tiles':len(tiles),'compressed_bytes':compressed,'source_commit':REF,'checks':['Every shard SHA-256 and row count matches A processing report','Every candidate ID reconstructed exactly from A source_field_id, with leading zero length preserved','Every object assigned to one display tile with original annual eligibility and geometry-valid flag','No rows omitted or predictions synthesized','Each compressed tile decompressed byte-exactly and output counts match source totals'],'browser_verification':'Not performed; supported browser tool unavailable'},indent=2)+'\n')
print(json.dumps({'complete':True,'objects':total,'tiles':len(tiles),'compressed_bytes':compressed,'seconds':round(time.monotonic()-started)}),flush=True)
