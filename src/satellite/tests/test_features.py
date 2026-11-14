"""Isolated synthetic unit checks only: these are never published as observations."""
from datetime import date, timedelta

import pytest

from satellite.features import summarize


SAMPLE = dict(field_id="barc_unit_test_only", year=2022, window_start="2022-04-01", window_end_exclusive="2022-12-01")


def row(day, ndvi, fraction=1, scene="scene_unit_only"):
    return dict(field_id=SAMPLE["field_id"], year=2022, date=day, sensor="sentinel2_l2a", scene_id=scene, ndvi=ndvi, valid_pixel_fraction=fraction, source_dataset_id="unit_test_only")


def test_no_data_is_not_a_zero_ndvi():
    result, daily = summarize([], SAMPLE)
    assert result["ndvi_peak"] is None and result["ndvi_late_mean"] is None
    assert result["valid_obs_count"] == 0 and result["quality_flag"] == "no_data"
    assert result["max_gap_days"] == 244 and daily == []


def test_dedup_threshold_tie_break_peak_and_drop():
    rows = [row("2022-04-01", .9, .49, "low_quality"), row("2022-09-01", .8, .8, "b"), row("2022-09-01", .7, .8, "a"), row("2022-09-11", .5), row("2022-09-21", .3)]
    result, daily = summarize(rows, SAMPLE)
    assert len(daily) == 4 and daily[1]["scene_id"] == "a"
    assert result["valid_obs_count"] == 3 and result["ndvi_peak"] == .7
    assert result["peak_doy"] == 244 and result["drop_doy"] == 254
    assert result["max_drop_per_day"] == pytest.approx(.02)
    assert result["ndvi_late_mean"] == pytest.approx(.5)
    assert result["quality_flag"] == "limited"


def test_single_observation_and_no_decline():
    one, _ = summarize([row("2022-08-01", .3)], SAMPLE)
    assert one["quality_flag"] == "insufficient" and one["max_drop_per_day"] is None
    assert "no_valid_late_season_observations" in one["missing_reason"]
    flat, _ = summarize([row("2022-09-01", .5), row("2022-09-11", .5)], SAMPLE)
    assert flat["max_drop_per_day"] == 0 and flat["drop_doy"] is None
    assert flat["peak_doy"] == 244


def test_usable_requires_coverage_at_both_boundaries():
    days = [(date(2022, 4, 1) + timedelta(days=28 * i)).isoformat() for i in range(9)]
    good, _ = summarize([row(d, .5) for d in days], SAMPLE)
    assert good["quality_flag"] == "usable" and good["max_gap_days"] == 28
    short, _ = summarize([row(d, .5) for d in days[3:]], SAMPLE)
    assert short["quality_flag"] == "limited" and short["max_gap_days"] == 84


@pytest.mark.parametrize("bad", [float("nan"), 1.1, -1.1])
def test_invalid_ratios_fail_instead_of_clipping(bad):
    with pytest.raises(ValueError):
        summarize([row("2022-09-01", bad)], SAMPLE)


def test_duplicate_scene_keys_fail():
    with pytest.raises(ValueError, match="Duplicate"):
        summarize([row("2022-09-01", .5)] * 2, SAMPLE)


def test_missing_ndvi_is_never_a_valid_day():
    result, _ = summarize([row("2022-09-01", None)], SAMPLE)
    assert result["valid_obs_count"] == 0 and result["ndvi_peak"] is None
