import concurrent.futures,subprocess,pathlib,os,hashlib
url='https://zenodo.org/api/records/19501943/files/cropsight-us_app_dat_v1.0.1.zip/content'
out=pathlib.Path('data/raw/external_corn/cropsight-us_app_dat_v1.0.1.parallel.zip');size=297267115;chunk=8*1024*1024
out.parent.mkdir(parents=True,exist_ok=True)
if not out.exists():
 with out.open('wb') as handle:handle.truncate(size)
fd=os.open(out,os.O_RDWR)
def fetch(i):
 start=i*chunk;end=min(size,start+chunk);n=end-start
 try:
  if os.lseek(fd,start,os.SEEK_HOLE)>=end:return i
 except OSError:pass
 part=pathlib.Path('/tmp/cornhub-cropsight-part-'+str(i))
 for attempt in range(8):
  have=part.stat().st_size if part.exists() else 0
  if have==n:
   os.pwrite(fd,part.read_bytes(),start);part.unlink();return i
  rem=part.with_suffix('.remain');headers=part.with_suffix('.headers')
  r=subprocess.run(['curl','-sSL','--fail','--max-time','300','--range',f'{start+have}-{end-1}','--max-filesize',str(n-have),'-D',str(headers),'-o',str(rem),url],capture_output=True)
  if rem.exists() and '206' in headers.read_text():
   with part.open('ab') as f:f.write(rem.read_bytes())
   rem.unlink()
  print('part',i,'bytes',part.stat().st_size if part.exists() else 0,'status',r.returncode,flush=True)
 raise RuntimeError('Incomplete chunk '+str(i))
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
 for f in concurrent.futures.as_completed([pool.submit(fetch,i) for i in range((size+chunk-1)//chunk)]):print('completed',f.result(),flush=True)
os.close(fd)
h=hashlib.md5(out.read_bytes()).hexdigest();print('md5',h,flush=True);assert h=='8df463cd8d09210354a6e31f8cdcada7'
out.replace(out.with_name('cropsight-us_app_dat_v1.0.1.zip'))
