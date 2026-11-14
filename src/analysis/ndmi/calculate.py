"""Maryland corn NDMI, 2021-2025: real public rasters, deterministic clear-pixel composites."""
import argparse
import calendar
import concurrent.futures
import datetime as dt
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import time
import tempfile
import threading
import sys
import urllib.parse
import urllib.request
import urllib.error

import numpy as np
import rasterio
from rasterio.features import geometry_mask, geometry_window
from rasterio.io import MemoryFile
from rasterio.transform import from_origin
from rasterio.vrt import WarpedVRT
from rasterio.windows import Window, bounds as window_bounds
from rasterio.enums import Resampling
from pyproj import Transformer
from shapely.geometry import shape, mapping
from shapely.ops import transform as geometry_transform

CDL = 'https://pdi.scinet.usda.gov/image/rest/services/CDL_WM/ImageServer'
CENSUS = 'https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer/0/query'
STAC = 'https://planetarycomputer.microsoft.com/api/stac/v1/search'
SIGN = 'https://planetarycomputer.microsoft.com/api/sas/v1/sign'
BANDS = ['nir08', 'swir16', 'qa_pixel', 'qa_radsat']
SCALE, OFFSET = 0.0000275, -0.2
QA_PIXEL_REJECT = 0b111111  # fill, dilated cloud, cirrus, cloud, shadow, snow
QA_RADSAT_REJECT = (1 << 4) | (1 << 5) | (1 << 11)  # B5, B6, terrain occlusion
SAS_TOKENS = {}
TOKEN_LOCK = threading.Lock()


def request(url, body=None, binary=False, timeout=90):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers={'User-Agent': 'CornHub-NDMI/1.0',
        **({'Content-Type': 'application/json'} if data else {})})
    for attempt in range(8):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as stream:
                raw = stream.read()
            return raw if binary else json.loads(raw)
        except Exception as exc:
            if attempt == 7:
                raise
            delay = min(30,2**attempt)
            if isinstance(exc, urllib.error.HTTPError) and exc.code == 429:
                delay = max(delay,int(exc.headers.get('Retry-After','10')))
                print(json.dumps({'stage':'rate_limit','retry_after_seconds':delay}),flush=True)
            time.sleep(delay)


def init_tokens(tokens):
    global SAS_TOKENS
    SAS_TOKENS = tokens


def public_container_tokens(years, cache):
    """One public read-only token per container, shared by workers; never persisted."""
    locations=set()
    for year in years:
        for item in json.load(gzip.open(cache/f'landsat_{year}.json.gz','rt')):
            for key in BANDS:
                u=urllib.parse.urlsplit(item['assets'][key]['href'])
                locations.add((u.netloc.split('.')[0],u.path.split('/')[1]))
    result={}
    for account,container in sorted(locations):
        reply=request(f'https://planetarycomputer.microsoft.com/api/sas/v1/token/{account}/{container}')
        result[(account,container)]={'token':reply['token'].lstrip('?'),
            'expiry':dt.datetime.fromisoformat(reply['msft:expiry'].replace('Z','+00:00')).timestamp()}
    return result


def signed_asset(unsigned):
    u=urllib.parse.urlsplit(unsigned)
    loc=(u.netloc.split('.')[0],u.path.split('/')[1])
    with TOKEN_LOCK:
        token=SAS_TOKENS[loc]
        if token['expiry'] < time.time()+120:
            reply=request(f'https://planetarycomputer.microsoft.com/api/sas/v1/token/{loc[0]}/{loc[1]}')
            token={'token':reply['token'].lstrip('?'),
                'expiry':dt.datetime.fromisoformat(reply['msft:expiry'].replace('Z','+00:00')).timestamp()}
            SAS_TOKENS[loc]=token
    return unsigned+'?'+token['token']


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')
    temp.replace(path)


def get_json(cache, name, url, body=None):
    path = cache/name
    if path.exists():
        return json.loads(path.read_text())
    result = request(url, body)
    save(path, result)
    return result


def setup(cache):
    query = {'where': "STATE='24'", 'outFields': 'STATE,NAME', 'returnGeometry': 'true',
             'outSR': 4326, 'geometryPrecision': 6, 'f': 'geojson'}
    boundary = get_json(cache, 'maryland_boundary.geojson', CENSUS+'?'+urllib.parse.urlencode(query))
    if len(boundary.get('features', [])) != 1:
        raise ValueError('Census did not return one Maryland geometry')
    geo = shape(boundary['features'][0]['geometry'])
    projection = Transformer.from_crs(4326, 5070, always_xy=True)
    albers = geometry_transform(projection.transform, geo)
    x0, y0, x1, y1 = albers.bounds
    left, top = math.floor(x0/30)*30, math.ceil(y1/30)*30
    width, height = math.ceil((x1-left)/30), math.ceil((top-y0)/30)
    grid = {'crs': 'EPSG:5070', 'left': left, 'top': top, 'width': width, 'height': height,
            'resolution_m': 30, 'bbox_4326': list(geo.bounds)}
    save(cache/'grid.json', grid)
    inside_path = cache/'inside_md.npy'
    if not inside_path.exists():
        inside = geometry_mask([mapping(albers)], out_shape=(height, width),
            transform=from_origin(left, top, 30, 30), invert=True, all_touched=False)
        np.save(inside_path, inside)
    result = get_json(cache, 'cdl_year_catalog.json', CDL+'/query?'+urllib.parse.urlencode({
        'where': 'Year >= 2021 AND Year <= 2025', 'outFields': 'OBJECTID,Name,Year',
        'returnGeometry': 'false', 'f': 'json'}))
    by_year = {r['attributes']['Year']: r['attributes'] for r in result.get('features', [])}
    if set(by_year) != set(range(2021, 2026)):
        raise ValueError('USDA missing a requested year; no year substitution')
    return grid, by_year


def build_mask(year, grid, source, cache):
    target = cache/f'corn_{year}.npy'
    if target.exists():
        return json.loads((cache/f'corn_{year}.json').read_text())
    transform = from_origin(grid['left'], grid['top'], 30, 30)
    inside = np.load(cache/'inside_md.npy', mmap_mode='r')
    mask = np.lib.format.open_memmap(target.with_suffix('.part.npy'), mode='w+',
        dtype='bool', shape=(grid['height'], grid['width']))
    mask[:] = False
    jobs = []
    for row in range(0, grid['height'], 4096):
        for col in range(0, grid['width'], 4096):
            h, w = min(4096, grid['height']-row), min(4096, grid['width']-col)
            if np.any(inside[row:row+h, col:col+w]):
                jobs.append((row, col, h, w))
    def fetch(job):
        row, col, h, w = job
        bounds = window_bounds(Window(col, row, w, h), transform)
        params = {'bbox': ','.join(map(str, bounds)), 'bboxSR': 5070, 'imageSR': 5070,
            'size': f'{w},{h}', 'format': 'tiff', 'pixelType': 'U8', 'interpolation': 'RSP_NearestNeighbor',
            'mosaicRule': json.dumps({'mosaicMethod':'esriMosaicLockRaster',
                'lockRasterIds':[source['OBJECTID']], 'mosaicOperation':'MT_FIRST'}),
            'renderingRule': json.dumps({'rasterFunction':'None'}), 'f':'image'}
        url = CDL+'/exportImage?'+urllib.parse.urlencode(params)
        raw = request(url, binary=True)
        with MemoryFile(raw) as mem, mem.open() as ds:
            if ds.count != 1 or ds.width != w or ds.height != h or ds.crs.to_epsg() != 5070:
                raise ValueError('USDA export grid mismatch')
            expected = rasterio.windows.transform(Window(col, row, w, h), transform)
            if not np.allclose(tuple(ds.transform), tuple(expected), rtol=0, atol=1e-6):
                raise ValueError('USDA export shifted/resized the grid')
            crop = ds.read(1) == 1
        return job, crop & inside[row:row+h, col:col+w], hashlib.sha256(raw).hexdigest(), url
    tiles = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for job, crop, sha, url in pool.map(fetch, jobs):
            row, col, h, w = job
            mask[row:row+h, col:col+w] = crop
            tiles.append({'row':row,'col':col,'height':h,'width':w,'sha256':sha,'source_url':url})
    count = int(np.count_nonzero(mask))
    if not count:
        raise ValueError('No corn pixels returned; no fabricated zero NDMI')
    mask.flush()
    del mask
    target.with_suffix('.part.npy').replace(target)
    metadata = {'year':year,'source':source,'corn_class':1,'excluded_classes':'sweet/popcorn and double-crop classes',
        'source_resolution_m':10 if year >= 2024 else 30, 'target_resolution_m':30,
        'resampling':'nearest','boundary_rule':'pixel center inside Census Maryland',
        'corn_pixel_count':count,'corn_area_ha':count*0.09,'tiles':tiles}
    save(cache/f'corn_{year}.json', metadata)
    print(json.dumps({'stage':'corn_mask','year':year,'pixels':count,'area_ha':count*0.09}), flush=True)
    return metadata


def catalog(year, grid, cache):
    path = cache/f'landsat_{year}.json.gz'
    if path.exists():
        with gzip.open(path, 'rt') as f:
            return json.load(f)
    body = {'collections':['landsat-c2-l2'], 'bbox':grid['bbox_4326'],
        'datetime':f'{year}-01-01T00:00:00Z/{year}-12-31T23:59:59Z',
        'query':{'platform':{'in':['landsat-8','landsat-9']},'landsat:collection_category':{'eq':'T1'}},
        'limit':500,'fields':{'include':['id','geometry','bbox','properties',
            'assets.nir08','assets.swir16','assets.qa_pixel','assets.qa_radsat','links']}}
    url, items, method = STAC, [], 'POST'
    while True:
        result = request(url, body if method == 'POST' else None)
        for item in result.get('features', []):
            if all(k in item['assets'] for k in BANDS):
                items.append(item)
        link = next((r for r in result.get('links',[]) if r['rel']=='next'), None)
        if not link:
            break
        url, method = link['href'], link.get('method','GET')
        body = {**body, **link.get('body',{})}
    if len({r['id'] for r in items}) != len(items):
        raise ValueError('Duplicate scene IDs in catalog')
    with gzip.open(path, 'wt') as f:
        json.dump(items, f)
    print(json.dumps({'stage':'catalog','year':year,'scenes':len(items)}), flush=True)
    return items


def ndmi(nir_dn, swir_dn, qa, sat):
    nir, swir = nir_dn.astype('float64')*SCALE+OFFSET, swir_dn.astype('float64')*SCALE+OFFSET
    valid = ((nir_dn != 0) & (swir_dn != 0) & ((qa & QA_PIXEL_REJECT)==0)
        & ((sat & QA_RADSAT_REJECT)==0) & (nir >= 0) & (swir >= 0) & ((nir+swir)>0))
    value = np.full(nir.shape, np.nan, dtype='float32')
    np.divide(nir-swir, nir+swir, out=value, where=valid)
    valid &= np.isfinite(value) & (value >= -1) & (value <= 1)
    return value, valid


def month_job(year, month, cache_name, result_name):
    cache, results = Path(cache_name), Path(result_name)
    path = results/f'{year}_{month:02}.json'
    if path.exists():
        return json.loads(path.read_text())
    grid = json.loads((cache/'grid.json').read_text())
    corn = np.load(cache/f'corn_{year}.npy', mmap_mode='r')
    total = int(np.count_nonzero(corn))
    with gzip.open(cache/f'landsat_{year}.json.gz','rt') as f:
        items = [r for r in json.load(f) if int(r['properties']['datetime'][5:7]) == month]
    middle = dt.datetime(year,month,15,tzinfo=dt.timezone.utc)
    def order(item):
        date = dt.datetime.fromisoformat(item['properties']['datetime'].replace('Z','+00:00'))
        return (item['properties'].get('eo:cloud_cover',100),abs((date-middle).total_seconds()),date.isoformat(),item['id'])
    items.sort(key=order)
    transform = from_origin(grid['left'],grid['top'],30,30)
    values = np.full(corn.shape, np.nan, dtype='float32')
    remaining, used, errors, examples = total, [], [], []
    progress_path=cache/f'progress_{year}_{month:02}.json'
    previous_array=None
    next_scene=0
    if progress_path.exists():
        progress=json.loads(progress_path.read_text())
        assert progress['scene_ids']==[s['id'] for s in items], 'Catalog changed during resume'
        previous_array=cache/progress['array']
        values=np.load(previous_array)
        used,errors,examples=progress['used'],progress['errors'],progress['examples']
        remaining=total-int(np.count_nonzero(np.isfinite(values)))
        next_scene=progress['next_scene']
    def checkpoint(next_scene):
        nonlocal previous_array
        target=cache/f'checkpoint_{year}_{month:02}_{next_scene}.npy'
        np.save(target,values)
        save(progress_path,{'array':target.name,'next_scene':next_scene,
            'scene_ids':[s['id'] for s in items],'used':used,'errors':errors,'examples':examples})
        if previous_array and previous_array != target:previous_array.unlink(missing_ok=True)
        previous_array=target
    projection = Transformer.from_crs(4326,5070,always_xy=True)
    profile = {'height':grid['height'],'width':grid['width'],'transform':transform}
    from types import SimpleNamespace
    dataset_grid = SimpleNamespace(**profile)
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR', CPL_VSIL_CURL_ALLOWED_EXTENSIONS='.TIF,.tif',
                      GDAL_HTTP_TIMEOUT=45, GDAL_HTTP_MAX_RETRY=2, GDAL_HTTP_RETRY_DELAY=1,
                      GDAL_CACHEMAX=128*1024*1024, VSI_CACHE=True, GDAL_HTTP_MULTIPLEX='YES'):
        for scene_number,item in enumerate(items):
            if scene_number < next_scene:continue
            if not remaining:
                break
            accepted = 0
            try:
                footprint = geometry_transform(projection.transform, shape(item['geometry']))
                try:
                    win = geometry_window(dataset_grid,[mapping(footprint)])
                except rasterio.errors.WindowError:
                    continue
                row0,col0,h,w = int(win.row_off),int(win.col_off),int(win.height),int(win.width)
                eligible = corn[row0:row0+h,col0:col0+w] & ~np.isfinite(values[row0:row0+h,col0:col0+w])
                if not np.any(eligible):
                    continue
                from contextlib import ExitStack
                accepted = 0
                with ExitStack() as stack:
                    # Read small QA assets first; skip reflectance when all wanted pixels
                    # fail QA. For at most two remaining tiles, use COG range reads.
                    folder = Path(stack.enter_context(tempfile.TemporaryDirectory(prefix='ndmi_scene_',dir=cache)))
                    def download(key):
                        signed=signed_asset(item['assets'][key]['href'])
                        target = folder/(key+'.tif')
                        for attempt in range(3):
                            try:
                                with urllib.request.urlopen(signed,timeout=90) as stream, target.open('wb') as out:
                                    while True:
                                        chunk = stream.read(4*1024*1024)
                                        if not chunk: break
                                        out.write(chunk)
                                return key,target
                            except Exception as exc:
                                if attempt == 2: raise
                                delay=int(exc.headers.get('Retry-After','10')) if isinstance(exc,urllib.error.HTTPError) and exc.code==429 else 2**attempt
                                time.sleep(delay)
                        raise RuntimeError('download retries exhausted')
                    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as downloads:
                        local = dict(downloads.map(download,['qa_pixel','qa_radsat']))
                    datasets = {}
                    def open_warp(key,location):
                        src=stack.enter_context(rasterio.open(location))
                        opts={'src_nodata':65535} if key.startswith('qa_') else {}
                        return stack.enter_context(WarpedVRT(src,crs='EPSG:5070',transform=transform,
                            width=grid['width'],height=grid['height'],resampling=Resampling.nearest,nodata=0,**opts))
                    for key in ['qa_pixel','qa_radsat']:
                        datasets[key]=open_warp(key,local[key])
                    active=[]
                    for row in range(row0,row0+h,1024):
                        for col in range(col0,col0+w,1024):
                            hh,ww=min(1024,row0+h-row),min(1024,col0+w-col)
                            wanted=corn[row:row+hh,col:col+ww] & ~np.isfinite(values[row:row+hh,col:col+ww])
                            if not np.any(wanted):continue
                            tile=Window(col,row,ww,hh)
                            q=datasets['qa_pixel'].read(1,window=tile)
                            sat=datasets['qa_radsat'].read(1,window=tile)
                            possible=wanted & ((q&QA_PIXEL_REJECT)==0) & ((sat&QA_RADSAT_REJECT)==0)
                            if np.any(possible):active.append((row,col,hh,ww))
                    if not active:continue
                    if len(active) <= 2:
                        for key in ['nir08','swir16']:
                            datasets[key]=open_warp(key,signed_asset(item['assets'][key]['href']))
                    else:
                        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as downloads:
                            local.update(dict(downloads.map(download,['nir08','swir16'])))
                        for key in ['nir08','swir16']:
                            datasets[key]=open_warp(key,local[key])
                    for row,col,hh,ww in active:
                        dest = values[row:row+hh,col:col+ww]
                        wanted = corn[row:row+hh,col:col+ww] & ~np.isfinite(dest)
                        if not np.any(wanted):
                            continue
                        tile = Window(col,row,ww,hh)
                        raw = [datasets[k].read(1,window=tile) for k in BANDS]
                        index, valid = ndmi(*raw)
                        take = wanted & valid
                        n = int(np.count_nonzero(take))
                        if n and len(examples) < 5:
                            rr, cc = np.argwhere(take)[0]
                            dn5, dn6, q, s = [int(a[rr,cc]) for a in raw]
                            x, y = transform * (col+int(cc)+0.5, row+int(rr)+0.5)
                            examples.append({'scene_id':item['id'],'row':row+int(rr),'col':col+int(cc),
                                'x_epsg5070':x,'y_epsg5070':y,'dn_b5':dn5,'dn_b6':dn6,
                                'qa_pixel':q,'qa_radsat':s,'rho_b5':dn5*SCALE+OFFSET,
                                'rho_b6':dn6*SCALE+OFFSET,'ndmi':float(index[rr,cc])})
                        dest[take] = index[take]
                        accepted += n
            except Exception as exc:
                import re
                message = re.sub(r'https?://[^\s]+', '[URL redacted]', str(exc))[:200]
                errors.append({'scene_id':item['id'],'type':type(exc).__name__,'message':message})
                print(json.dumps({'stage':'scene_error','year':year,'month':month,'scene':item['id'],'type':type(exc).__name__}),flush=True)
            finally:
                if accepted:
                    remaining -= accepted
                    used.append({'scene_id':item['id'],'date':item['properties']['datetime'],
                        'platform':item['properties']['platform'],'pixels_used':accepted,
                        'scene_cloud_cover':item['properties'].get('eo:cloud_cover'),
                        'assets':{k:item['assets'][k]['href'] for k in BANDS}})
                    print(json.dumps({'stage':'month_scene','year':year,'month':month,'scene':item['id'],
                        'accepted':accepted,'coverage':(total-remaining)/total}),flush=True)
                if sys.exc_info()[0] is None:checkpoint(scene_number+1)
    valid = values[np.isfinite(values)]
    n = len(valid)
    status = 'computed' if n and not errors else 'partial_scene_errors' if n else 'failed_scene_errors' if errors else 'no_valid_observations'
    result = {'year':year,'month':month,'scope':'Maryland state; annual CDL Corn class=1',
        'status':status,'method':'spatial mean of deterministic monthly first-clear-pixel mosaic',
        'corn_pixel_count':total,'corn_area_ha':total*0.09,'valid_pixel_count':n,'valid_area_ha':n*0.09,
        'valid_area_fraction':n/total,'ndmi_mean':float(np.mean(valid,dtype='float64')) if n else None,
        'ndmi_median':float(np.median(valid)) if n else None,
        'ndmi_p10':float(np.quantile(valid,0.1)) if n else None,'ndmi_p90':float(np.quantile(valid,0.9)) if n else None,
        'candidate_scenes':len(items),'used_scene_count':len(used),'used_scenes':used,'scene_errors':errors,
        'pixel_examples':examples,
        'formula':'((DN_B5*0.0000275-0.2)-(DN_B6*0.0000275-0.2))/((DN_B5*0.0000275-0.2)+(DN_B6*0.0000275-0.2))',
        'qa_pixel_reject_bits':[0,1,2,3,4,5],'qa_radsat_reject_bits':[4,5,11],
        'resampling':'nearest on EPSG:5070 fixed 30m grid; pixel centers in Maryland',
        'priority':'scene cloud cover, absolute distance from month day 15, datetime, scene id',
        'notes':['Not a mean of every observation in a month; each corn pixel contributes at most one clear observation.',
                 'Annual corn mask does not imply live corn is present throughout winter.',
                 'Valid area is reported; missing/cloud/snow pixels are not filled with zero.',
                 'NDMI is a vegetation moisture proxy, not volumetric soil moisture or a silage/grain label.']}
    save(path,result)
    progress_path.unlink(missing_ok=True)
    if previous_array:previous_array.unlink(missing_ok=True)
    print(json.dumps({'stage':'month_done','year':year,'month':month,'status':status,'ndmi_mean':result['ndmi_mean'],'coverage':result['valid_area_fraction']}),flush=True)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cache',type=Path,default=Path('/tmp/cornhub_md_ndmi'))
    p.add_argument('--output',type=Path,default=Path('data/processed/analysis/ndmi/months'))
    p.add_argument('--prepare-only',action='store_true')
    p.add_argument('--year',type=int,choices=range(2021,2026))
    p.add_argument('--month',type=int,choices=range(1,13))
    p.add_argument('--workers',type=int,default=2)
    args=p.parse_args()
    args.cache.mkdir(parents=True,exist_ok=True)
    grid,sources=setup(args.cache)
    years=[args.year] if args.year else list(range(2021,2026))
    for year in years:
        build_mask(year,grid,sources[year],args.cache)
        catalog(year,grid,args.cache)
    if args.prepare_only:
        return
    jobs=[(y,m,str(args.cache),str(args.output)) for y in years for m in ([args.month] if args.month else range(1,13))]
    tokens=public_container_tokens(years,args.cache)
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers,initializer=init_tokens,initargs=(tokens,)) as pool:
        list(pool.map(run_job,jobs))


def run_job(args):
    return month_job(*args)


if __name__=='__main__':
    main()
