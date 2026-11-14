"""Optional CuPy backend; CPU remains the default. No silent GPU fallback."""
import numpy as np

_NAME='cpu'
_CP=None
_DEVICE=None


def configure(backend='cpu', gpu_ids=None, worker_index=0):
    global _NAME,_CP,_DEVICE
    if backend not in ('cpu','gpu'):raise ValueError('backend must be cpu or gpu')
    _NAME=backend;_CP=None;_DEVICE=None
    if backend=='gpu':
        import cupy as cp
        count=cp.cuda.runtime.getDeviceCount()
        ids=list(range(count)) if gpu_ids is None else list(gpu_ids)
        if not ids or any(i<0 or i>=count for i in ids):raise RuntimeError('No usable requested CUDA device')
        device=ids[worker_index%len(ids)]
        cp.cuda.Device(device).use()
        # Fail during initialization if CUDA kernels/runtime cannot execute.
        cp.sum(cp.arange(16)).get()
        _CP=cp;_DEVICE=device
    return {'backend':_NAME,'gpu_id':_DEVICE}


def info():return {'backend':_NAME,'gpu_id':_DEVICE}


def gpu_ndmi(nir_dn,swir_dn,qa,sat):
    if _NAME!='gpu' or _CP is None:raise RuntimeError('GPU backend not initialized')
    cp=_CP
    n,s,q,r=[cp.asarray(x) for x in (nir_dn,swir_dn,qa,sat)]
    nir=n.astype(cp.float64)*0.0000275-0.2
    swir=s.astype(cp.float64)*0.0000275-0.2
    valid=((n!=0)&(s!=0)&((q&63)==0)&((r&((1<<4)|(1<<5)|(1<<11)))==0)
        &(nir>=0)&(swir>=0)&((nir+swir)>0))
    value=cp.full(nir.shape,cp.nan,dtype=cp.float32)
    cp.divide(nir-swir,nir+swir,out=value,where=valid)
    valid &= cp.isfinite(value)&(value>=-1)&(value<=1)
    # asnumpy synchronizes the transfers; caller timing includes both directions.
    return cp.asnumpy(value),cp.asnumpy(valid)
