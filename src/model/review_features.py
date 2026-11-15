"""Recompute B's contract features from committed real scene summaries, no imagery IO."""
import argparse
import csv
from datetime import date
import hashlib
import io
import math
from pathlib import Path
import subprocess

from .pipeline import write_json


def review(ref, output):
    def git(*args):
        return subprocess.check_output(['git', *args])
    commit = git('rev-parse', '--verify', '--end-of-options', ref + '^{commit}').decode().strip()
    def read(path):
        return git('show', commit + ':' + path)
    raw = read('data/processed/satellite/timeseries.csv')
    feature_raw = read('data/processed/satellite/features.csv')
    rows = list(csv.DictReader(io.StringIO(raw.decode('utf-8'))))
    features = list(csv.DictReader(io.StringIO(feature_raw.decode('utf-8'))))
    grouped, seen = {}, set()
    for r in rows:
        key = (r['field_id'], int(r['year']))
        when = date.fromisoformat(r['date'])
        assert date(key[1], 4, 1) <= when < date(key[1], 12, 1), 'outside contract window'
        scene_key = (*key, r['date'], r['scene_id'])
        assert scene_key not in seen, 'duplicate scene key'
        seen.add(scene_key)
        assert r['sensor'] == 'sentinel2_l2a' and r['source_dataset_id'], 'invalid provenance'
        assert math.isfinite(float(r['valid_pixel_fraction'])) and 0 <= float(r['valid_pixel_fraction']) <= 1
        if r['ndvi']:
            assert math.isfinite(float(r['ndvi'])) and -1 <= float(r['ndvi']) <= 1
        grouped.setdefault(key, []).append(r)
    feature_keys = {(r['field_id'], int(r['year'])) for r in features}
    assert len(feature_keys) == len(features) and feature_keys == set(grouped), 'feature/scene key mismatch'
    checks = []
    for f in features:
        key = (f['field_id'], int(f['year']))
        daily = {}
        for r in sorted(grouped[key], key=lambda r: (r['date'], -float(r['valid_pixel_fraction']), r['scene_id'])):
            daily.setdefault(r['date'], r)
        valid = [r for r in daily.values() if float(r['valid_pixel_fraction']) >= .5 and r['ndvi']]
        assert valid, 'no valid days in delivered feature'
        peak = min(valid, key=lambda r: (-float(r['ndvi']), r['date']))
        drops = [(max(0., (float(a['ndvi']) - float(b['ndvi'])) / (date.fromisoformat(b['date']) - date.fromisoformat(a['date'])).days), b['date']) for a, b in zip(valid, valid[1:])]
        maximum, drop_date = min(drops, key=lambda v: (-v[0], v[1])) if drops else (0., None)
        dates = [date(key[1], 4, 1), *[date.fromisoformat(r['date']) for r in valid], date(key[1], 12, 1)]
        late = [float(r['ndvi']) for r in valid if date(key[1], 9, 1) <= date.fromisoformat(r['date']) < date(key[1], 12, 1)]
        computed = dict(ndvi_peak=float(peak['ndvi']), peak_doy=date.fromisoformat(peak['date']).timetuple().tm_yday,
                        max_drop_per_day=maximum, drop_doy=date.fromisoformat(drop_date).timetuple().tm_yday if maximum > 0 else None,
                        ndvi_late_mean=sum(late) / len(late) if late else None, valid_obs_count=len(valid),
                        max_gap_days=max((b - a).days for a, b in zip(dates, dates[1:])))
        for col, value in computed.items():
            supplied = float(f[col]) if f[col] else None
            assert (value is None and supplied is None) or (value is not None and supplied is not None and math.isclose(value, supplied, rel_tol=1e-9, abs_tol=1e-9)), (key, col, value, supplied)
        n, gap = computed['valid_obs_count'], computed['max_gap_days']
        quality = 'insufficient' if n == 1 else 'limited' if n < 6 or gap > 30 else 'usable'
        assert quality == f['quality_flag'], (key, 'quality_flag')
        checks.append(dict(field_id=key[0], year=key[1], n_scene_rows=len(grouped[key]), n_selected_dates=len(daily),
                           n_valid_dates=n, n_late_season_valid_dates=len(late), max_gap_days=gap, quality_flag=quality, status='passed'))
    result = dict(status='passed', source_commit=commit, n_scene_rows=len(rows), n_feature_rows=len(features),
                  timeseries_sha256=hashlib.sha256(raw).hexdigest(), features_sha256=hashlib.sha256(feature_raw).hexdigest(),
                  tolerance=1e-9, checks=checks,
                  notes=['Independent recomputation from B scene summaries; not a rerun of imagery reads, scaling, SCL or geospatial aggregation.',
                         'Same-day highest valid fraction then scene_id, threshold 0.5, no interpolation; seven numeric features and quality checked.',
                         'No feature selection or tuning based on these checks. Quality is not probability reliability.'])
    write_json(output, result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--satellite-ref', required=True)
    parser.add_argument('--output', type=Path, default=Path('reports/c_model/upstream_review.json'))
    args = parser.parse_args()
    review(args.satellite_ref, args.output)


if __name__ == '__main__':
    main()
