"""Display geometry from original candidate polygons; never invent rectangles."""
import gzip,hashlib,io,json,subprocess,math
from pathlib import Path
import numpy as np,pyarrow.parquet as pq,shapely
ROOT=Path(__file__).resolve().parents[2];REF='83fc31f4a6f1fcd3555935c9fb4b286665b8b9ee';Z=9;N=2**Z
out=ROOT/'web/national/polygons';out.mkdir(exist_ok=True)
spool=ROOT.parent/'work/polygon-spool';spool.mkdir(exist_ok=True)
git=subprocess.Popen(['git','cat-file','--batch'],cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE)
def blob(p):
 git.stdin.write(f'{REF}:{p}\n'.encode());git.stdin.flush();h=git.stdout.readline().split();assert len(h)==3;d=git.stdout.read(int(h[2]));assert git.stdout.read(1)==b'\n';return d
stats={};total=0
for kind in ['csb','cropsight']:
 report=json.loads(blob(f'reports/a_data/external_corn/{kind}_processing.json'))
 for si,shard in enumerate(report['shards']):
  raw=blob(shard['path']);assert hashlib.sha256(raw).hexdigest()==shard['sha256'];t=pq.read_table(io.BytesIO(raw));n=t.num_rows
  geom=shapely.from_wkb(t['geometry'].to_pylist());bounds=shapely.bounds(geom);lon=(bounds[:,0]+bounds[:,2])/2;lat=(bounds[:,1]+bounds[:,3])/2
  simplified=shapely.simplify(geom,.0001,preserve_topology=True)
  geometry_json=shapely.to_geojson(shapely.set_precision(simplified,1e-7,mode="pointwise"))
  tx=np.floor((lon+180)/360*N).astype(int);ty=np.floor((1-np.arcsinh(np.tan(np.radians(lat)))/np.pi)/2*N).astype(int)
  ids=t['candidate_id'].to_pylist();valid=t['geometry_valid'].to_pylist();flags=np.array(valid,dtype='u1')*8+(16 if kind=='cropsight' else 0)
  for j,y in enumerate([2021,2022,2023]):flags|=(np.array(t[f'cdl{y}'].to_pylist())==1 if kind=='csb' else np.array(t['year'].to_pylist())==y).astype('u1')*(1<<j)
  buffers={}
  for i in range(n):
   key=f'{tx[i]}-{ty[i]}';line='['+json.dumps(ids[i])+','+str(int(flags[i]))+','+geometry_json[i]+']\n';buffers.setdefault(key,[]).append(line)
   st=stats.setdefault(key,{'x':int(tx[i]),'y':int(ty[i]),'count':0,'bbox':[180.,90.,-180.,-90.]});st['count']+=1;b=st['bbox'];bb=bounds[i];st['bbox']=[min(b[0],float(bb[0])),min(b[1],float(bb[1])),max(b[2],float(bb[2])),max(b[3],float(bb[3]))]
  for key,lines in buffers.items():
   with (spool/(key+'.ndjson.gz')).open('ab') as f:f.write(gzip.compress(''.join(lines).encode(),compresslevel=1,mtime=0))
  total+=n
  if si%100==0:print(json.dumps({'kind':kind,'shard':si,'polygons':total}),flush=True)
files=[]
for key,st in sorted(stats.items()):
 src=spool/(key+'.ndjson.gz');dest=out/(key+'.ndjson.gz')
 with gzip.open(src,'rb') as source,gzip.GzipFile(filename=str(dest),mode='wb',compresslevel=6,mtime=0) as target:
  import shutil;shutil.copyfileobj(source,target)
 st['path']='polygons/'+dest.name;st['bytes']=dest.stat().st_size;files.append(st);src.unlink()
index={'source_commit':REF,'objects':total,'display_simplification_degrees':.0001,'notes':'Actual source polygon shapes with topology-preserving display simplification; no bounding boxes substituted; invalid-source flags retained.','tiles':files}
(ROOT/'web/national/polygons-index.json').write_text(json.dumps(index,separators=(',',':'))+'\n');print(json.dumps({'complete':True,'polygons':total,'tiles':len(files),'bytes':sum(f['bytes'] for f in files)}),flush=True)
