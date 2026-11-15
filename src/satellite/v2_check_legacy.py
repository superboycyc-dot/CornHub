"""Cross-catalog radiometry spot-check of existing NL values, not new independent rows."""
import argparse,json
from pathlib import Path
import pandas as pd
from global_v2 import REPORT,write_json
from v2_acquire import catalog,calibration,observe,clean
def physical(uri):
    p=uri.split('_');return (p[0],p[2],p[5])
def main(source):
    folder=source/'data/global_maize/netherlands_2025';fc=json.loads((folder/'fields.geojson').read_text());fields={str(f['id']):f for f in fc['features']}
    rows=pd.read_csv(folder/'ndvi_all.csv',dtype={'field_id':str});idx=pd.read_csv(folder/'field_index.csv',dtype={'field_id':str});scenes={s['id']:s for s in json.loads((folder/'scenes.json').read_text())};checks=[]
    for label in ['grain','silage']:
        candidates=sorted(set(idx.loc[idx.harvest_label==label,'field_id']) & set(rows.loc[rows.ndvi_median.notna(),'field_id']))
        fid=candidates[0];f=dict(type='Feature',geometry=fields[fid]['geometry'],properties=dict(entity_id='nl_rvo_brp_2025_'+fid,year=2025))
        inventory=catalog(f)['features']
        for day in ['2025-06-12','2025-09-28']:
            legacy=rows[(rows.field_id==fid)&(rows.date==day)].iloc[0];original=scenes[legacy.scene];key=physical(original['properties']['s2:product_uri'])
            matching=[i for i in inventory if physical(i['properties']['s2:product_uri'])==key]
            if not matching:checks.append(dict(field_id=fid,date=day,status='no_PC_counterpart'));continue
            item=max(matching,key=lambda i:(i['properties'].get('s2:processing_baseline',''),i['properties'].get('s2:generation_time','')))
            cal=calibration(item);result=observe(item,f,cal)
            old=None if pd.isna(legacy.ndvi_median) else float(legacy.ndvi_median);new=result.get('ndvi')
            checks.append(dict(entity_id=f['properties']['entity_id'],date=day,legacy_scene_id=legacy.scene,pc_scene_id=item['id'],same_physical_observation=True,legacy_ndvi=old,pc_v2_ndvi=new,difference=new-old if new is not None and old is not None else None,legacy_total_pixels=int(legacy.interior_pixels),pc_total_pixels=result.get('ndvi_total_pixels'),legacy_valid_pixels=int(legacy.valid_pixels),pc_valid_pixels=result.get('ndvi_valid_pixels'),xml_calibration=cal,status=result['status'],interpretation='SCL4,5 legacy vs4,5,6,7 v2;rounding1e-5;not appended as independent observation',pixel_evidence=result.get('pixel_evidence',[])))
    write_json(REPORT/'netherlands_radiometry_spotcheck.json',checks);print('NL real cross-catalog checks',[(r['date'],r.get('difference'),r['status']) for r in checks])
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);main(p.parse_args().input)
