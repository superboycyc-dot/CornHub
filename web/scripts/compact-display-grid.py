"""Preserve all polygon vertices/IDs with sub-decimeter display coordinates."""
import struct,json,brotli
from pathlib import Path
import numpy as np
root=Path(__file__).resolve().parents[1]/'national';index=json.loads((root/'polygons-index.json').read_text());total=0
for i,tile in enumerate(index['tiles']):
 path=root/tile['path'];data=brotli.decompress(path.read_bytes());assert data[:4]==b'NPG1';out=bytearray(b'NPG2'+data[4:8]);pos=8
 def copy(n):
  global pos
  value=data[pos:pos+n];pos+=n;out.extend(value);return value
 for _ in range(tile['count']):
  header=copy(15);npoly=struct.unpack_from('<I',header,11)[0]
  for p in range(npoly):
   nrings=struct.unpack('<I',copy(4))[0]
   for r in range(nrings):
    n=struct.unpack('<I',copy(4))[0];old=np.frombuffer(data,dtype='<i4',count=n*2,offset=pos).reshape(n,2).cumsum(axis=0,dtype=np.int64);pos+=n*8
    new=np.rint(old/10).astype(np.int64);assert np.max(np.abs(new*10-old),initial=0)<=5
    delta=new.copy();delta[1:]-=new[:-1];out.extend(delta.astype('<i4').tobytes())
 assert pos==len(data) and len(out)==len(data)
 packed=brotli.compress(bytes(out),quality=5);assert brotli.decompress(packed)==out;path.write_bytes(packed);tile['bytes']=len(packed);total+=len(packed)
 if i%300==0:print(json.dumps({'tiles':i,'bytes':total}),flush=True)
index['geometry_format']='NPG2';index['coordinate_scale']=1000000;index['coordinate_rounding_max_degrees']=.0000005
(root/'polygons-index.json').write_text(json.dumps(index,separators=(',',':'))+'\n');print(json.dumps({'complete':True,'bytes':total}),flush=True)
