import json

import pytest

from satellite.contracts import load_json, load_sample, write_json


def inputs(tmp_path):
    sample = dict(field_id="barc_0001_unit_only", year=2022, window_start="2022-04-01", window_end_exclusive="2022-12-01", selection_rule="unit_test_not_for_delivery", source_dataset_id="unit_only")
    fields = dict(type="FeatureCollection", features=[dict(type="Feature", properties=dict(field_id=sample["field_id"], source_field_id="0001", source_dataset_id="unit_only", area_ha=1), geometry=dict(type="Polygon", coordinates=[[[-76, 39], [-75.999, 39], [-75.999, 39.001], [-76, 39.001], [-76, 39]]]))])
    f, s = tmp_path / "fields.geojson", tmp_path / "sample.json"
    f.write_text(json.dumps(fields)); s.write_text(json.dumps(sample))
    return f, s, fields, sample


def test_preserves_leading_zeros_and_a_identifier(tmp_path):
    f, s, _, _ = inputs(tmp_path)
    sample, field = load_sample(f, s)
    assert field["properties"]["source_field_id"] == "0001"
    assert sample["field_id"] == "barc_0001_unit_only"


def test_no_silent_window_change(tmp_path):
    f, s, _, sample = inputs(tmp_path)
    sample["window_end_exclusive"] = "2022-11-01"
    s.write_text(json.dumps(sample))
    with pytest.raises(ValueError, match="Window"):
        load_sample(f, s)


def test_duplicate_field_and_unknown_sample_fail(tmp_path):
    f, s, fields, sample = inputs(tmp_path)
    fields["features"] *= 2
    f.write_text(json.dumps(fields))
    with pytest.raises(ValueError, match="unique"):
        load_sample(f, s)
    fields["features"] = fields["features"][:1]
    f.write_text(json.dumps(fields))
    sample["field_id"] = "barc_unknown_unit_only"
    s.write_text(json.dumps(sample))
    with pytest.raises(ValueError, match="not found"):
        load_sample(f, s)


def test_json_nan_rejected(tmp_path):
    p = tmp_path / "bad.json"; p.write_text('{"x":NaN}')
    with pytest.raises(ValueError):
        load_json(p)


def test_compressed_inventory_roundtrip_is_lossless_and_deterministic(tmp_path):
    p = tmp_path / "inventory.json.gz"
    value = dict(collection="unit_only", scenes=[dict(id="unit_only", scale=.0001)])
    write_json(p, value)
    original = p.read_bytes()
    assert load_json(p) == value
    write_json(p, value)
    assert p.read_bytes() == original
