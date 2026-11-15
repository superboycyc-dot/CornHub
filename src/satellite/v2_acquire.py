"""Real PC STAC + metadata-driven, native-grid small-window pilot acquisition."""
import argparse, hashlib, json, math, sys, time, traceback, threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit
import xml.etree.ElementTree as ET
import requests
import numpy as np
import rasterio
from rasterio.io import MemoryFile
from rasterio.transform import Affine
from rasterio.features import geometry_mask
from rasterio.windows import from_bounds
from rasterio.warp import transform_geom
from shapely.geometry import shape, mapping, box
from global_v2 import OUT, REPORT, write_json, write_csv, sha

PC='https://planetarycomputer.microsoft.com'
CAT=PC+'/api/stac/v1'
CACHE=REPORT/'.cache'
VERSION='global-v2-xml-erosion10-nearest-min3-v2'
TOKENS={}
TOKEN_LOCK=threading.Lock()
def now():return datetime.now(timezone.utc).isoformat()
def get(method,url,**kwargs):
    for attempt in range(3):
        try:
            r=requests.request(method,url,timeout=(10,45),**kwargs)
            if r.status_code in [429,500,502,503,504]:
                if attempt<2:time.sleep(max(2**attempt,min(float(r.headers.get('Retry-After',0)),30)));continue
            r.raise_for_status();return r
        except requests.RequestException:
            if attempt==2:raise
            time.sleep(2**attempt)
def clean(url):
    s=urlsplit(url);return urlunsplit((s.scheme,s.netloc,s.path,'',''))
def write_scene_manifest(path,document):
    # Preserve a completed bounded gap-fill pass when replaying initial acquisition.
    previous=json.loads(path.read_text()) if path.exists() else {'scenes':[]}
    merged={x['scene_id']:x for x in previous['scenes']}
    merged.update({x['scene_id']:x for x in document['scenes']})
    document['scenes']=sorted(merged.values(),key=lambda x:x['scene_id'])
    write_json(path,document)
def signed(url):
    # Official container-token endpoint avoids one signing request per product.
    # Tokens remain in memory only and are never returned to provenance/logging.
    parts=urlsplit(url);account=parts.netloc.split('.')[0];container=parts.path.split('/')[1];key=(account,container)
    with TOKEN_LOCK:
        if key not in TOKENS or time.time()-TOKENS[key][0]>1800:
            token=get('GET',PC+f'/api/sas/v1/token/{account}/{container}').json()['token']
            TOKENS[key]=(time.time(),token)
    return clean(url)+'?'+TOKENS[key][1]
def catalog(field):
    eid=field['properties']['entity_id'];year=field['properties']['year']
    query=dict(collections=['sentinel-2-l2a'],intersects=field['geometry'],datetime=f'{year}-04-01T00:00:00Z/{year}-11-30T23:59:59.999999Z',limit=500)
    key=hashlib.sha256(json.dumps(query,sort_keys=True).encode()).hexdigest()
    target=CACHE/'catalog'/f'{key}.json'
    if target.exists():return json.loads(target.read_text())
    page=get('POST',CAT+'/search',json=query).json();items=page['features'];seen=set()
    while True:
        nxt=next((l for l in page.get('links',[]) if l['rel']=='next'),None)
        if not nxt:break
        url=nxt['href'];method=nxt.get('method','GET').upper()
        if not url.startswith(CAT+'/') or url in seen:raise ValueError('Invalid pagination')
        seen.add(url);page=get(method,url,**({'json':nxt.get('body',query)} if method=='POST' else {})).json();items+=page['features']
    # Dedupe physical products before temporal selection, highest baseline/generation.
    unique={}
    for i in items:
        prop=i['properties'];day=prop['datetime'][:10]
        if not f'{year}-04-01'<=day<f'{year}-12-01':raise ValueError('Out of window')
        key=(prop['datetime'],prop['s2:mgrs_tile'])
        if key not in unique or (prop.get('s2:processing_baseline',''),prop.get('s2:generation_time',''),i['id'])>(unique[key]['properties'].get('s2:processing_baseline',''),unique[key]['properties'].get('s2:generation_time',''),unique[key]['id']):unique[key]=i
    result=dict(query=query,retrieved_at_utc=now(),raw_count=len(items),features=sorted(unique.values(),key=lambda i:(i['properties']['datetime'],i['id'])))
    write_json(target,result);return result
def calibration(item):
    target=CACHE/'metadata'/f"{item['id']}.json"
    if target.exists():return json.loads(target.read_text())
    url=item['assets']['product-metadata']['href']
    r=get('GET',signed(url));root=ET.fromstring(r.content)
    def local(e):return e.tag.split('}')[-1]
    quant=[float(e.text) for e in root.iter() if local(e)=='BOA_QUANTIFICATION_VALUE']
    offsets={int(e.attrib['band_id']):float(e.text) for e in root.iter() if local(e)=='BOA_ADD_OFFSET'}
    nodata=[int(next(v.text for v in e if local(v)=='SPECIAL_VALUE_INDEX')) for e in root.iter() if local(e)=='Special_Values' and any(local(v)=='SPECIAL_VALUE_TEXT' and v.text=='NODATA' for v in e)]
    if len(quant)!=1 or quant[0]<=0 or not all(k in offsets for k in [3,7,11]) or not nodata:raise ValueError('Missing explicit product XML quantification/offset/nodata; no inference')
    result=dict(source_url=clean(url),xml_sha256=hashlib.sha256(r.content).hexdigest(),quantification=quant[0],offsets={k:offsets[n] for k,n in [('B04',3),('B08',7),('B11',11)]},nodata=nodata[0],processing_baseline=item['properties'].get('s2:processing_baseline'),retrieved_at_utc=now())
    target.parent.mkdir(parents=True,exist_ok=True);target.with_suffix('.xml').write_bytes(r.content);write_json(target,result);return result
def observe(item,field,cal):
    signature=dict(version=VERSION,item=item['id'],geometry=field['geometry'],calibration=cal['xml_sha256'])
    key=hashlib.sha256(json.dumps(signature,sort_keys=True).encode()).hexdigest();target=CACHE/'observations'/f'{key}.json'
    if target.exists():return json.loads(target.read_text())
    crs=f"EPSG:{item['properties']['proj:epsg']}";a=item['assets'];grid0=Affine(*a['B04']['proj:transform'][:6])
    if grid0.a!=10 or grid0.e!=-10:raise ValueError('Not native 10m B04 grid')
    polygon=shape(transform_geom('EPSG:4326',crs,field['geometry'])).buffer(-10)
    if polygon.is_empty:return dict(status='unobservable_eroded',scene_id=item['id'])
    win=from_bounds(*polygon.bounds,transform=grid0);left,top=math.floor(win.col_off),math.floor(win.row_off)
    w,h=math.ceil(win.col_off+win.width)-left,math.ceil(win.row_off+win.height)-top
    if w*h>500000:raise ValueError('Window exceeds 50 square km guard')
    grid=grid0*Affine.translation(left,top)
    inside=geometry_mask([mapping(polygon)],out_shape=(h,w),transform=grid,all_touched=False,invert=True)
    total=int(inside.sum())
    if total<3:return dict(status='unobservable_min_pixels',scene_id=item['id'],total_pixels=total)
    rectangle=mapping(box(grid.c,grid.f+h*grid.e,grid.c+w*grid.a,grid.f))
    params=[('collection','sentinel-2-l2a'),('item',item['id'])]+[('assets',k) for k in ['B04','B08','B11','SCL']]+[('coord_crs',crs),('dst_crs',crs),('width',w),('height',h),('resampling','nearest'),('reproject','nearest'),('unscale','false')]
    r=get('POST',PC+'/api/data/v1/item/feature.tif',params=params,json=dict(type='Feature',properties={},geometry=rectangle))
    with MemoryFile(r.content) as mem:
        with mem.open() as ds:
            if ds.shape!=(h,w) or not ds.transform.almost_equals(grid) or str(ds.crs)!=crs or ds.count<4:raise ValueError(f'Crop grid mismatch:actual={ds.shape},{ds.crs},{list(ds.transform)[:6]},bands={ds.count};expected={(h,w)},{crs},{list(grid)[:6]}')
            # Ignore the combined output alpha; mask each reflectance band's raw
            # XML NODATA separately so B11 missing support cannot censor NDVI.
            raw=ds.read([1,2,3,4],masked=False).astype('float64')
    refl={}
    for n,k in enumerate(['B04','B08','B11']):
        v=raw[n].copy();v[v==cal['nodata']]=np.nan;refl[k]=(v+cal['offsets'][k])/cal['quantification']
    scl=raw[3];good=inside & np.isin(scl,[4,5,6,7]);stats={};masks={};indices={}
    for name,other in [('ndvi','B04'),('ndmi','B11')]:
        nir=refl['B08'];b=refl[other];den=nir+b
        with np.errstate(invalid='ignore',divide='ignore'):ix=(nir-b)/den
        valid=good & np.isfinite(nir)&np.isfinite(b)&(den>1e-12)&np.isfinite(ix)&(ix>=-1)&(ix<=1)
        n=int(valid.sum());stats.update({name:float(np.median(ix[valid])) if n>=3 else None,f'{name}_valid_pixels':n,f'{name}_total_pixels':total,f'{name}_valid_fraction':n/total});masks[name]=valid;indices[name]=ix
    evidence=[]
    for yy,xx in list(zip(*np.where(masks['ndvi'])))[:5]:
        evidence.append(dict(row=int(yy),col=int(xx),center_xy=list(grid*(int(xx)+.5,int(yy)+.5)),raw_dn={k:float(raw[n,yy,xx]) if np.isfinite(raw[n,yy,xx]) else None for n,k in enumerate(['B04','B08','B11','SCL'])},reflectance={k:float(v[yy,xx]) if np.isfinite(v[yy,xx]) else None for k,v in refl.items()},ndvi=float(indices['ndvi'][yy,xx]),ndmi=float(indices['ndmi'][yy,xx]) if masks['ndmi'][yy,xx] else None))
    result=dict(status='observed',algorithm_version=VERSION,entity_id=field['properties']['entity_id'],year=field['properties']['year'],date=item['properties']['datetime'][:10],sensor='sentinel2_l2a',scene_id=item['id'],source_dataset_id='planetary_computer_sentinel2_l2a',**stats,grid_crs=crs,grid_transform=list(grid)[:6],grid_shape=[h,w],native_resolutions={k:a[k]['gsd'] for k in ['B04','B08','B11','SCL']},resampling='nearest for all;B11 20m contains no additional 10m information',edge_rule='10m inward buffer;pixel centers;min3',response_bytes=len(r.content),calibration=cal,product_id=item['properties'].get('s2:product_uri'),assets={k:clean(a[k]['href']) for k in ['B04','B08','B11','SCL']},pixel_evidence=evidence,retrieved_at_utc=now())
    write_json(target,result);return result

def run(limit_fields=None,workers=3):
    started=time.time();fields=json.loads((REPORT/'selected_fields.geojson').read_text())['features']
    if limit_fields:fields=fields[:limit_fields]
    catalogs={};errors=[]
    for n,f in enumerate(fields,1):
        eid=f['properties']['entity_id']
        try:catalogs[eid]=catalog(f);print('catalog',n,len(fields),eid,len(catalogs[eid]['features']),flush=True)
        except Exception as e:errors.append(dict(entity_id=eid,stage='catalog',error_type=type(e).__name__,message=str(e).split('?')[0][:200]));print('catalog FAILED',eid,type(e).__name__,flush=True)
    # Initial acquisition uses one catalog-cloud-ranked candidate per fixed 10-day bin.
    # This is label independent; failed/low-quality observations remain missing and are gap-fill candidates.
    jobs=[];scene_items={};audit=[]
    from datetime import date
    for f in fields:
        eid=f['properties']['entity_id'];items=catalogs.get(eid,{}).get('features',[]);bins={}
        for item in items:
            when=date.fromisoformat(item['properties']['datetime'][:10]);binid=(when-date(when.year,4,1)).days//10
            bins.setdefault(binid,[]).append(item)
        for b,items in sorted(bins.items()):
            item=min(items,key=lambda i:(i['properties'].get('eo:cloud_cover',100),i['properties']['datetime'],i['id']))
            jobs.append((item,f));scene_items[item['id']]=item
            audit.append(dict(entity_id=eid,bin_index=b,selected_scene_id=item['id'],catalog_candidates=len(items)))
    write_csv(REPORT/'scene_selection.csv',audit) if audit else None
    write_json(REPORT/'catalog_receipt.json',dict(fields=len(fields),queries={k:dict(query=v['query'],raw_count=v['raw_count'],deduplicated_count=len(v['features'])) for k,v in catalogs.items()},rule='one minimum catalog cloud candidate per fixed 10day bin from Apr1;initial budget stage;local SCL decides acceptance',planned_jobs=len(jobs)))
    calibrations={}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures={pool.submit(calibration,item):sid for sid,item in sorted(scene_items.items())}
        for n,future in enumerate(as_completed(futures),1):
            sid=futures[future]
            try:calibrations[sid]=future.result()
            except Exception as e:errors.append(dict(scene_id=sid,stage='metadata',error_type=type(e).__name__,message=str(e).split('?')[0][:200]))
            if n%20==0 or n==len(scene_items):print('metadata',n,len(scene_items),'success',len(calibrations),flush=True)
    receipts=[]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures={pool.submit(observe,i,f,calibrations[i['id']]):(i,f) for i,f in jobs if i['id'] in calibrations}
        for n,future in enumerate(as_completed(futures),1):
            i,f=futures[future]
            try:r=future.result();receipts.append(r)
            except Exception as e:errors.append(dict(entity_id=f['properties']['entity_id'],scene_id=i['id'],stage='pixels',error_type=type(e).__name__,message=str(e).split('?')[0][:200]))
            if n%20==0 or n==len(futures):print('pixels',n,len(futures),'success',sum(r['status']=='observed' for r in receipts),flush=True)
    write_json(REPORT/'run_report.json',dict(status='partial' if errors or len(receipts)<len(jobs) else 'initial_acquisition_completed',workers=workers,algorithm_version=VERSION,elapsed_seconds=time.time()-started,fields_attempted=len(fields),catalog_success=len(catalogs),planned_observations=len(jobs),successful_observations=sum(r['status']=='observed' for r in receipts),unobservable_jobs=sum(r['status']!='observed' for r in receipts),metadata_success=len(calibrations),metadata_planned=len(scene_items),errors=errors,completed_at_utc=now(),checkpoint='reports/b_satellite/v2/.cache',expansion_authorized=False))
    write_scene_manifest(REPORT/'scene_manifest.json',dict(catalog=CAT,collection='sentinel-2-l2a',scenes=[dict(scene_id=k,product_id=i['properties'].get('s2:product_uri'),datetime=i['properties']['datetime'],processing_baseline=i['properties'].get('s2:processing_baseline'),crs=i['properties'].get('proj:epsg'),assets={b:{kk:vv for kk,vv in i['assets'][b].items() if kk!='href'}|{'href':clean(i['assets'][b]['href'])} for b in ['B04','B08','B11','SCL','product-metadata']},calibration=calibrations.get(k)) for k,i in sorted(scene_items.items())]))
    print('FINISHED',len(receipts),'seconds',time.time()-started,flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--limit-fields',type=int);p.add_argument('--workers',type=int,default=3);a=p.parse_args()
    if not 1<=a.workers<=6:p.error('workers must be 1..6')
    REPORT.mkdir(parents=True,exist_ok=True)
    with (REPORT/'acquisition_stdout.txt').open('a',encoding='utf-8') as log:
        original=sys.stdout
        class Tee:
            def write(self,s):original.write(s);log.write(s)
            def flush(self):original.flush();log.flush()
        sys.stdout=Tee()
        try:print('START',now(),'workers',a.workers,flush=True);run(a.limit_fields,a.workers)
        finally:sys.stdout=original
