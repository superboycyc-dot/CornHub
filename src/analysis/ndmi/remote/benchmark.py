"""Compare CPU/GPU on identical raw input tiles, including host/device transfers."""
import argparse
import json
from pathlib import Path
import statistics
import sys
import time
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from calculate import ndmi
from compute_backend import configure


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input-npz',type=Path,help='Real same-grid uint16 nir08/swir16/qa_pixel/qa_radsat tile')
    p.add_argument('--synthetic',action='store_true',help='Explicit synthetic performance test; never an observation')
    p.add_argument('--output',type=Path,default=Path('reports/d_analysis/ndmi/remote/backend_benchmark.json'))
    p.add_argument('--repeats',type=int,default=10)
    a=p.parse_args()
    if bool(a.input_npz)==a.synthetic:p.error('Choose exactly one of --input-npz and --synthetic')
    if a.repeats<1:p.error('repeats must be positive')
    if a.synthetic:
        rng=np.random.default_rng(42)
        arrays=[rng.integers(7500,40000,(1024,1024),dtype=np.uint16) for _ in range(2)]
        arrays += [np.full((1024,1024),64,dtype=np.uint16),np.zeros((1024,1024),dtype=np.uint16)]
        source='synthetic performance inputs; not satellite observations'
    else:
        with np.load(a.input_npz) as z:arrays=[z[k] for k in ['nir08','swir16','qa_pixel','qa_radsat']]
        source=str(a.input_npz)
    if any(x.dtype!=np.uint16 for x in arrays) or len({x.shape for x in arrays})!=1:
        raise ValueError('Require four equal-shaped uint16 raw tiles')
    output={'input':source,'shape':list(arrays[0].shape),'timing_includes':'kernel, allocation and host/device transfers',
        'observation_result':False,'benchmarks':[],'gpu_parity_passed':False,'recommended_backend':'cpu'}
    configure('cpu');reference=ndmi(*arrays)
    backends=[('cpu',None)]
    try:
        import cupy as cp
        backends += [('gpu',i) for i in range(cp.cuda.runtime.getDeviceCount())]
    except Exception as exc:output['gpu_unavailable']=type(exc).__name__
    for name,device in backends:
        configure(name,None if device is None else [device])
        got=ndmi(*arrays)  # warm-up includes initial compilation, excluded from steady timing
        np.testing.assert_array_equal(got[1],reference[1])
        np.testing.assert_allclose(got[0][reference[1]],reference[0][reference[1]],rtol=0,atol=1e-7)
        durations=[]
        for _ in range(a.repeats):
            start=time.perf_counter();ndmi(*arrays);durations.append(time.perf_counter()-start)
        output['benchmarks'].append({'backend':name,'gpu_id':device,'parity':'passed',
            'median_seconds':statistics.median(durations),'repeats':a.repeats})
    gpu=[b for b in output['benchmarks'] if b['backend']=='gpu']
    output['gpu_parity_passed']=bool(gpu)
    if gpu and max(b['median_seconds'] for b in gpu)<output['benchmarks'][0]['median_seconds']:
        output['recommended_backend']='gpu'
    output['notes']='Kernel benchmark only; full pipeline may still be dominated by download, reprojection or disk.'
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(output,indent=2)+'\n');print(json.dumps(output))

if __name__=='__main__':main()
