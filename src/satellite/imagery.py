"""Public STAC search and remote COG window reads; no full-scene downloads."""
from datetime import datetime, timedelta, timezone
import math
import os
import ssl

import numpy as np
import requests
# Some rasterio wheels inject a certifi GDAL_CA default at import time. Capture
# caller-provided trust settings first so a configured proxy CA is not replaced.
_CONFIGURED_CA = os.environ.get("GDAL_CURL_CA_BUNDLE") or os.environ.get("CURL_CA_BUNDLE") or os.environ.get("SSL_CERT_FILE")
import rasterio
from rasterio.enums import Resampling
from rasterio.features import geometry_mask
from rasterio.vrt import WarpedVRT
from rasterio.warp import transform_geom
from rasterio.windows import Window, from_bounds
from shapely.geometry import shape

ENDPOINT = "https://earth-search.aws.element84.com/v1"
COLLECTION = "sentinel-2-l2a"
ALGORITHM_VERSION = "barc-smoke-v1"
VALID_SCL = [4, 5, 6, 7]  # Preserve the official starter's whitelist, including bare soil.


def search(sample, geometry, session=None):
    session = session or requests.Session()
    end = datetime.fromisoformat(sample["window_end_exclusive"]).replace(tzinfo=timezone.utc) - timedelta(microseconds=1)
    body = dict(collections=[COLLECTION], intersects=geometry, datetime=f"{sample['window_start']}T00:00:00Z/{end.isoformat().replace('+00:00', 'Z')}", limit=100)
    url, method, payload = ENDPOINT + "/search", "POST", body
    items, page_keys = {}, set()
    for _ in range(100):
        key = (url, str(payload), method)
        if key in page_keys:
            raise ValueError("STAC repeated pagination link")
        page_keys.add(key)
        response = session.request(method, url, json=payload if method == "POST" else None, timeout=(15, 90))
        response.raise_for_status()
        page = response.json()
        for item in page["features"]:
            if item.get("collection") != COLLECTION:
                raise ValueError("Unexpected STAC collection")
            observed = datetime.fromisoformat(item["properties"]["datetime"].replace("Z", "+00:00")).astimezone(timezone.utc).date().isoformat()
            if not sample["window_start"] <= observed < sample["window_end_exclusive"]:
                raise ValueError("STAC returned out-of-window observation")
            items[item["id"]] = item
        following = next((link for link in page.get("links", []) if link["rel"] == "next"), None)
        if following is None:
            return sorted(items.values(), key=lambda item: (item["properties"]["datetime"], item["id"]))
        url, method = following["href"], following.get("method", "GET").upper()
        if not url.startswith(ENDPOINT + "/") or method not in {"GET", "POST"}:
            raise ValueError("Unexpected pagination endpoint or method")
        payload = dict(body, **following.get("body", {})) if following.get("merge") else following.get("body")
    raise ValueError("STAC pagination limit reached; refusing silent truncation")


def asset_parameters(asset, dataset, reflectance=False):
    bands = asset.get("raster:bands", [])
    metadata = bands[0] if len(bands) == 1 else {}
    nodata = metadata.get("nodata", dataset.nodata)
    if nodata is None:
        raise ValueError("Missing nodata metadata; refusing to interpret fill pixels as vegetation")
    if not reflectance:
        return dict(nodata=nodata)
    if "scale" not in metadata:
        raise ValueError("Missing explicit STAC reflectance scale; no baseline guess is allowed")
    # Raster Extension defines omitted offset as zero; never infer a baseline correction.
    scale, offset = float(metadata["scale"]), float(metadata.get("offset", 0))
    if not math.isfinite(scale) or not math.isfinite(offset) or scale <= 0:
        raise ValueError("Invalid radiometric metadata")
    return dict(nodata=nodata, scale=scale, offset=offset)


def ndvi_statistics(red, nir, scl, inside):
    """Denominator is all 10m centers in polygon, including nodata/cloud/coverage gaps."""
    denominator = int(inside.sum())
    if denominator == 0:
        raise ValueError("No 10m pixel centers within this field; no fractional/edge replacement")
    total = red + nir
    with np.errstate(divide="ignore", invalid="ignore"):
        ndvi = (nir - red) / total
    good = inside & np.isfinite(red) & np.isfinite(nir) & np.isin(scl, VALID_SCL) & (total > 1e-12) & np.isfinite(ndvi) & (ndvi >= -1) & (ndvi <= 1)
    numerator = int(good.sum())
    return dict(ndvi=float(np.median(ndvi[good])) if numerator else None, valid_pixel_fraction=numerator / denominator, valid_pixels=numerator, field_pixels=denominator)


def observe(item, geometry, max_pixels=2_000_000):
    assets = {name: item["assets"][name] for name in ("red", "nir", "scl")}
    if any(not asset["href"].startswith("https://") for asset in assets.values()):
        raise ValueError("Only public HTTPS COGs supported")
    # GDAL's bundled curl may not inherit Python/requests' system trust store.
    # Use the configured or OS CA bundle; never disable certificate verification.
    ca_bundle = _CONFIGURED_CA or ssl.get_default_verify_paths().cafile
    trust = dict(GDAL_CURL_CA_BUNDLE=ca_bundle, CURL_CA_BUNDLE=ca_bundle) if ca_bundle else {}
    # A persistent upstream 503 must not stall every queued scene for minutes.
    # Completed receipts survive; the explicit next run retries only missing reads.
    with rasterio.Env(GDAL_HTTP_TIMEOUT=20, GDAL_HTTP_MAX_RETRY=0, GDAL_CACHEMAX=64 * 1024 * 1024, GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif", **trust):
        with rasterio.open(assets["red"]["href"]) as reference:
            if reference.crs is None or reference.crs.is_geographic or not (math.isclose(abs(reference.res[0]), 10) and math.isclose(abs(reference.res[1]), 10)):
                raise ValueError("Expected projected 10m B04 reference grid")
            projected = transform_geom("EPSG:4326", reference.crs, geometry)
            raw_window = from_bounds(*shape(projected).bounds, transform=reference.transform)
            left, top = math.floor(raw_window.col_off), math.floor(raw_window.row_off)
            width = math.ceil(raw_window.col_off + raw_window.width) - left
            height = math.ceil(raw_window.row_off + raw_window.height) - top
            if width * height > max_pixels:
                raise ValueError("Field window exceeds memory guard; refusing a regional image read")
            transform = reference.window_transform(Window(left, top, width, height))
            inside = geometry_mask([projected], out_shape=(height, width), transform=transform, all_touched=False, invert=True)
            target_crs = reference.crs
        values, parameters = {}, {}
        for name, asset in assets.items():
            with rasterio.open(asset["href"]) as dataset:
                parameters[name] = asset_parameters(asset, dataset, name != "scl")
                with WarpedVRT(dataset, crs=target_crs, transform=transform, width=width, height=height, resampling=Resampling.nearest, src_nodata=parameters[name]["nodata"], nodata=float("nan"), dtype="float32") as vrt:
                    raw = vrt.read(1, masked=True).filled(float("nan"))
                values[name] = raw if name == "scl" else raw * parameters[name]["scale"] + parameters[name]["offset"]
    stats = ndvi_statistics(values["red"], values["nir"], values["scl"], inside)
    return stats, dict(asset_urls={k: v["href"] for k, v in assets.items()}, radiometry=parameters, processing_baseline=item["properties"].get("s2:processing_baseline"), boa_offset_applied=item["properties"].get("earthsearch:boa_offset_applied"), grid_crs=str(target_crs), grid_transform=list(transform), grid_shape=[height, width], valid_scl=VALID_SCL, resampling="nearest", edge_rule="pixel_center_inside_all_touched_false", algorithm_version=ALGORITHM_VERSION)
