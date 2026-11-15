from argparse import Namespace
import csv
import json

from satellite import pipeline
from satellite.contracts import FEATURE_COLUMNS, TIMESERIES_COLUMNS


def test_missing_official_files_publish_only_headers_and_block(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "probe_catalog", lambda _: dict(status="reachable", note="unit_test_only"))
    args = Namespace(command="smoke", fields=tmp_path / "missing_fields.geojson", sample=tmp_path / "missing_sample.json", notebook=tmp_path / "missing_notebook.ipynb", reports=tmp_path / "reports", output=tmp_path / "output", notebook_reviewed=False)
    assert pipeline.run(args) == 2
    report = json.loads((args.reports / "run_report.json").read_text())
    assert report["status"] == "blocked" and report["real_sample_computed"] is False
    assert report["valid_obs_count"] is None
    assert {r["code"] for r in report["issues"]} == {"official_notebook_missing", "a_fields_missing", "a_smoke_sample_missing"}
    for name, columns in [("features.csv", FEATURE_COLUMNS), ("timeseries.csv", TIMESERIES_COLUMNS)]:
        with (args.output / name).open() as stream:
            assert list(csv.reader(stream)) == [columns]
    assert not list(tmp_path.rglob("*.png"))
