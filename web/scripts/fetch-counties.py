"""Refresh the packaged US Census county context layer; no field IDs or predictions."""
import json,hashlib,urllib.request,urllib.parse
from pathlib import Path
from datetime import datetime,timezone
BASE='https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer/9'
params={'where':'1=1','outFields':'GEOID,NAME,STATE,INTPTLAT,INTPTLON','outSR':'4326','returnGeometry':'true','maxAllowableOffset':'0.002','geometryPrecision':'5','f':'geojson'}
def get(url):
    with urllib.request.urlopen(url,timeout=90) as r:return json.load(r)
url=BASE+'/query?'+urllib.parse.urlencode(params)
data=get(url)
count=get(BASE+'/query?where=1%3D1&returnCountOnly=true&f=json')['count']
if data.get('type')!='FeatureCollection' or len(data.get('features',[]))!=count or data.get('exceededTransferLimit'):raise RuntimeError('Incomplete Census response')
seen=set()
for f in data['features']:
    geoid=f['properties']['GEOID']
    if not isinstance(geoid,str) or geoid in seen:raise ValueError('Invalid/duplicate county GEOID')
    seen.add(geoid)
    points=[]
    def walk(c):
        if isinstance(c[0],(int,float)):points.append(c)
        else:
            for child in c:walk(child)
    walk(f['geometry']['coordinates'])
    if any(not(-180<=p[0]<=180 and -90<=p[1]<=90) for p in points):raise ValueError('Invalid coordinates')
    f['bbox']=[min(p[0] for p in points),min(p[1] for p in points),max(p[0] for p in points),max(p[1] for p in points)]
data['features'].sort(key=lambda f:f['properties']['GEOID'])
root=Path(__file__).resolve().parents[1]/'reference';root.mkdir(exist_ok=True)
content=(json.dumps(data,separators=(',',':'))+'\n').encode()
(root/'us-counties.geojson').write_bytes(content)
metadata={'organization':'U.S. Census Bureau','source_url':url,'layer_url':BASE,'vintage':'2026-01-01','retrieved_at_utc':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'feature_count':count,'sha256':hashlib.sha256(content).hexdigest(),'crs':'EPSG:4326','generalization_degrees':0.002,'notes':'Generalized administrative context, not historical crop-year boundaries or a cadastral survey. County GEOID is independent of CornHub field_id. Source: U.S. Census Bureau.'}
(root/'us-counties.source.json').write_text(json.dumps(metadata,indent=2)+'\n')
print(json.dumps({'feature_count':count,'bytes':len(content),'sha256':metadata['sha256']}))
