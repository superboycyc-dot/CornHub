"""Save a few real crop arrays and boundary overlays for independent QA."""
import json, math
from pathlib import Path
import numpy as np
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from rasterio.io import MemoryFile
from rasterio.transform import Affine
from rasterio.warp import transform_geom
from rasterio.windows import from_bounds
from rasterio.features import geometry_mask
from shapely.geometry import shape,mapping,box
from v2_acquire import REPORT,CACHE,PC,get,calibration,write_json,VERSION

def main():
    fields=json.loads((REPORT/'selected_fields.geojson').read_text())['features'];byid={f['properties']['entity_id']:f for f in fields}
    scene_items={}
    for p in (CACHE/'catalog').glob('*.json'):
        for i in json.loads(p.read_text())['features']:scene_items[i['id']]=i
    receipts=[json.loads(p.read_text()) for p in (CACHE/'observations').glob('*.json')];receipts=[r for r in receipts if r.get('algorithm_version')==VERSION]
    chosen=[]
    for region in ['be2','be3','bg','si']:
        candidates=[r for r in receipts if f'_{region}_' in r['entity_id'] and r['ndvi'] is not None and r['ndvi_valid_fraction']>=.5]
        if candidates:chosen.append(sorted(candidates,key=lambda r:(r['entity_id'],r['date']))[0])
    checks=[];folder=REPORT/'alignment_evidence';folder.mkdir(exist_ok=True)
    for r in chosen:
        item=scene_items[r['scene_id']];field=byid[r['entity_id']];crs=r['grid_crs'];grid=Affine(*r['grid_transform']);h,w=r['grid_shape'];cal=r['calibration']
        rectangle=mapping(box(grid.c,grid.f+h*grid.e,grid.c+w*grid.a,grid.f))
        params=[('collection','sentinel-2-l2a'),('item',item['id'])]+[('assets',b) for b in ['B04','B08','B11','SCL']]+[('coord_crs',crs),('dst_crs',crs),('width',w),('height',h),('resampling','nearest'),('reproject','nearest'),('unscale','false')]
        response=get('POST',PC+'/api/data/v1/item/feature.tif',params=params,json=dict(type='Feature',properties={},geometry=rectangle))
        with MemoryFile(response.content) as mem:
            with mem.open() as ds:
                assert ds.transform.almost_equals(grid) and ds.shape==(h,w) and str(ds.crs)==crs
                raw=ds.read([1,2,3,4],masked=False).astype(float)
        polygon=shape(transform_geom('EPSG:4326',crs,field['geometry']));interior=polygon.buffer(-10)
        mask=geometry_mask([mapping(interior)],out_shape=(h,w),transform=grid,invert=True,all_touched=False)
        bands=raw[:3].copy();bands[bands==cal['nodata']]=np.nan
        for n,k in enumerate(['B04','B08','B11']):bands[n]=(bands[n]+cal['offsets'][k])/cal['quantification']
        with np.errstate(invalid='ignore',divide='ignore'):ndvi=(bands[1]-bands[0])/(bands[1]+bands[0]);ndmi=(bands[1]-bands[2])/(bands[1]+bands[2])
        for ix,data,other in [('ndvi',ndvi,0),('ndmi',ndmi,2)]:
            valid=mask & np.isin(raw[3],[4,5,6,7]) & np.isfinite(data)&np.isfinite(bands[1])&np.isfinite(bands[other])&((bands[1]+bands[other])>1e-12)&(data>=-1)&(data<=1)
            assert int(valid.sum())==r[ix+'_valid_pixels'];assert int(mask.sum())==r[ix+'_total_pixels']
            if valid.sum()>=3:assert math.isclose(float(np.median(data[valid])),r[ix],rel_tol=1e-12)
        name=r['entity_id']+'_'+r['date'];np.savez_compressed(folder/(name+'.npz'),raw_dn=raw,reflectance=bands,inside=mask,ndvi=ndvi,ndmi=ndmi,grid=np.array(r['grid_transform']))
        fig,axs=plt.subplots(1,3,figsize=(10,3));extent=(grid.c,grid.c+w*10,grid.f-h*10,grid.f)
        for ax,data,title in zip(axs,[bands[0],ndvi,raw[3]],['B04 reflectance','NDVI','SCL nearest']):
            ax.imshow(data,extent=extent,origin='upper',interpolation='nearest');ax.set_title(title)
            for g,color in [(polygon,'red'),(interior,'cyan')]:
                for part in (list(g.geoms) if g.geom_type=='MultiPolygon' else [g]):
                    if not part.is_empty:x,y=part.exterior.xy;ax.plot(x,y,color=color,lw=.8)
            ax.ticklabel_format(style='plain',useOffset=False);ax.tick_params(labelsize=6)
        fig.suptitle(name,fontsize=8);fig.tight_layout();fig.savefig(folder/(name+'.png'),dpi=130);plt.close(fig)
        checks.append(dict(entity_id=r['entity_id'],scene_id=r['scene_id'],native_grid_checked=True,independent_pixel_counts_and_medians_match=True,array_file=name+'.npz',overlay_file=name+'.png',overlay_rule='red=original;cyan=10m interior;image grid B04 native10m'))
    write_json(folder/'checks.json',checks);print('Independent real-array QA',len(checks))
if __name__=='__main__':main()
