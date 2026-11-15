import numpy as np
import pytest
import rasterio
from rasterio.io import MemoryFile
from rasterio.transform import from_origin
from rasterio.warp import transform_geom

from satellite import imagery


def test_mask_denominator_includes_clouds_and_nodata():
    red = np.array([[.1, np.nan], [.1, .1]])
    nir = np.array([[.3, .3], [.3, .3]])
    result = imagery.ndvi_statistics(red, nir, np.array([[4, 4], [3, 9]]), np.ones((2, 2), bool))
    assert result["valid_pixel_fraction"] == .25
    assert result["ndvi"] == pytest.approx(.5)


def test_zero_sum_and_out_of_range_ratios_are_missing():
    result = imagery.ndvi_statistics(np.array([[0., -.1]]), np.array([[0., .2]]), np.array([[4, 4]]), np.array([[True, True]]))
    assert result["ndvi"] is None and result["valid_pixel_fraction"] == 0


def test_no_pixel_centers_is_explicit_blocker():
    with pytest.raises(ValueError, match="No 10m"):
        imagery.ndvi_statistics(np.ones((1, 1)), np.ones((1, 1)), np.ones((1, 1)), np.zeros((1, 1), bool))


def test_real_raster_operations_on_isolated_synthetic_fixture(monkeypatch):
    # In-memory synthetic rasters never enter data/processed or production reports.
    files = {}
    original_open = rasterio.open
    red = np.full((4, 4), 2000, np.uint16); red[0, 0] = 0
    arrays = {"red": red, "nir": np.full((4, 4), 4000, np.uint16), "scl": np.array([[4, 5], [3, 9]], np.uint8)}
    try:
        for name, array in arrays.items():
            mem = MemoryFile(); files[name] = mem
            resolution = 20 if name == "scl" else 10
            with mem.open(driver="GTiff", width=array.shape[1], height=array.shape[0], count=1, dtype=array.dtype, crs="EPSG:32618", transform=from_origin(400000, 4300000, resolution, resolution), nodata=0) as dst:
                dst.write(array, 1)
        monkeypatch.setattr(imagery.rasterio, "open", lambda url: original_open(files[url.rsplit("/", 1)[-1]].name))
        item = dict(properties={"s2:processing_baseline": "unit_only"}, assets={name: dict(href="https://unit.test/" + name, **{"raster:bands": [dict(nodata=0, scale=.0001, offset=-.1)]}) for name in arrays})
        polygon = dict(type="Polygon", coordinates=[[(400000, 4300000), (400040, 4300000), (400040, 4299960), (400000, 4299960), (400000, 4300000)]])
        geometry = transform_geom("EPSG:32618", "EPSG:4326", polygon)
        stats, provenance = imagery.observe(item, geometry)
        assert stats["field_pixels"] == 16 and stats["valid_pixels"] == 7
        assert stats["valid_pixel_fraction"] == 7 / 16
        assert stats["ndvi"] == pytest.approx(.5)
        assert provenance["radiometry"]["red"]["offset"] == -.1
        assert provenance["resampling"] == "nearest"
    finally:
        for mem in files.values():
            mem.close()


def test_missing_scale_blocks_processing():
    class Dataset:
        nodata = 0
    with pytest.raises(ValueError, match="scale"):
        imagery.asset_parameters({}, Dataset(), reflectance=True)
