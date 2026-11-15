import unittest
from unittest.mock import patch
import tempfile
import json
import gzip
import io
import contextlib
import calculate
from pathlib import Path
import importlib.util
import numpy as np
from compute_backend import configure
from calculate import ndmi

spec=importlib.util.spec_from_file_location('ndmi_launcher',Path(__file__).parent/'remote/launch.py')
launcher=importlib.util.module_from_spec(spec);spec.loader.exec_module(launcher)

class RemoteTests(unittest.TestCase):
    def test_scene_error_circuit_breaker(self):
        # Isolated synthetic plumbing fixture; no synthetic observation is published.
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);cache=root/'cache';cache.mkdir()
            grid={'left':1730000,'top':1930060,'width':2,'height':2}
            (cache/'grid.json').write_text(json.dumps(grid))
            np.save(cache/'corn_2021.npy',np.ones((2,2),dtype=bool))
            items=[{'id':f'test_scene_{i}','properties':{'datetime':f'2021-01-{i+1:02}T00:00:00Z','platform':'landsat-8','eo:cloud_cover':i},
                'geometry':{'type':'Polygon','coordinates':[[[-80,37],[-74,37],[-74,41],[-80,41],[-80,37]]]},
                'assets':{k:{'href':'https://example.invalid/test'} for k in calculate.BANDS}} for i in range(5)]
            with gzip.open(cache/'landsat_2021.json.gz','wt') as f:json.dump(items,f)
            with patch.object(calculate,'MAX_SCENE_ERRORS',2), patch.object(calculate,'signed_asset',side_effect=OSError('test offline')):
                with contextlib.redirect_stdout(io.StringIO()):r=calculate.month_job(2021,1,str(cache),str(root/'results'))
            self.assertEqual(r['status'],'failed_scene_errors')
            self.assertTrue(r['aborted_due_to_errors'])
            self.assertEqual(len(r['scene_errors']),2)
            self.assertEqual(r['unprocessed_scene_count'],3)
            self.assertIsNone(r['ndmi_mean'])

    def tearDown(self):configure('cpu')
    def test_resource_bounds(self):
        r={'cpu_slots':32,'available_ram_gb':10,'free_disk_gb':50}
        self.assertEqual(launcher.worker_plan(r,'cpu')['workers'],4)
        with self.assertRaises(ValueError):launcher.worker_plan(r,'cpu','8')
        with self.assertRaises(RuntimeError):launcher.worker_plan({**r,'free_disk_gb':2},'cpu')
    def test_unknown_backend_rejected(self):
        with self.assertRaises(ValueError):configure('imaginary')
    def test_gpu_equivalence_when_available(self):
        try:
            import cupy as cp
            if not cp.cuda.runtime.getDeviceCount():self.skipTest('No CUDA device')
        except ImportError:self.skipTest('CuPy not installed')
        rng=np.random.default_rng(8)
        arrays=[rng.integers(0,65536,(128,128),dtype=np.uint16) for _ in range(4)]
        configure('cpu');expected=ndmi(*arrays)
        # Check every visible GPU; a detected-but-broken CUDA stack must fail.
        for device in range(cp.cuda.runtime.getDeviceCount()):
            configure('gpu',[device]);actual=ndmi(*arrays)
            np.testing.assert_array_equal(actual[1],expected[1])
            np.testing.assert_allclose(actual[0][expected[1]],expected[0][expected[1]],atol=1e-7,rtol=0)

if __name__=='__main__':unittest.main()
