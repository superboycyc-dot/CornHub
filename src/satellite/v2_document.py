"""Write explicit field definitions and reproducibility metadata (no credentials)."""
import json,sys,platform,subprocess
from pathlib import Path
import importlib.metadata as md
from global_v2 import OUT,REPORT,write_csv,write_json,sha

def main():
    # Stable artifact bytes across Windows/Linux, including reproducibility hashes.
    for root in [OUT,REPORT]:
        for path in root.rglob('*'):
            if path.is_file() and '.cache' not in path.parts and path.suffix in ['.csv','.json','.geojson','.md','.txt']:
                path.write_text(path.read_text(encoding='utf-8'),encoding='utf-8',newline='\n')
    rows=[]
    def add(field,unit,algorithm,missing='empty/null;never zero-filled',table='features'):
        rows.append(dict(table=table,field=field,unit=unit,algorithm=algorithm,missing_rule=missing))
    add('entity_id','identifier','source namespace + source version + region/year + unchanged cropfield ID;NL namespaced UUID','required','all')
    add('year','calendar year','source_year;not a predictor','required','all')
    add('ndvi_peak','index','max accepted daily NDVI;min1 valid day')
    add('peak_doy','day of year','DOY of peak;earliest tie;min1 valid day')
    add('max_drop_per_day','index/day','max(0,(NDVI_previous-NDVI_next)/elapsed_days) over adjacent accepted days;min2 days;no interpolation')
    add('drop_doy','day of year','DOY of later endpoint of maximum drop;earliest tie;requires strictly positive drop')
    add('ndvi_late_mean','index','arithmetic mean of accepted daily NDVI in [Sep1,Dec1);min1 late day')
    add('valid_obs_count','days','number of accepted NDVI days;fraction>=0.5 AND >=3 valid pixels AND finite NDVI','0 is measured count;not filled NDVI')
    add('max_gap_days','days','maximum successive gap in [Apr1]+accepted_dates+[Dec1];no valid day=244 days in these years','always defined')
    add('quality_flag','category','no_data=0 days;insufficient=1;limited=2..5 OR max_gap>30;usable otherwise;not predictive accuracy','required')
    add('missing_reason','reason codes','explicit acquisition/geometric/temporal insufficiency;none means empty string','empty string when no identified gaps')
    add('date','UTC date','STAC datetime date;[Apr1,Dec1)','required','timeseries')
    add('sensor','category','sentinel2_l2a','required','timeseries')
    add('scene_id','identifier','PC product item ID;NL retained Earth Search ID;physical dedupe by satellite/sensing/tile,not catalog ID','required','timeseries')
    add('source_dataset_id','identifier','satellite provider provenance;source label dataset separately in selection','required','timeseries')
    for ix,formula in [('ndvi','(B08-B04)/(B08+B04)'),('ndmi','(B08-B11)/(B08+B11)')]:
        add(ix,'index',f'median of {formula} over individually valid band supports;float64 reflectance=(DN+XML_BOA_ADD_OFFSET)/XML_BOA_QUANTIFICATION_VALUE;min3 valid pixels;positive denominator;range[-1,1]','null if fewer than3 valid pixels;NDMI missing does not remove NDVI','timeseries')
        add(ix+'_valid_pixels','10m target pixels',f'10m inward-buffer pixel centers with SCL4,5,6,7;per-band raw NODATA masked;finite valid {ix};B11 nearest20m->10m','0 valid pixels allowed;unread observations absent','timeseries')
        add(ix+'_total_pixels','10m target pixels','all native B04 10m grid centers in 10m inward buffer;includes cloud/nodata/noncoverage;unobservable if <3','zero/too-small interior is unobservable;no zero-valued index','timeseries')
        add(ix+'_valid_fraction','fraction',ix+'_valid_pixels / '+ix+'_total_pixels','undefined/null for zero denominator;NDMI unknown in legacy NL','timeseries')
    add('source_field_id','identifier','EuroCrops cropfield (not off_id);off_id separately retained in acceptance labels;NL original field_id UUID','required','selection')
    add('source_region','category','unchanged source region','required','selection')
    add('selection_reason','text','seed20261114;4 regions x2 labels x5 rank-area quintiles x5 draws','required','selection')
    write_csv(OUT/'feature_dictionary.csv',rows)
    sources=[
        ('eurocrops_v2_gpqtv202','European Commission JRC','https://jeodpp.jrc.ec.europa.eu/ftp/public/JRC-OpenData/DRLL/EuroCropsV2/','gpqtv202','CC BY 4.0','annual declared crop-use labels;original EPSG3035;no satellite training inputs implied'),
        ('planetary_computer_sentinel2_l2a','Microsoft / ESA','https://planetarycomputer.microsoft.com/api/stac/v1/collections/sentinel-2-l2a','STAC1.0 collection checked2026-11-14','Copernicus Sentinel data terms','B04,B08 10m;B11,SCL20m;product-metadata XML;unsigned product asset references'),
        ('pc_crop_api','Microsoft','https://planetarycomputer.microsoft.com/api/data/v1/openapi.json','live OpenAPI checked2026-11-14','unknown','feature.tif;unscale=false;native10m grid verified;nearest;extra alpha ignored;raw per-band nodata'),
        ('pc_sas_api','Microsoft','https://planetarycomputer.microsoft.com/api/sas/v1/openapi.json','live OpenAPI checked2026-11-14','unknown','container token reused in memory only;no persisted token or signed URL'),
        ('esa_radiometry','ESA','https://sentiwiki.copernicus.eu/web/s2-products','live documentation checked2026-11-14','unknown','L2A reflectance=(DN+BOA_ADD_OFFSET)/QUANTIFICATION_VALUE;actual values parsed from each product XML'),
        ('earthsearch_sentinel2_l2a_legacy_nl','Element84 / ESA','https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a','legacy scenes retained','Copernicus Sentinel data terms','existing8 dates;SCL4,5;10m erosion;scale.0001;EarthSearch boa_offset_applied=true handled by original script;not mixed with new PC pixel policy'),
        ('nl_rvo_brp_2025','RVO / PDOK','https://api.pdok.nl/rvo/gewaspercelen/ogc/v1','2025','unknown','134 original annual declared fields;121 silage13 grain;UUID source IDs'),
        ('quebec_bdppad','La Financiere agricole du Quebec','https://www.fadq.qc.ca/documents/donnees/base-de-donnees-des-parcelles-et-productions-agricoles-declarees/','2025','https://www.donneesquebec.ca/licence/','39653 grain-only fields;excluded from first two-class pilot;NAD83 metadata in crs_audit.json')]
    write_csv(REPORT/'sources.csv',[dict(source_dataset_id=s[0],organization=s[1],source_url=s[2],product_version=s[3],retrieved_at_utc='2026-11-14',license=s[4],notes=s[5]) for s in sources])
    write_json(REPORT/'runtime_versions.json',dict(python=sys.version,platform=platform.platform(),packages={k:md.version(k) for k in ['numpy','pandas','pyarrow','pyproj','rasterio','shapely','requests','matplotlib']}))
    manifest=json.loads((REPORT/'input_manifest.json').read_text());manifest['main_contract_sha256']=__import__('hashlib').sha256(subprocess.check_output(['git','show','origin/main:docs/team-contract.md'])).hexdigest();manifest['selection_rule']='4 dual-class regions x2 labels x5 area rank quintiles x5 seeded draws';manifest['acquisition_budget_rule']='initial one min-catalog-cloud candidate per fixed 10day bin from Apr1;field SCL controls acceptance;gapfill pending where necessary';manifest['legacy_netherlands_separate']=True
    manifest['selection_file']='data/processed/v2/satellite/selection.csv'
    manifest['selection_sha256']=sha(OUT/'selection.csv')
    manifest['sample_keys']=[dict(entity_id=r['entity_id'],year=int(r['year'])) for r in __import__('csv').DictReader((OUT/'selection.csv').open(encoding='utf-8'))]
    manifest['main_contract_reviewed_sha']=subprocess.check_output(['git','rev-parse','origin/main']).decode().strip()
    manifest['selected_geometry_sha256']=sha(REPORT/'selected_fields.geojson')
    manifest['algorithm_version']=__import__('v2_acquire').VERSION
    source=Path(__file__).parent
    manifest['code_files_sha256']={p.relative_to(source.parents[1]).as_posix():sha(p) for p in list(source.glob('v2_*.py'))+[source/'global_v2.py',source/'requirements-v2.txt']}
    manifest['official_api_snapshots']={p.name:sha(p) for p in (REPORT/'.cache/official_docs').glob('*.json')}
    write_json(REPORT/'input_manifest.json',manifest)
    for path in REPORT.rglob('*.json'):
        if '.cache' not in path.parts:
            text=path.read_text(encoding='utf-8')
            if '+00:00' in text:path.write_text(text.replace('+00:00','Z'),encoding='utf-8',newline='\n')
    print('Wrote dictionary, sources and runtime metadata')
if __name__=='__main__':main()
