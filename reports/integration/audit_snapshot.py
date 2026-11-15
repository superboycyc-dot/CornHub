"""Read-only repository audit; emits JSON to stdout, without running notebooks."""
import ast
import csv
import hashlib
import json
import platform
import sqlite3
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def rows(path):
    with (ROOT / path).open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def file_info(path):
    file = ROOT / path
    if not file.exists():
        return {"path": path, "exists": False}
    return {"path": path, "exists": True, "bytes": file.stat().st_size,
            "sha256": hashlib.sha256(file.read_bytes()).hexdigest()}


def main():
    raw_path = "01_QuickStats/corn_grain_silage_acres_2012_2025_raw.csv"
    ca_path = "data/processed/usda_nass/california_corn_acreage_annual_reference_2012_2025.csv"
    label_path = "data/processed/barc_field_year_labels.csv"
    gpkg_path = "04_Evaluation/BARC_Corn.2021-2023.gpkg"
    notebook_path = "05_Model/barc_sentinel2_baseline.ipynb"
    raw, ca, labels = rows(raw_path), rows(ca_path), rows(label_path)
    layer = "barc_silage_grain_corn20212023"
    with sqlite3.connect(f"file:{ROOT / gpkg_path}?mode=ro", uri=True) as connection:
        count, farms = connection.execute(
            f'SELECT COUNT(*), COUNT(DISTINCT FARM_ID) FROM "{layer}"'
        ).fetchone()
        contents = connection.execute(
            "SELECT table_name, srs_id FROM gpkg_contents"
        ).fetchall()
        source_counts = {}
        for year in [2021, 2022, 2023]:
            source_counts[str(year)] = dict(connection.execute(
                f'SELECT "Corn_{year}", COUNT(*) FROM "{layer}" '
                f'WHERE "Corn_{year}" IN (\'Grain\', \'Silage\') GROUP BY "Corn_{year}"'
            ).fetchall())
    notebook = json.loads((ROOT / notebook_path).read_text())
    code_cells = [c for c in notebook["cells"] if c["cell_type"] == "code"]
    parsed_cells = 0
    for cell in code_cells:
        source = "".join(cell["source"])
        if source.startswith("%pip"):
            continue
        ast.parse(source)
        parsed_cells += 1
    scripts = ["scripts/curate_quickstats.py", "scripts/prepare_barc_labels.py",
               "01_QuickStats/download_corn_acres.py"]
    for script in scripts:
        ast.parse((ROOT / script).read_text())
    expected = ["core/fields.geojson", "core/labels.csv", "core/smoke_sample.json",
                "core/validation_folds.csv", "satellite/timeseries.csv",
                "satellite/features.csv", "model/predictions.csv", "model/metrics.json",
                "analysis/summary.json", "analysis/review_queue.csv"]
    result = {
        "audited_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "head_before_documentation_commit": git("rev-parse", "HEAD"),
        "origin_main_at_audit": git("rev-parse", "origin/main"),
        "python_version": platform.python_version(),
        "scope": "Local checkout and fetched origin/main; no inspection of teammates' private workspaces.",
        "barc": {"source_features": count, "distinct_farms_in_source": farms,
                 "gpkg_contents": contents, "source_label_counts": source_counts,
                 "exported_rows": len(labels), "exported_unique_fields": len({r['field_id'] for r in labels}),
                 "exported_unique_field_years": len({(r['field_id'], r['year']) for r in labels})},
        "quickstats": {"raw_rows": len(raw), "california_rows": len(ca),
                       "states": sorted({r['state_name'] for r in ca}),
                       "by_year": dict(sorted(Counter(r['year'] for r in ca).items())),
                       "unique_series_keys": len({(r['year'], r['aggregation_level'], r['state_ansi'],
                                                    r['county_ansi'], r['short_description']) for r in ca}),
                       "california_2025": [r for r in ca if r['year'] == '2025']},
        "notebook": {"code_cells": len(code_cells), "ast_parsed_cells": parsed_cells,
                     "skipped_magic_cells": len(code_cells) - parsed_cells,
                     "saved_executed_cells": sum(c.get('execution_count') is not None for c in code_cells),
                     "saved_output_blocks": sum(len(c.get('outputs', [])) for c in code_cells),
                     "execution_performed_by_audit": False},
        "parsed_scripts": scripts,
        "contract_outputs": [{"path": "data/processed/" + p,
                              "exists": (ROOT / "data/processed" / p).exists()} for p in expected],
        "web_directory_exists": (ROOT / "web").is_dir(),
        "files": [file_info(p) for p in [raw_path, ca_path, label_path, gpkg_path, notebook_path,
                  "data/processed/usda_nass/corn_state_benchmarks_2025.csv",
                  "data/usda_nass_cdl/california/manifest.json", *scripts]],
        "not_checked": ["Satellite retrieval, raster values, CRS transformations and geometry validity",
                        "Training, accuracy, calibration, geographic transfer or area uncertainty",
                        "CDL ZIP CRC, raster resolution or archive SHA re-verification",
                        "External NASS source correctness or reason for conflicting 2025 values",
                        "Other branches' unpublished work, deployment or hackathon submission status"],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
