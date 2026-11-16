"""Lossless transport recompression; retains byte-identical NDJSON geometry."""
from pathlib import Path
import gzip,brotli,json,hashlib
root=Path(__file__).resolve().parents[1]/'national';index=json.loads((root/'polygons-index.json').read_text());total=0
for i,tile in enumerate(index['tiles']):
 src=root/tile['path'];data=gzip.decompress(src.read_bytes());packed=brotli.compress(data,quality=6);assert brotli.decompress(packed)==data
 dest=src.with_suffix('.br');dest.write_bytes(packed);tile['path']=dest.relative_to(root).as_posix();tile['bytes']=len(packed);tile['sha256']=hashlib.sha256(packed).hexdigest();src.unlink();total+=len(packed)
 if i%200==0:print(json.dumps({'compressed':i,'of':len(index['tiles'])}),flush=True)
index['compression']='brotli';(root/'polygons-index.json').write_text(json.dumps(index,separators=(',',':'))+'\n')
print(json.dumps({'complete':True,'bytes':total}),flush=True)
