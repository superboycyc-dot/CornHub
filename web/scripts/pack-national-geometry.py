"""Pack all existing display vertices into exact 1e-7 degree grid deltas."""
import json,brotli,struct
from pathlib import Path
import numpy as np
root=Path(__file__).resolve().parents[1]/'national';idx=json.loads((root/'polygons-index.json').read_text());total=0;vertices=0
for ti,tile in enumerate(idx['tiles']):
 src=root/tile['path'];text=brotli.decompress(src.read_bytes()).decode();out=bytearray(b'NPG1'+struct.pack('<I',tile['count']));count=0
 for line in text.splitlines():
  if not line:continue
  cid,flags,g=json.loads(line);prefix='cropsight_' if flags&16 else 'csb_';sid=cid[len(prefix):];assert cid==prefix+sid
  kind=1 if g['type']=='Polygon' else 2;assert g['type'] in ['Polygon','MultiPolygon'];parts=[g['coordinates']] if kind==1 else g['coordinates']
  out+=struct.pack('<QBBBI',int(sid),len(sid),flags,kind,len(parts))
  for poly in parts:
   out+=struct.pack('<I',len(poly))
   for ring in poly:
    xy=np.array(ring)[:,:2];q=np.rint(xy*1e7).astype(np.int64);assert np.max(np.abs(q/1e7-xy),initial=0)<1e-10
    delta=q.copy();delta[1:]-=q[:-1];assert np.all(delta>=-2147483648) and np.all(delta<=2147483647)
    out+=struct.pack('<I',len(q))+delta.astype('<i4').tobytes();vertices+=len(q)
  count+=1
 assert count==tile['count'];packed=brotli.compress(bytes(out),quality=5);assert brotli.decompress(packed)==out
 dest=src.with_name(src.name.replace('.ndjson.br','.npg.br'));dest.write_bytes(packed);tile['path']=dest.relative_to(root).as_posix();tile['bytes']=len(packed);src.unlink();total+=len(packed)
 if ti%200==0:print(json.dumps({'tiles':ti,'of':len(idx['tiles']),'bytes':total}),flush=True)
idx['geometry_format']='NPG1';idx['coordinate_scale']=10000000;idx['vertices']=vertices;idx['notes']+=' NPG1 stores every display vertex on the existing 1e-7 degree grid; no further simplification or vertex omission.'
(root/'polygons-index.json').write_text(json.dumps(idx,separators=(',',':'))+'\n');print(json.dumps({'complete':True,'bytes':total,'vertices':vertices}),flush=True)
