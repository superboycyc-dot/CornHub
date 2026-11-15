import concurrent.futures,subprocess,pathlib,os,time
url='https://www.nass.usda.gov/sites/default/files/Research_and_Science/Crop-Sequence-Boundaries/datasets/NationalCSB_2016-2023_rev23.zip'
out=pathlib.Path('data/raw/external_corn/NationalCSB_2016-2023_rev23.zip')
size=3505346935;chunk=32*1024*1024
out.parent.mkdir(parents=True,exist_ok=True)
if out.exists() and out.stat().st_size != 0:
 raise RuntimeError('Existing CSB raw file: validate it or move it before fresh download')
with out.open('wb') as f:f.truncate(size)
fd=os.open(out,os.O_WRONLY)
def fetch(i):
 start=i*chunk;end=min(size-1,start+chunk-1);p=pathlib.Path('/tmp/cornhub-csb-part-'+str(i))
 for attempt in range(5):
  r=subprocess.run(['curl','-sSL','--fail','--max-time','180','--range',f'{start}-{end}','--max-filesize',str(chunk+1),'-o',str(p),url+'?part='+str(i)],capture_output=True)
  if r.returncode==0 and p.stat().st_size==end-start+1:
   os.pwrite(fd,p.read_bytes(),start);p.unlink();return i
  print('retry',i,attempt,r.stderr.decode()[:90],flush=True)
 raise RuntimeError('Failed chunk '+str(i))
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
 for n,i in enumerate(pool.map(fetch,range((size+chunk-1)//chunk)),1):print('completed',n,'chunks',flush=True)
os.close(fd)
