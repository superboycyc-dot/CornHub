"""Verify raw archives and record acquisition details without storing archives in Git."""
import hashlib,json,zipfile
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
items=[('csb','NationalCSB_2016-2023_rev23.zip','https://www.nass.usda.gov/sites/default/files/Research_and_Science/Crop-Sequence-Boundaries/datasets/NationalCSB_2016-2023_rev23.zip',3505346935,None,'U.S. Public Domain'),('cropsight','cropsight-us_app_dat_v1.0.1.zip','https://zenodo.org/api/records/19501943/files/cropsight-us_app_dat_v1.0.1.zip/content',297267115,'8df463cd8d09210354a6e31f8cdcada7','CC-BY-4.0')]
result=[]
for kind,name,url,size,md5,license in items:
 path=ROOT/'data/raw/external_corn'/name
 assert path.stat().st_size==size
 h=hashlib.sha256();m=hashlib.md5()
 with path.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b);m.update(b)
 if md5:assert m.hexdigest()==md5
 with zipfile.ZipFile(path) as z:
  assert z.testzip() is None
  contents=[{'name':v.filename,'bytes':v.file_size} for v in z.infolist()]
  if kind=='csb':
   metadata=next(v.filename for v in z.infolist() if v.filename.endswith('.htm'))
   (ROOT/'reports/a_data/external_corn/csb_official_metadata.htm').write_text('\n'.join(line.rstrip() for line in z.read(metadata).decode('utf-8-sig').splitlines())+'\n')
 result.append(dict(dataset=kind,url=url,local_path=str(path.relative_to(ROOT)),bytes=size,uncompressed_bytes=sum(v['bytes'] for v in contents),sha256=h.hexdigest(),md5=m.hexdigest(),publisher_md5_verified=bool(md5),zip_crc='passed',license=license,verified_at_utc=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),contents=contents))
 print(kind,'raw verified',flush=True)
(ROOT/'reports/a_data/external_corn/sources_manifest.json').write_text(json.dumps(result,indent=2)+'\n')
