from argparse import Namespace
import json
import pytest

from satellite import pipeline


def test_derived_cache_resumes_and_invalidates_geometry(tmp_path, monkeypatch):
    calls = []
    def fake_observe(item, geometry, max_pixels):
        calls.append(geometry)
        return dict(ndvi=.5, valid_pixel_fraction=1., field_pixels=1, valid_pixels=1), dict(test_fixture_only=True)
    monkeypatch.setattr(pipeline, "observe", fake_observe)
    args = Namespace(cache=tmp_path, max_window_pixels=10)
    item, sample = dict(id="unit_only"), dict(field_id="barc_unit_only", year=2021)
    first = pipeline.process_scene(item, sample, {"unit_only": 1}, args)
    again = pipeline.process_scene(item, sample, {"unit_only": 1}, args)
    assert not first["cache_hit"] and again["cache_hit"] and len(calls) == 1
    assert first["retrieved_at_utc"] == again["retrieved_at_utc"]
    pipeline.process_scene(item, sample, {"unit_only": 2}, args)
    assert len(calls) == 2
    receipt = tmp_path / (first["cache_key"] + ".json")
    receipt.write_text('{"interrupted":')
    repaired = pipeline.process_scene(item, sample, {"unit_only": 1}, args)
    assert not repaired["cache_hit"] and len(calls) == 3
    assert json.loads(receipt.read_text())["stats"]["ndvi"] == .5


def test_offline_cache_miss_does_not_invent_or_fetch(tmp_path, monkeypatch):
    def no_network(*args, **kwargs):
        pytest.fail("Offline mode must not call the remote raster reader")
    monkeypatch.setattr(pipeline, "observe", no_network)
    with pytest.raises(RuntimeError, match="cache_miss"):
        pipeline.process_scene(dict(id="unit_only"), dict(field_id="barc_unit_only"), {}, Namespace(cache=tmp_path, offline=True))
    assert not list(tmp_path.glob("*.json"))
