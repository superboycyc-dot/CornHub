"""Use compact regional overview, avoiding unused individual-point transport."""
import json,gzip,brotli,math
from pathlib import Path
import numpy as np
root=Path(__file__).resolve().parents[1]/'national';old=json.loads((root/'index.json').read_text());dtype=np.dtype([('id','<u8'),('x','<u2'),('y','<u2'),('flags','u1'),('length','u1')]);stats={}
for tile in old['tiles']:
 raw=gzip.decompress((root/tile['path']).read_bytes());rows=np.frombuffer(raw,dtype=dtype,offset=8);x=(tile['x']+rows['x']/65535)/128;y=(tile['y']+rows['y']/65535)/128;xx=np.minimum(np.floor(x*512).astype(int),511);yy=np.minimum(np.floor(y*512).astype(int),511);codes=xx+yy*512
 for code in np.unique(codes):
  mask=codes==code;st=stats.setdefault(int(code),{'x':int(code%512),'y':int(code//512),'count':0,'year_counts':{'2021':0,'2022':0,'2023':0},'lon':0.,'lat':0.});st['count']+=int(mask.sum());st['lon']+=float((x[mask]*360-180).sum());st['lat']+=float((np.arctan(np.sinh(np.pi*(1-2*y[mask])))*180/np.pi).sum())
  for j,yr in enumerate(['2021','2022','2023']):st['year_counts'][yr]+=int(((rows['flags'][mask]&(1<<j))!=0).sum())
for st in stats.values():st['center']=[st.pop('lat')/st['count'],st.pop('lon')/st['count']]
assert sum(s['count'] for s in stats.values())==old['object_count']
(root/'overview.json').write_text(json.dumps({'source_commit':old['source_commit'],'tile_zoom':9,'tiles':list(stats.values()),'objects':old['object_count'],'notes':'Regional counted clusters, not individual field locations. Full IDs and shapes are in polygon tiles.'},separators=(',',':'))+'\n')
index=json.loads((root/'polygons-index.json').read_text());total=0
for i,t in enumerate(index['tiles']):
 p=root/t['path'];data=brotli.decompress(p.read_bytes());packed=brotli.compress(data,quality=8);assert brotli.decompress(packed)==data;p.write_bytes(packed);t['bytes']=len(packed);total+=len(packed)
 if i%300==0:print(json.dumps({'repacked':i,'bytes':total}),flush=True)
(root/'polygons-index.json').write_text(json.dumps(index,separators=(',',':'))+'\n');print(json.dumps({'complete':True,'polygon_bytes':total}),flush=True)
