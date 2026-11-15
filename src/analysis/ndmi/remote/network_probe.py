"""Check actual public NDMI sources, including a signed COG byte range. No secrets logged."""
import argparse
import datetime as dt
import json
from pathlib import Path
import time
import urllib.request
import urllib.parse
import urllib.error


def fetch(url,body=None,byte_range=False):
    headers={'User-Agent':'CornHub-NDMI-network-probe/1.0'}
    if byte_range:headers['Range']='bytes=0-1023'
    if body is not None:headers['Content-Type']='application/json'
    data=None if body is None else json.dumps(body).encode()
    for attempt in range(2):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,data=data,headers=headers),timeout=20) as f:
                raw=f.read(1024) if byte_range else f.read()
                return raw if byte_range else json.loads(raw)
        except urllib.error.HTTPError as exc:
            if exc.code!=429 or attempt:raise
            time.sleep(int(exc.headers.get('Retry-After','10')))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    checks=[];item=None
    def check(name,fn):
        start=time.perf_counter()
        try:
            value=fn();checks.append({'source':name,'passed':True,'seconds':time.perf_counter()-start});return value
        except Exception as exc:
            checks.append({'source':name,'passed':False,'seconds':time.perf_counter()-start,
                'error_type':type(exc).__name__,'http_status':getattr(exc,'code',None)})
    def cdl():
        u='https://pdi.scinet.usda.gov/image/rest/services/CDL_WM/ImageServer/query?'+urllib.parse.urlencode({
            'where':'Year >= 2021 AND Year <= 2025','outFields':'Year','returnGeometry':'false','f':'json'})
        r=fetch(u)
        if {f['attributes']['Year'] for f in r.get('features',[])}!=set(range(2021,2026)):
            raise ValueError('Requested CDL years not returned')
    def boundary():
        u='https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer/0/query?'+urllib.parse.urlencode({
            'where':"STATE='24'",'outFields':'STATE','returnGeometry':'false','f':'json'})
        if len(fetch(u).get('features',[]))!=1:raise ValueError('Maryland query failed')
    def catalog():
        r=fetch('https://planetarycomputer.microsoft.com/api/stac/v1/search',{
            'collections':['landsat-c2-l2'],'ids':['LC08_L2SP_015033_20210716_02_T1'],'limit':1})
        return r['features'][0]
    check('USDA annual CDL',cdl);check('Census Maryland boundary',boundary)
    item=check('Planetary Computer Landsat catalog',catalog)
    if item:
        def cog():
            unsigned=item['assets']['nir08']['href'];u=urllib.parse.urlsplit(unsigned)
            token=fetch(f'https://planetarycomputer.microsoft.com/api/sas/v1/token/{u.netloc.split(".")[0]}/{u.path.split("/")[1]}')['token'].lstrip('?')
            raw=fetch(unsigned+'?'+token,byte_range=True)
            if raw[:4] not in (b'II*\x00',b'II+\x00',b'MM\x00*',b'MM\x00+'):
                raise ValueError('Expected TIFF header')
        check('Landsat blob + public signing + TIFF range',cog)
    passed=len(checks)==4 and all(c['passed'] for c in checks)
    result={'checked_at_utc':dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00','Z'),
        'passed':passed,'checks':checks,'signed_urls_saved':False}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result));raise SystemExit(0 if passed else 1)

if __name__=='__main__':main()
