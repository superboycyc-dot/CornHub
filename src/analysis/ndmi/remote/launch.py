"""Resource-bounded local launcher for the NVIDIA host; no remote login or provisioning."""
import argparse
import csv
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time


def inventory(cache):
    cache=Path(cache);cache.mkdir(parents=True,exist_ok=True)
    cpus=len(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else os.cpu_count() or 1
    try:
        quota,period=Path('/sys/fs/cgroup/cpu.max').read_text().split()
        if quota!='max':cpus=min(cpus,max(1,int(quota)//int(period)))
    except (OSError,ValueError):pass
    try:available=os.sysconf('SC_AVPHYS_PAGES')*os.sysconf('SC_PAGE_SIZE')
    except (ValueError,OSError):available=4*1024**3
    try:
        limit=Path('/sys/fs/cgroup/memory.max').read_text().strip()
        used=int(Path('/sys/fs/cgroup/memory.current').read_text())
        if limit!='max':available=min(available,max(0,int(limit)-used))
    except (OSError,ValueError):pass
    gpus=[]
    if shutil.which('nvidia-smi'):
        r=subprocess.run(['nvidia-smi','--query-gpu=index,name,memory.total,memory.free',
            '--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=20,check=True)
        for row in csv.reader(io.StringIO(r.stdout)):
            gpus.append({'physical_index':int(row[0]),'name':row[1].strip(),
                'total_memory_mib':int(row[2]),'free_memory_mib':int(row[3])})
    return {'cpu_slots':cpus,'available_ram_gb':available/1024**3,
        'free_disk_gb':shutil.disk_usage(cache).free/1024**3,'gpus':gpus,
        'cuda_visible_devices':os.environ.get('CUDA_VISIBLE_DEVICES','not set')}


def worker_plan(resources,backend,requested='auto'):
    # Reserve 2 GiB RAM/disk and approximately 2 GiB RAM + 1.25 GiB disk per worker.
    cap=min(resources['cpu_slots'],16,int((resources['available_ram_gb']-2)//2),
        int((resources['free_disk_gb']-2)//1.25))
    if cap<1:raise RuntimeError('Need at least 4 GiB available RAM and 3.25 GiB free disk')
    visible=0
    if backend=='gpu':
        import cupy as cp
        visible=cp.cuda.runtime.getDeviceCount()
        if visible<1:raise RuntimeError('GPU requested but no visible CUDA GPU')
        if visible>cap:raise RuntimeError('Not enough host resources for one worker on every visible GPU')
    workers=cap if requested=='auto' else int(requested)
    if workers<1 or workers>cap:raise ValueError(f'workers must be between 1 and resource cap {cap}')
    if backend=='gpu' and workers<visible:raise ValueError('Use at least one worker per visible GPU')
    # Two workers per GPU at most; more contexts generally waste device memory.
    if backend=='gpu' and requested=='auto':workers=min(cap,max(visible,2*visible))
    return {'backend':backend,'workers':workers,'visible_gpu_count':visible,'resource_cap':cap}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cache',type=Path,required=True)
    p.add_argument('--output',type=Path,default=Path('data/processed/analysis/ndmi/months'))
    p.add_argument('--report',type=Path,default=Path('reports/d_analysis/ndmi/remote'))
    p.add_argument('--backend',choices=['cpu','gpu'],default='cpu')
    p.add_argument('--workers',default='auto')
    p.add_argument('--year',type=int,choices=range(2021,2026))
    p.add_argument('--month',type=int,choices=range(1,13))
    p.add_argument('--plan-only',action='store_true')
    a=p.parse_args()
    root=Path(__file__).resolve().parents[4]
    resources=inventory(a.cache)
    plan=worker_plan(resources,a.backend,a.workers)
    command=[sys.executable,str(root/'src/analysis/ndmi/calculate.py'),'--cache',str(a.cache.resolve()),
        '--output',str(a.output.resolve()),'--workers',str(plan['workers']),'--backend',a.backend,
        '--gpu-ids','all','--max-scene-errors','3','--retry-incomplete']
    if a.year:command += ['--year',str(a.year)]
    if a.month:command += ['--month',str(a.month)]
    record={'resources':resources,'plan':plan,'command':command,'plan_only':a.plan_only}
    a.report.mkdir(parents=True,exist_ok=True)
    (a.report/'launch_plan.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record),flush=True)
    if a.plan_only:return
    env=os.environ.copy()
    for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:env[key]='1'
    start=time.perf_counter()
    result=subprocess.run(command,cwd=root,env=env)
    record.update(exit_code=result.returncode,wall_seconds=time.perf_counter()-start)
    (a.report/'last_run.json').write_text(json.dumps(record,indent=2)+'\n')
    raise SystemExit(result.returncode)

if __name__=='__main__':main()
