"""Smoke orchestration, source receipts, and explicit blockers."""
import ast
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import requests

from .contracts import (FEATURE_COLUMNS, SOURCE_COLUMNS, TIMESERIES_COLUMNS,
                        load_json, load_sample, write_csv, write_json)
from .features import summarize
from .imagery import ALGORITHM_VERSION, COLLECTION, ENDPOINT, observe, search


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def audit_notebook(path, report):
    notebook = load_json(path)
    if notebook.get("nbformat") != 4 or not isinstance(notebook.get("cells"), list):
        raise ValueError("Official notebook is not valid nbformat 4")
    imports, definitions, findings = set(), set(), []
    for index, cell in enumerate(notebook["cells"]):
        if cell.get("cell_type") != "code":
            continue
        source = "".join(cell.get("source", [])) if isinstance(cell.get("source"), list) else cell.get("source", "")
        # Inventory only; do not execute an unreviewed notebook or persist secrets/outputs.
        try:
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.add(node.module)
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    definitions.add(node.name)
        except SyntaxError:
            pass  # notebook magics are not Python AST
        for pattern, label in [(r"stac|catalog|search\(", "catalog_or_search_reference"), (r"\bSCL\b|scene.class", "scl_reference"), (r"ndvi", "ndvi_reference"), (r"scale|offset", "radiometry_reference")]:
            if re.search(pattern, source, re.IGNORECASE):
                findings.append(dict(cell_index=index, signal=label))
    audit = dict(status="inventoried_not_executed", source_filename=Path(path).name, sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest(), cells=len(notebook["cells"]), imports=sorted(imports), defined_functions=sorted(definitions), signals=findings, limitation="Text/AST inventory is not verification that masking, scaling, or search is correct; manual code review is required before claiming official-notebook adaptation.")
    write_json(Path(report) / "starter_notebook_audit.json", audit)
    return audit


def prerequisites(args):
    issues = []
    paths = [(args.notebook, "official_notebook_missing", "Download 03_Geospatial_References/starter_notebook.ipynb from the logged-in team JupyterLab and save to notebooks/b_satellite/starter_notebook.ipynb. Do not commit it until redistribution permission is confirmed."),
             (args.fields, "a_fields_missing", "A must provide data/processed/core/fields.geojson from the official BARC data."),
             (args.sample, "a_smoke_sample_missing", "A must provide data/processed/core/smoke_sample.json selected by the contract; B does not invent field_id, year or labels.")]
    for path, code, action in paths:
        if not Path(path).is_file():
            issues.append(dict(code=code, action=action))
    audit = None
    if Path(args.notebook).is_file():
        try:
            audit = audit_notebook(args.notebook, args.reports)
        except (ValueError, KeyError, TypeError) as error:
            issues.append(dict(code="invalid_official_notebook", action=str(error)))
    sample = feature = None
    if Path(args.fields).is_file() and Path(args.sample).is_file():
        try:
            sample, feature = load_sample(args.fields, args.sample)
        except (ValueError, KeyError, TypeError) as error:
            issues.append(dict(code="invalid_a_handoff", action=str(error)))
    return issues, sample, feature, audit


def probe_catalog(reports):
    try:
        response = requests.get(ENDPOINT + "/collections/" + COLLECTION, timeout=(15, 45))
        response.raise_for_status()
        collection = response.json()
        result = dict(status="reachable", checked_at_utc=utc_now(), source_url=response.url, collection=collection["id"], catalog_license=collection.get("license", "unknown"), note="Collection metadata request only; no field or scene query and no raster read.")
    except (requests.RequestException, ValueError, KeyError) as error:
        result = dict(status="blocked", checked_at_utc=utc_now(), error=str(error), note="No claim of scene availability.")
    write_json(Path(reports) / "catalog_probe.json", result)
    return result


def sources(reports):
    write_csv(Path(reports) / "sources.csv", SOURCE_COLUMNS, [
        dict(source_dataset_id="earthsearch_sentinel2_l2a", organization="ESA / Sinergise / Element 84 / AWS", source_url=ENDPOINT + "/collections/" + COLLECTION, product_version="Sentinel-2 L2A; scene processing baseline recorded separately", retrieved_at_utc=utc_now(), license="unknown", notes="Catalog declares proprietary; consult Copernicus terms. No original imagery redistributed. Timestamp is catalog retrieval/run time, not a claim of successful scene acquisition."),
        dict(source_dataset_id="cornhub_team_contract", organization="CornHub", source_url="https://github.com/superboycyc-dot/CornHub/blob/main/docs/team-contract.md", product_version="contract added in b603997; official files in 51d5989", retrieved_at_utc=utc_now(), license="unknown", notes="Contract defines BARC 2021-2023, superseding older README scope for this task."),
        dict(source_dataset_id="official_sentinel2_starter", organization="Hack the Harvest organizers", source_url="https://github.com/superboycyc-dot/CornHub/blob/51d5989/03_Geospatial_References/sentinel-2_starter_notebook.ipynb", product_version="51d5989; 14 cells", retrieved_at_utc=utc_now(), license="unknown", notes="Actual notebook reviewed; see notebook_review.md and SHA256 in starter_notebook_audit.json. Original remains unmodified.")])


def empty_outputs(output):
    output = Path(output)
    for name, columns in [("timeseries.csv", TIMESERIES_COLUMNS), ("features.csv", FEATURE_COLUMNS)]:
        if not (output / name).exists():
            write_csv(output / name, columns, [])


def finish(args, report):
    report["finished_at_utc"] = utc_now()
    write_json(Path(args.reports) / "run_report.json", report)
    lines = ["# B satellite execution report", "", f"Status: `{report['status']}`", "", f"Valid observation days: {report.get('valid_obs_count', 'not computed')}", ""]
    for issue in report.get("issues", []):
        lines.extend([f"- `{issue['code']}`: {issue['action']}"])
    lines.extend(["", "Official notebook is now available in the repository as `03_Geospatial_References/sentinel-2_starter_notebook.ipynb`; see `notebook_review.md`. No manual download is currently required.", "", "If unavailable in another checkout, download `03_Geospatial_References/starter_notebook.ipynb` from the team JupyterLab to `notebooks/b_satellite/starter_notebook.ipynb`.", "", "A owns the official BARC boundary/label extraction and must deliver `data/processed/core/fields.geojson` and `smoke_sample.json`.", "", "Missing inputs are not evidence of zero cloud-free observations. Header-only handoff tables contain no invented fields, labels or observations."])
    (Path(args.reports) / "BLOCKERS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0 if report["status"] in {"ready", "completed"} else 2


def plot_observations(rows, daily, sample, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(10, 4))
    low = [r for r in rows if r["ndvi"] is not None and r["valid_pixel_fraction"] < .5]
    high = [r for r in daily if r["ndvi"] is not None and r["valid_pixel_fraction"] >= .5]
    if low:
        ax.scatter([datetime.fromisoformat(r["date"]) for r in low], [r["ndvi"] for r in low], marker="x", color="gray", label="Excluded: valid pixels < 50%")
    if high:
        ax.scatter([datetime.fromisoformat(r["date"]) for r in high], [r["ndvi"] for r in high], label="Selected valid daily observations")
    ax.set(xlabel="UTC observation date (no interpolation)", ylabel="Field median NDVI", ylim=(-1, 1), title=f"{sample['field_id']} / {sample['year']} — {len(high)} valid days")
    ax.set_xlim(datetime.fromisoformat(sample["window_start"]), datetime.fromisoformat(sample["window_end_exclusive"]))
    ax.legend()
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def run(args):
    Path(args.reports).mkdir(parents=True, exist_ok=True)
    Path(args.output).mkdir(parents=True, exist_ok=True)
    empty_outputs(args.output)
    issues, sample, feature, audit = prerequisites(args)
    catalog = probe_catalog(args.reports)
    if catalog["status"] != "reachable":
        issues.append(dict(code="catalog_unreachable", action="Public catalog metadata probe failed; see catalog_probe.json. Do not claim scene availability."))
    sources(args.reports)
    report = dict(status="blocked" if issues else "ready", started_at_utc=utc_now(), command=args.command, algorithm_version=ALGORITHM_VERSION, issues=issues, catalog_probe=catalog, real_sample_computed=False, valid_obs_count=None, missing_data_status="not_computed", official_notebook_reviewed=bool(audit and args.notebook_reviewed), scope="BARC 2021–2023; latest team contract; no California weather upload in B's PR")
    if audit is not None:
        report["official_notebook_inventory"] = audit
    if issues or args.command == "preflight":
        return finish(args, report)
    # The user may provide the notebook after the initial blocked delivery. Do not claim
    # its functionality verified merely because AST inventory succeeded.
    if not args.notebook_reviewed:
        report.update(status="blocked")
        report["issues"].append(dict(code="official_notebook_review_required", action="Review the actual notebook code and its AST inventory, then pass --notebook-reviewed. This flag records a human/agent code review, not automatic proof."))
        return finish(args, report)
    report["official_notebook_reviewed"] = True
    report["sample"] = sample
    try:
        items = search(sample, feature["geometry"])
    except (requests.RequestException, ValueError, KeyError) as error:
        report.update(status="blocked", issues=[dict(code="stac_search_failed", action=str(error))])
        return finish(args, report)
    write_json(Path(args.reports) / "scene_inventory.json", dict(retrieved_at_utc=utc_now(), collection=COLLECTION, geometry=feature["geometry"], window_start=sample["window_start"], window_end_exclusive=sample["window_end_exclusive"], scenes=items))
    rows, provenance = [], []
    for index, item in enumerate(items):
        print(f"Scene {index + 1}/{len(items)}: {item['id']}", flush=True)
        try:
            stats, parameters = observe(item, feature["geometry"], max_pixels=args.max_window_pixels)
            row = dict(field_id=sample["field_id"], year=sample["year"], date=datetime.fromisoformat(item["properties"]["datetime"].replace("Z", "+00:00")).astimezone(timezone.utc).date().isoformat(), sensor="sentinel2_l2a", scene_id=item["id"], ndvi=stats["ndvi"], valid_pixel_fraction=stats["valid_pixel_fraction"], source_dataset_id="earthsearch_sentinel2_l2a")
            rows.append(row)
            provenance.append(dict(scene_id=item["id"], source_url=f"{ENDPOINT}/collections/{COLLECTION}/items/{item['id']}", observed_at_utc=item["properties"]["datetime"], retrieved_at_utc=utc_now(), source_field_dataset_id=sample["source_dataset_id"], stats=stats, parameters=parameters))
        except Exception as error:
            report["issues"].append(dict(code="scene_read_failed", action=f"{item['id']}: {type(error).__name__}: {error}"))
    result, daily = summarize(rows, sample, "no_scenes_returned" if not items else "all_scene_reads_failed")
    if report["issues"]:
        result["missing_reason"] = ";".join(filter(None, [result["missing_reason"], "scene_read_failures_see_report"]))
    write_csv(Path(args.output) / "timeseries.csv", TIMESERIES_COLUMNS, rows)
    write_csv(Path(args.output) / "features.csv", FEATURE_COLUMNS, [result])
    write_json(Path(args.reports) / "scene_provenance.json", provenance)
    if result["valid_obs_count"]:
        plot_observations(rows, daily, sample, Path(args.reports) / "ndvi_timeseries.png")
    report.update(status="partial" if report["issues"] else "completed" if result["valid_obs_count"] else "blocked_no_valid_observations", real_sample_computed=True, scene_count=len(items), processed_scene_count=len(rows), valid_obs_count=result["valid_obs_count"], max_gap_days=result["max_gap_days"], quality_flag=result["quality_flag"], missing_data_status=result["missing_reason"] or "none")
    if not result["valid_obs_count"]:
        report["issues"].append(dict(code="no_valid_observation_days", action="No real NDVI chart generated. Inspect scene availability, cloud masks and read errors; do not interpolate missing observations."))
    return finish(args, report)
