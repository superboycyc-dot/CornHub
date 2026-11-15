"""Fetch fixed-version public NOAA/Census inputs; large originals stay out of Git."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import time
import urllib.request
import urllib.error

NOAA='https://downloads.psl.noaa.gov/Datasets/cpc_global_precip/'
BOUNDARY='https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_state_20m.zip'


def fetch(url,path):
    path=Path(path);meta=path.with_suffix(path.suffix+'.source.json')
    if path.exists() and meta.exists():return json.loads(meta.read_text())
    path.parent.mkdir(parents=True,exist_ok=True)
    for attempt in range(4):
        try:
            sha=hashlib.sha256();n=0
            req=urllib.request.Request(url,headers={'User-Agent':'CornHub-weekly-precip/1.0'})
            with urllib.request.urlopen(req,timeout=60) as stream,path.with_suffix(path.suffix+'.part').open('wb') as out:
                for block in iter(lambda:stream.read(2*1024*1024),b''):
                    out.write(block);sha.update(block);n+=len(block)
                expected=stream.headers.get('Content-Length')
                if expected is not None and int(expected)!=n:raise IOError('Truncated source file')
            path.with_suffix(path.suffix+'.part').replace(path)
            from datetime import datetime,timezone
            record={'source_url':url,'filename':path.name,'bytes':n,'sha256':sha.hexdigest(),
                'retrieved_at_utc':datetime.now(timezone.utc).isoformat().replace('+00:00','Z')}
            meta.write_text(json.dumps(record,indent=2)+'\n')
            print(json.dumps({'downloaded':path.name,'bytes':n}),flush=True)
            return record
        except Exception as exc:
            if attempt==3:raise
            delay=int(exc.headers.get('Retry-After','10')) if isinstance(exc,urllib.error.HTTPError) and exc.code==429 else 2**attempt
            time.sleep(delay)


def inputs(cache,start_year=2021,end_year=2025):
    cache=Path(cache)
    jobs=[(NOAA+f'precip.{y}.nc',cache/f'precip.{y}.nc') for y in range(start_year,end_year+1)]
    jobs += [(BOUNDARY,cache/'cb_2024_us_state_20m.zip')]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        return list(pool.map(lambda j:fetch(*j),jobs))

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--cache',type=Path,default=Path('/tmp/cornhub_weekly_precip'))
    a=p.parse_args();inputs(a.cache)
