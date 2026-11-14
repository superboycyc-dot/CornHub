"""Deterministic date selection and feature definitions from team-contract.md."""
import math
from datetime import date


def summarize(rows, sample, empty_reason="no_scenes_returned"):
    start = date.fromisoformat(sample["window_start"])
    end = date.fromisoformat(sample["window_end_exclusive"])
    seen = set()
    daily = {}
    for row in rows:
        if row["field_id"] != sample["field_id"] or int(row["year"]) != sample["year"]:
            raise ValueError("Mixed field/year in smoke timeseries")
        if row["sensor"] != "sentinel2_l2a" or not row["scene_id"] or not row["source_dataset_id"]:
            raise ValueError("Invalid sensor or missing scene/source identifier")
        when = date.fromisoformat(row["date"])
        if not start <= when < end:
            raise ValueError("Observation outside contract window")
        key = (row["field_id"], int(row["year"]), row["date"], row["scene_id"])
        if key in seen:
            raise ValueError("Duplicate timeseries key")
        seen.add(key)
        fraction = float(row["valid_pixel_fraction"])
        if not math.isfinite(fraction) or not 0 <= fraction <= 1:
            raise ValueError("Invalid valid_pixel_fraction")
        ndvi = row["ndvi"]
        if ndvi is not None and (not math.isfinite(float(ndvi)) or not -1 <= float(ndvi) <= 1):
            raise ValueError("Invalid NDVI; do not clip invalid reflectance ratios")
        previous = daily.get(when)
        if previous is None or (-fraction, row["scene_id"]) < (-float(previous["valid_pixel_fraction"]), previous["scene_id"]):
            daily[when] = row
    valid = [(d, float(r["ndvi"])) for d, r in sorted(daily.items()) if float(r["valid_pixel_fraction"]) >= 0.5 and r["ndvi"] is not None]
    dates = [d for d, value in valid]
    gaps = [(b - a).days for a, b in zip([start] + dates, dates + [end])]
    max_gap = max(gaps)
    n = len(valid)
    result = dict(field_id=sample["field_id"], year=sample["year"], ndvi_peak=None, peak_doy=None, max_drop_per_day=None, drop_doy=None, ndvi_late_mean=None, valid_obs_count=n, max_gap_days=max_gap, quality_flag="no_data" if not n else "insufficient" if n == 1 else "limited" if n < 6 or max_gap > 30 else "usable", missing_reason="")
    reasons = []
    if valid:
        peak_date, peak = min(valid, key=lambda item: (-item[1], item[0]))
        result.update(ndvi_peak=peak, peak_doy=peak_date.timetuple().tm_yday)
        if n >= 2:
            drops = [(max(0., (a[1] - b[1]) / (b[0] - a[0]).days), b[0]) for a, b in zip(valid, valid[1:])]
            # Equal decimal rates can differ at machine precision (e.g. .7-.5 vs .5-.3).
            drop = max(rate for rate, day in drops)
            day = min(day for rate, day in drops if math.isclose(rate, drop, rel_tol=1e-12, abs_tol=1e-12))
            result.update(max_drop_per_day=drop, drop_doy=day.timetuple().tm_yday if drop > 0 else None)
        else:
            reasons.append("fewer_than_two_valid_days")
        late = [v for d, v in valid if date(sample["year"], 9, 1) <= d < end]
        if late:
            result["ndvi_late_mean"] = sum(late) / len(late)
        else:
            reasons.append("no_valid_late_season_observations")
        if result["quality_flag"] == "limited":
            if n < 6:
                reasons.append("fewer_than_six_valid_days")
            if max_gap > 30:
                reasons.append("gap_exceeds_30_days")
    else:
        reasons.append("no_days_meeting_pixel_quality_threshold" if rows else empty_reason)
    result["missing_reason"] = ";".join(reasons)
    return result, [dict(row) for _, row in sorted(daily.items())]
