"""Provider-side COG crop fallback: public API, native pixel grid, no SAS persistence."""
import argparse,hashlib,json,math,shutil,threading
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
import numpy as np
import requests
from rasterio.io import MemoryFile
from rasterio.transform import Affine
from rasterio.features import geometry_mask
from rasterio.warp import transform_geom
from rasterio.windows import from_bounds
from shapely.geometry import shape,box,mapping
from .contracts import load_sample,load_json,write_json,write_csv,TIMESERIES_COLUMNS,FEATURE_COLUMNS,SOURCE_COLUMNS
from .features import summarize
from .imagery import ndvi_statistics
from .pipeline import utc_now,plot_observations
PC='https://planetarycomputer.microsoft.com'
API=PC+'/api/data/v1/item/feature.tif'
RADIOMETRY_REFERENCE='https://sentiwiki.copernicus.eu/web/s2-products'
_CACHE_LOCK=threading.Lock()

def calibration_parameters(item):
    value=item['properties'].get('s2:processing_baseline','')
    try:baseline=float(value)
    except (ValueError,TypeError):raise ValueError('Missing numeric processing baseline')
    if not 2<=baseline<=5.13:raise ValueError('Unsupported processing baseline; no calibration guess')
    # ESA L2A DQR explicitly specifies -1000 DN for all bands at PB04+.
    # PC confirms its raw COGs are not harmonized; unscale=false preserves raw DN.
    return value,(-1000.0 if baseline>=4 else 0.0)

def observe_crop(item,geometry,cache):
    baseline,dn_offset=calibration_parameters(item)
    signature=dict(version='pc-native-crop-baseline-calibrated-v2',item=item,geometry=geometry)
    key=hashlib.sha256(json.dumps(signature,sort_keys=True).encode()).hexdigest()
    target=cache/(key+'.json')
    if target.exists():
        result=load_json(target);result['cache_hit']=True;return result
    epsg=item['properties'].get('proj:epsg')
    if not epsg:raise ValueError('Missing product projection metadata')
    crs=f'EPSG:{epsg}'
    asset=item['assets']['B04'];transform=Affine(*asset['proj:transform'][:6])
    if abs(transform.a)!=10 or abs(transform.e)!=10:raise ValueError('Not native 10m')
    projected=transform_geom('EPSG:4326',crs,geometry)
    window=from_bounds(*shape(projected).bounds,transform=transform)
    left,top=math.floor(window.col_off),math.floor(window.row_off)
    width,height=math.ceil(window.col_off+window.width)-left,math.ceil(window.row_off+window.height)-top
    if width*height>2_000_000:raise ValueError('Field window too large')
    grid=transform*Affine.translation(left,top)
    rectangle=mapping(box(grid.c,grid.f+height*grid.e,grid.c+width*grid.a,grid.f))
    params=[('collection','sentinel-2-l2a'),('item',item['id']),('assets','B04'),('assets','B08'),('assets','SCL'),('coord_crs',crs),('dst_crs',crs),('resampling','nearest'),('reproject','nearest'),('width',width),('height',height),('unscale','false')]
    response=requests.post(API,params=params,json={'type':'Feature','properties':{},'geometry':rectangle},timeout=(15,75))
    if not response.ok:raise RuntimeError(f'PC crop HTTP {response.status_code}')
    with MemoryFile(response.content) as mem:
        with mem.open() as raster:
            if raster.shape!=(height,width) or not raster.transform.almost_equals(grid) or str(raster.crs)!=crs or raster.count<3:
                raise ValueError('Server crop does not preserve requested native grid')
            data=raster.read([1,2,3],masked=True).astype('float64').filled(np.nan)
    for band in (0,1):
        data[band][data[band]==0]=np.nan
        data[band]+=dn_offset
    inside=geometry_mask([projected],out_shape=(height,width),transform=grid,all_touched=False,invert=True)
    # Offset is applied to float DN after nodata masking. Common quantification gain cancels.
    stats=ndvi_statistics(data[0],data[1],data[2],inside)
    result=dict(scene_id=item['id'],product_id=item['properties'].get('s2:product_uri'),source_url=PC+'/api/stac/v1/collections/sentinel-2-l2a/items/'+item['id'],retrieved_at_utc=utc_now(),cache_hit=False,stats=stats,parameters=dict(api_url=API,request_parameters=params,request_geometry=rectangle,grid_crs=crs,grid_transform=list(grid),grid_shape=[height,width],radiometry='Float DN plus metadata-baseline documented BOA offset; common 1/10000 gain cancels in NDVI',processing_baseline=baseline,applied_dn_offset=dn_offset,calibration_basis='ESA L2A DQR: PB04+ BOA_ADD_OFFSET=-1000 for all bands; PC raw COGs not harmonized',provider_reference='https://github.com/microsoft/PlanetaryComputer/issues/134',radiometry_reference=RADIOMETRY_REFERENCE,valid_scl=[4,5,6,7],resampling='nearest',edge_rule='pixel_center_inside_all_touched_false',asset_urls={k:item['assets'][k]['href'] for k in ['B04','B08','SCL']},response_bytes=len(response.content)))
    cache.mkdir(parents=True,exist_ok=True)
    payload=json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False)
    with _CACHE_LOCK:
        if sum(p.stat().st_size for p in cache.glob('*.json'))+len(payload.encode())<=256*1024*1024:
            temporary=target.with_suffix('.tmp');write_json(temporary,result);temporary.replace(target)
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fields',required=True);parser.add_argument('--sample',required=True)
    parser.add_argument('--refresh-inventory',action='store_true')
    args=parser.parse_args();sample,field=load_sample(args.fields,args.sample)
    root=Path(__file__).resolve().parents[2];reports=root/'reports/b_satellite';out=root/'data/processed/satellite'
    inventory_file=reports/'pc_scene_inventory.json.gz'
    receipt_file=reports/'pc_search_receipt.json'
    if args.refresh_inventory or not inventory_file.exists() or not receipt_file.exists():
        query=dict(collections=['sentinel-2-l2a'],intersects=field['geometry'],datetime=f"{sample['window_start']}T00:00:00Z/{sample['year']}-11-30T23:59:59Z",limit=500)
        response=requests.post(PC+'/api/stac/v1/search',json=query,timeout=(15,60));response.raise_for_status()
        write_json(inventory_file,response.json())
        write_json(receipt_file,dict(retrieved_at_utc=utc_now(),sample=sample,geometry=field['geometry'],query=query,source_url=PC+'/api/stac/v1/search'))
    receipt=load_json(receipt_file)
    if receipt['sample']!=sample or receipt['geometry']!=field['geometry']:raise ValueError('PC inventory does not match A sample/geometry')
    inventory=load_json(inventory_file)
    if any(link['rel']=='next' for link in inventory.get('links',[])):raise ValueError('Inventory paginated; fetch all before running')
    items=inventory['features']
    for item in items:
        if not sample['window_start']<=item['properties']['datetime'][:10]<sample['window_end_exclusive']:raise ValueError('Out-of-window item')
    receipts=[];errors=[]
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures={pool.submit(observe_crop,item,field['geometry'],reports/'.cache/pc_crop'):item for item in items}
        for n,future in enumerate(as_completed(futures),1):
            item=futures[future]
            try:
                receipt=future.result();receipt['date']=item['properties']['datetime'][:10];receipts.append(receipt)
                print(n,len(items),item['id'],'OK',flush=True)
            except Exception as error:
                errors.append(dict(scene_id=item['id'],error_type=type(error).__name__,message=str(error)[:160]));print(n,len(items),item['id'],'FAILED',flush=True)
    receipts.sort(key=lambda r:(r['date'],r['scene_id']))
    rows=[dict(field_id=sample['field_id'],year=sample['year'],date=r['date'],sensor='sentinel2_l2a',scene_id=r['scene_id'],ndvi=r['stats']['ndvi'],valid_pixel_fraction=r['stats']['valid_pixel_fraction'],source_dataset_id='planetary_computer_sentinel2_l2a') for r in receipts]
    result,daily=summarize(rows,sample)
    report=dict(status='partial' if errors else 'completed' if result['valid_obs_count'] else 'blocked_no_valid_observations',provider='planetary_computer_server_crop',real_sample_computed=True,sample=sample,scene_count=len(items),processed_scene_count=len(receipts),cache_hits=sum(r['cache_hit'] for r in receipts),valid_obs_count=result['valid_obs_count'],max_gap_days=result['max_gap_days'],quality_flag=result['quality_flag'],issues=errors,finished_at_utc=utc_now())
    write_json(reports/'pc_run_report.json',report);write_json(reports/'pc_scene_provenance.json',receipts)
    if not receipts:return 2
    if errors:result['missing_reason']=';'.join(filter(None,[result['missing_reason'],'unprocessed_pc_scenes_see_report']))
    archive=reports/'earthsearch_partial';archive.mkdir(exist_ok=True)
    for name in ['run_report.json','scene_provenance.json','ndvi_timeseries.png','coverage_report.json','validation_report.json']:
        if (reports/name).exists() and not (archive/name).exists():shutil.copyfile(reports/name,archive/name)
    for name in ['timeseries.csv','features.csv']:
        if (out/name).exists() and not (archive/name).exists():shutil.copyfile(out/name,archive/name)
    write_csv(out/'timeseries.csv',TIMESERIES_COLUMNS,rows);write_csv(out/'features.csv',FEATURE_COLUMNS,[result]);plot_observations(rows,daily,sample,reports/'ndvi_timeseries.png')
    write_json(reports/'run_report.json',report)
    return 2 if errors else 0
if __name__=='__main__':raise SystemExit(main())
