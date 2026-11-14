import json,csv,sys
from pathlib import Path
import numpy as np,rasterio as rio
from rasterio.features import geometry_mask
from rasterio.windows import from_bounds,Window
from rasterio.warp import transform_geom
from rasterio.vrt import WarpedVRT
from shapely.geometry import shape,mapping
from shapely.ops import unary_union
from contextlib import ExitStack
out=Path(__file__).parent
fields=[f for f in json.load(open(sys.argv[1]))['features'] if f['properties']['gewascode'] in (259,316)]
for f in fields:f['properties']['harvest_label']={259:'silage',316:'grain'}[f['properties']['gewascode']]
(out/'fields.geojson').write_text(json.dumps(dict(type='FeatureCollection',features=fields),ensure_ascii=False))
scenes=sorted(json.load(open(sys.argv[2]))['features'],key=lambda f:f['properties']['eo:cloud_cover'])[:4]
(out/'scenes.json').write_text(json.dumps(scenes))
with (out/'ndvi.csv').open('w') as file:
 w=csv.writer(file);w.writerow(['field_id','label','date','scene','interior_pixels','valid_pixels','ndvi_median'])
 for s in scenes:
  a=s['assets']
  with ExitStack() as st:
   r,n,c=[st.enter_context(rio.open(a[k]['href'])) for k in ('red','nir','scl')]
   v=st.enter_context(WarpedVRT(c,crs=r.crs,transform=r.transform,width=r.width,height=r.height))
   gs=[shape(transform_geom('EPSG:4326',r.crs,f['geometry'])).buffer(-10) for f in fields]
   b=unary_union(gs).bounds
   win=from_bounds(b[0]-20,b[1]-20,b[2]+20,b[3]+20,r.transform).round_offsets().round_lengths()
   R,N,C=[x.read(1,window=win) for x in (r,n,v)]
   def refl(x,k):
    m=a[k]['raster:bands'][0];return x*m['scale']+(0 if s['properties'].get('earthsearch:boa_offset_applied') else m['offset'])
   rr,nn=refl(R,'red'),refl(N,'nir');good=(R>0)&(N>0)&np.isin(C,[4,5])&(nn+rr>0)
   nd=np.divide(nn-rr,nn+rr,out=np.zeros_like(rr),where=good)
   for f,g in zip(fields,gs):
    mask=geometry_mask([mapping(g)],R.shape,r.window_transform(win),invert=True) if not g.is_empty else np.zeros(R.shape,bool)
    vals=nd[mask&good];w.writerow([f['id'],f['properties']['harvest_label'],s['properties']['datetime'][:10],s['id'],mask.sum(),len(vals),round(float(np.median(vals)),5) if len(vals) else ''])
  file.flush();print(s['id'],flush=True)
