"""Validate A-owned inputs without generating identifiers or labels."""
import csv
import json
import math
from datetime import date
from pathlib import Path

from shapely.geometry import shape

TIMESERIES_COLUMNS = "field_id year date sensor scene_id ndvi valid_pixel_fraction source_dataset_id".split()
FEATURE_COLUMNS = "field_id year ndvi_peak peak_doy max_drop_per_day drop_doy ndvi_late_mean valid_obs_count max_gap_days quality_flag missing_reason".split()
SOURCE_COLUMNS = "source_dataset_id organization source_url product_version retrieved_at_utc license notes".split()


def load_json(path):
    def reject(value):
        raise ValueError(f"Nonstandard JSON numeric value: {value}")
    def finite_float(value):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("JSON float overflows finite range")
        return number
    return json.loads(Path(path).read_text(encoding="utf-8"), parse_constant=reject, parse_float=finite_float)


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def write_csv(path, columns, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def load_sample(fields_path, sample_path):
    sample = load_json(sample_path)
    if not isinstance(sample, dict):
        raise ValueError("smoke_sample must be a JSON object")
    required = {"field_id", "year", "window_start", "window_end_exclusive", "selection_rule", "source_dataset_id"}
    if not required.issubset(sample):
        raise ValueError(f"smoke_sample missing: {sorted(required - sample.keys())}")
    if not isinstance(sample["field_id"], str) or not sample["field_id"].startswith("barc_"):
        raise ValueError("field_id must be A's nonempty barc_ string")
    if len(sample["field_id"]) <= 5 or type(sample["year"]) is not int or sample["year"] not in (2021, 2022, 2023):
        raise ValueError("BARC smoke sample requires an A-owned ID and integer year 2021–2023")
    for key in ("selection_rule", "source_dataset_id"):
        if not isinstance(sample[key], str) or not sample[key].strip():
            raise ValueError(f"{key} must be a nonempty string")
    year = sample["year"]
    if (sample["window_start"], sample["window_end_exclusive"]) != (f"{year}-04-01", f"{year}-12-01"):
        raise ValueError("Window differs from contract [04-01,12-01); request a contract change first")
    date.fromisoformat(sample["window_start"])
    date.fromisoformat(sample["window_end_exclusive"])
    collection = load_json(fields_path)
    if collection.get("type") != "FeatureCollection" or not isinstance(collection.get("features"), list):
        raise ValueError("fields.geojson must be a FeatureCollection")
    crs = collection.get("crs")
    if crs and crs.get("properties", {}).get("name") not in {"EPSG:4326", "urn:ogc:def:crs:OGC:1.3:CRS84", "urn:ogc:def:crs:EPSG::4326"}:
        raise ValueError("GeoJSON must be EPSG:4326, longitude then latitude")
    ids = set()
    selected = None
    for feature in collection["features"]:
        props = feature.get("properties", {})
        fid = props.get("field_id")
        if not isinstance(fid, str) or not fid.startswith("barc_") or len(fid) <= 5 or fid in ids:
            raise ValueError("Every field_id must be a unique A-owned barc_ string")
        ids.add(fid)
        if not isinstance(props.get("source_field_id"), str) or not props["source_field_id"].strip():
            raise ValueError("source_field_id must preserve the original string ID")
        if not isinstance(props.get("source_dataset_id"), str) or not props["source_dataset_id"].strip():
            raise ValueError("Every field must have source_dataset_id")
        area = props.get("area_ha")
        if isinstance(area, bool) or not isinstance(area, (int, float)) or not math.isfinite(area) or area <= 0:
            raise ValueError("A must supply positive area_ha; B does not infer it from degrees")
        geometry = shape(feature.get("geometry"))
        if geometry.geom_type not in {"Polygon", "MultiPolygon"} or geometry.is_empty or not geometry.is_valid:
            raise ValueError(f"Invalid polygon for {fid}; return to A rather than silently repairing")
        west, south, east, north = geometry.bounds
        if not (-180 <= west <= east <= 180 and -90 <= south <= north <= 90):
            raise ValueError("Coordinates are not EPSG:4326 bounds")
        if fid == sample["field_id"]:
            selected = feature
    if selected is None:
        raise ValueError("smoke_sample field_id not found in fields.geojson")
    if selected["properties"]["source_dataset_id"] != sample["source_dataset_id"]:
        raise ValueError("Sample and field source_dataset_id disagree; A must reconcile provenance")
    return sample, selected
