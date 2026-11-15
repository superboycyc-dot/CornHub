"""Area-weighted NOAA CPC weekly US precipitation, including Alaska and Hawaii."""
import argparse,csv,datetime as dt,gzip,hashlib,io,json,zipfile
from pathlib import Path
import numpy as np
import netCDF4,shapefile,shapely
from shapely.geometry import shape,mapping
from shapely.ops import transform as transform_geometry
from pyproj import CRS,Geod,Transformer
from download import inputs
FIPS=set('01 02 04 05 06 08 09 10 11 12 13 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32 33 34 35 36 37 38 39 40 41 42 44 45 46 47 48 49 50 51 53 54 55 56'.split())
GEOD=Geod(ellps='WGS84')

def save(path,obj):
 p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')
def table(path,rows):
 p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def area_km2(g):return abs(GEOD.geometry_area_perimeter(shapely.orient_polygons(g))[0])/1e6

def boundaries(cache):
 states=[];features=[]
 with zipfile.ZipFile(cache/'cb_2024_us_state_20m.zip') as z:
  stem=next(n[:-4] for n in z.namelist() if n.endswith('.shp'))
  reader=shapefile.Reader(shp=io.BytesIO(z.read(stem+'.shp')),shx=io.BytesIO(z.read(stem+'.shx')),dbf=io.BytesIO(z.read(stem+'.dbf')))
  project=Transformer.from_crs(CRS.from_wkt(z.read(stem+'.prj').decode()),4326,always_xy=True)
  for record in reader.iterShapeRecords():
   p=record.record.as_dict()
   if p['STATEFP'] not in FIPS:continue
   geom=transform_geometry(project.transform,shape(record.shape.__geo_interface__))
   if not geom.is_valid:geom=shapely.make_valid(geom)
   info={'scope_id':p['STUSPS'],'scope_name':p['NAME'],'state_fips':p['STATEFP'],'geometry_area_km2':area_km2(geom)}
   states.append((info,geom));features.append({'type':'Feature','properties':info,'geometry':mapping(geom)})
 assert len(states)==51 and {s[0]['state_fips'] for s in states}==FIPS
 return sorted(states,key=lambda x:x[0]['scope_id']),{'type':'FeatureCollection','features':features}

def weights(cache,output,lats,lons):
 states,features=boundaries(cache);normalized=(lons+180)%360-180;xx,yy=np.meshgrid(normalized,lats)
 pieces=[];records=[];cell_indices=set()
 for info,geom in states:
  x0,y0,x1,y1=geom.bounds
  rr,cc=np.where((xx>=x0-.25)&(xx<=x1+.25)&(yy>=y0-.25)&(yy<=y1+.25))
  boxes=shapely.box(xx[rr,cc]-.25,yy[rr,cc]-.25,xx[rr,cc]+.25,yy[rr,cc]+.25)
  shapely.prepare(geom);keep=shapely.intersects(geom,boxes);rr,cc=rr[keep],cc[keep]
  areas=np.array([area_km2(g) for g in shapely.intersection(geom,boxes[keep])])
  keep=areas>1e-9;rr,cc,areas=rr[keep],cc[keep],areas[keep]
  for r,c,a in zip(rr,cc,areas):
   cell_indices.add((int(r),int(c)));records.append({'scope_id':info['scope_id'],'grid_row':int(r),'grid_col':int(c),'lat':float(lats[r]),'lon':float(normalized[c]),'intersection_area_km2':float(a)})
  info['weighted_area_km2']=float(areas.sum());info['overlapping_grid_cells']=len(areas);pieces.append((info,rr,cc,areas))
  print(json.dumps({'stage':'state_weights','state':info['scope_id'],'cells':len(areas),'area_km2':info['weighted_area_km2']}),flush=True)
 ordered=sorted(cell_indices);index={rc:i for i,rc in enumerate(ordered)}
 rows=np.array([r for r,c in ordered]);cols=np.array([c for r,c in ordered]);w=np.zeros((53,len(ordered)),dtype='float64');scopes=[]
 for i,(info,rr,cc,aa) in enumerate(pieces):
  scopes.append(info)
  for r,c,value in zip(rr,cc,aa):w[i,index[(int(r),int(c))]]=value
 w[51]=w[:51].sum(axis=0);w[52]=w[[i for i,s in enumerate(scopes) if s['scope_id'] not in ('AK','HI')]].sum(axis=0)
 scopes += [{'scope_id':'US50_DC','scope_name':'United States: 50 states + DC'},{'scope_id':'CONUS48_DC','scope_name':'Contiguous 48 states + DC'}]
 for i,s in enumerate(scopes):s['weighted_area_km2']=float(w[i].sum())
 (output/'inputs').mkdir(parents=True,exist_ok=True)
 (output/'inputs/states_2024_20m.geojson.gz').write_bytes(gzip.compress(json.dumps(features).encode(),mtime=0))
 table(output/'inputs/grid_state_weights.csv',records);save(output/'inputs/scopes.json',scopes)
 return w,scopes,rows,cols

def summarize(values,w):
 """Require every requested day at a cell; missing is never zero rainfall."""
 valid=np.isfinite(values).all(axis=0);totals=np.where(valid,np.sum(values,axis=0,dtype='float64'),0)
 area=w@valid.astype('float64');means=np.divide(w@totals,area,out=np.full(len(w),np.nan),where=area>0)
 return means,area,valid

def weekly_groups(dates):
 groups={}
 for i,d in enumerate(dates):groups.setdefault(d-dt.timedelta(days=d.weekday()),[]).append(i)
 return sorted(groups.items())

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--cache',type=Path,default=Path('/tmp/cornhub_weekly_precip'));p.add_argument('--output',type=Path,default=Path('data/processed/analysis/precipitation'));p.add_argument('--report',type=Path,default=Path('reports/d_analysis/precipitation'));a=p.parse_args()
 a.output.mkdir(parents=True,exist_ok=True);a.report.mkdir(parents=True,exist_ok=True);manifest=inputs(a.cache)
 with netCDF4.Dataset(a.cache/'precip.2021.nc') as ds:lats=np.asarray(ds['lat'][:]);lons=np.asarray(ds['lon'][:])
 assert len(lats)==360 and len(lons)==720
 w,scopes,rr,cc=weights(a.cache,a.output,lats,lons)
 dates=[dt.date(2021,1,1)+dt.timedelta(days=i) for i in range((dt.date(2026,1,1)-dt.date(2021,1,1)).days)];lookup={d:i for i,d in enumerate(dates)}
 values=np.full((len(dates),len(rr)),np.nan,dtype='float32');observed=set();metadata=[]
 def plain(x):return x.tolist() if isinstance(x,np.ndarray) else x.item() if isinstance(x,np.generic) else x
 for year in range(2021,2026):
  with netCDF4.Dataset(a.cache/f'precip.{year}.nc') as ds:
   assert np.array_equal(ds['lat'][:],lats) and np.array_equal(ds['lon'][:],lons)
   var=ds['precip'];assert var.units=='mm','Unexpected source units'
   tv=ds['time'];tt=netCDF4.num2date(tv[:],tv.units,calendar=getattr(tv,'calendar','standard'));these=[dt.date(t.year,t.month,t.day) for t in tt]
   assert len(these)==len(set(these)) and all(t.year==year for t in these)
   low,high=map(float,var.valid_range)
   for i,day in enumerate(these):
    raw=np.ma.asarray(var[i]).filled(np.nan);selected=np.asarray(raw[rr,cc],dtype='float32');selected[(selected<low)|(selected>high)|~np.isfinite(selected)]=np.nan;values[lookup[day]]=selected;observed.add(day)
   metadata.append({'year':year,'days':len(these),'first_date':str(min(these)),'last_date':str(max(these)),'precip_attributes':{k:plain(v) for k,v in var.__dict__.items()},'dataset_attributes':{k:plain(v) for k,v in ds.__dict__.items()},'time_units':tv.units})
   print(json.dumps({'stage':'daily_loaded','year':year,'source_days':len(these),'us_grid_cells':len(rr)}),flush=True)
 np.savez_compressed(a.cache/'selected_us_daily.npz',values=values,rows=rr,cols=cc,weights=w)
 save(a.output/'inputs/netcdf_metadata.json',metadata);save(a.output/'inputs/source_manifest.json',manifest)
 missing=sorted(str(d) for d in set(dates)-observed);save(a.report/'missing_source_dates.json',missing)
 output=[];groups=weekly_groups(dates)
 for monday,indices in groups:
  means,area,valid=summarize(values[indices],w);iso=monday.isocalendar()
  for i,s in enumerate(scopes):
   mean=None if not np.isfinite(means[i]) else float(means[i])
   output.append({'scope_id':s['scope_id'],'scope_name':s['scope_name'],'iso_year':iso.year,'iso_week':iso.week,'week_start':str(monday),'week_end':str(monday+dt.timedelta(days=6)),'period_start':str(dates[indices[0]]),'period_end':str(dates[indices[-1]]),'days_expected':7,'days_in_requested_range':len(indices),'source_days':sum(dates[j] in observed for j in indices),'precip_total_mm':mean,'precip_total_in':None if mean is None else mean/25.4,'covered_area_km2':float(area[i]),'total_area_km2':float(w[i].sum()),'coverage_fraction':float(area[i]/w[i].sum()),'status':'no_complete_cell' if mean is None else 'partial_week' if len(indices)<7 else 'computed','source_dataset_id':'noaa_cpc_global_daily_v1_rt'})
 table(a.output/'weekly_all_scopes_2021_2025.csv',output)
 for code,name in [('US50_DC','us50'),('CONUS48_DC','conus48'),('MD','maryland')]:table(a.output/f'weekly_{name}_2021_2025.csv',[r for r in output if r['scope_id']==code])
 for year in range(2021,2026):table(a.output/f'by_calendar_start_year/weekly_{year}.csv',[r for r in output if int(r['period_start'][:4])==year])
 annual=[]
 for year in range(2021,2026):
  indices=[j for j,d in enumerate(dates) if d.year==year];means,area,valid=summarize(values[indices],w)
  for i,s in enumerate(scopes):
   mean=None if not np.isfinite(means[i]) else float(means[i]);annual.append({'year':year,'scope_id':s['scope_id'],'scope_name':s['scope_name'],'precip_total_mm':mean,'precip_total_in':None if mean is None else mean/25.4,'covered_area_km2':float(area[i]),'total_area_km2':float(w[i].sum()),'coverage_fraction':float(area[i]/w[i].sum()),'days_expected':len(indices),'source_days':sum(dates[j] in observed for j in indices),'status':'computed' if mean is not None else 'no_complete_cell'})
 table(a.output/'annual_summary_2021_2025.csv',annual)
 grouped={}
 for r in output:grouped.setdefault(r['week_start'],{})[r['scope_id']]=r
 max_difference=0.
 for week,group in grouped.items():
  children=[group[s['scope_id']] for s in scopes[:51]];denominator=sum(c['covered_area_km2'] for c in children)
  if denominator:
   direct=sum(c['precip_total_mm']*c['covered_area_km2'] for c in children if c['precip_total_mm'] is not None)/denominator;max_difference=max(max_difference,abs(direct-group['US50_DC']['precip_total_mm']))
 assert max_difference<1e-8
 assert len({(r['scope_id'],r['week_start']) for r in output})==len(output)
 assert all(r['precip_total_mm'] is None or r['precip_total_mm']>=0 for r in output)
 assert all(0<=r['coverage_fraction']<=1+1e-12 for r in output)
 assert all(r['precip_total_mm'] is None or abs(r['precip_total_mm']/25.4-r['precip_total_in'])<1e-10 for r in output)
 validation={'target_years':[2021,2022,2023,2024,2025],'scope_count':len(scopes),'states_plus_dc':51,'week_count':len(groups),'weekly_rows':len(output),'annual_rows':len(annual),'daily_dates_expected':len(dates),'source_dates_observed':len(observed),'missing_source_dates':missing,'selected_grid_cells':len(rr),'full_weeks':sum(len(idx)==7 for _,idx in groups),'partial_boundary_weeks':sum(len(idx)<7 for _,idx in groups),'weekly_rows_with_no_complete_cell':sum(r['precip_total_mm'] is None for r in output),'weekly_rows_below_90pct_coverage':sum(r['coverage_fraction']<.9 for r in output),'national_vs_state_weighted_max_difference_mm':max_difference,'checks':['source date uniqueness and year','source units mm','stable global grid','51 FIPS states including AK/HI/DC','scope+week_start unique','nonnegative precipitation','coverage bounds','mm/inch conversion','independent national/state aggregation'],'completed_at_utc':dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00','Z')}
 save(a.report/'validation.json',validation);print(json.dumps({'stage':'done',**validation}),flush=True)
if __name__=='__main__':main()
