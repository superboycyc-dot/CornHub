"""A-label-driven batch execution, gated on a successful real smoke run."""
import copy
import csv
import hashlib
from pathlib import Path

from .contracts import FEATURE_COLUMNS, TIMESERIES_COLUMNS, load_json, load_sample, write_csv, write_json
from .pipeline import run, utc_now


def make_plan(args):
    sample, _ = load_sample(args.fields, args.sample)
    fields = load_json(args.fields)
    by_id = {f["properties"]["field_id"]: f for f in fields["features"]}
    with Path(args.labels).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"field_id", "year", "label", "label_raw", "source_dataset_id"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError("A labels.csv must use the core handoff schema")
        rows = list(reader)
    if not rows:
        raise ValueError("A labels.csv is empty; no batch identifiers will be invented")
    seen, plan = set(), []
    for row in rows:
        fid = row["field_id"]
        year = int(row["year"])
        if fid not in by_id or year not in (2021, 2022, 2023) or row["label"] not in {"grain", "silage"}:
            raise ValueError("Invalid A label field/year/class; no silent row dropping")
        if (fid, year) in seen:
            raise ValueError("Duplicate A label field_id+year")
        seen.add((fid, year))
        source = by_id[fid]["properties"]["source_dataset_id"]
        if row["source_dataset_id"] != source:
            raise ValueError("A label/field source_dataset_id mismatch")
        request = dict(field_id=fid, year=year, window_start=f"{year}-04-01", window_end_exclusive=f"{year}-12-01", selection_rule="Existing labeled A field-year; no B-generated identifiers or labels", source_dataset_id=source)
        # Preserve A's exact common sample request so its existing receipts are reusable.
        if (fid, year) == (sample["field_id"], sample["year"]):
            request = dict(sample)
        plan.append(request)
    plan.sort(key=lambda r: (r["field_id"], r["year"]))
    return plan


def run_batch(args):
    report_path = Path(args.reports) / "batch_report.json"
    try:
        proof = load_json(args.smoke_report)
        if proof.get("status") != "completed" or not proof.get("real_sample_computed") or not proof.get("valid_obs_count", 0):
            raise ValueError("A real smoke run must complete successfully before batch processing")
        plan = make_plan(args)
    except (OSError, ValueError, KeyError, TypeError) as error:
        write_json(report_path, dict(status="blocked", issues=[str(error)], finished_at_utc=utc_now()))
        print(str(error), flush=True)
        return 2
    selected = plan[:args.limit] if args.limit is not None else plan
    report = dict(status="planned" if args.dry_run else "running", started_at_utc=utc_now(), label_field_year_count=len(plan), selected_field_year_count=len(selected), plan=selected, full_label_list_selected=len(selected) == len(plan), completed_field_years=0, runs=[], raw_imagery_written=False)
    write_json(report_path, report)
    if args.dry_run:
        print(f"Validated {len(plan)} real A label keys; selected {len(selected)}; no scene queries or imagery reads.", flush=True)
        return 0
    observations, features, issues = [], [], []
    for sample in selected:
        key = hashlib.sha256(f"{sample['field_id']}:{sample['year']}".encode()).hexdigest()[:16]
        sub = copy.copy(args)
        sub.command = "smoke"
        sub.reports = Path(args.reports) / "batch_runtime" / key
        sub.output = Path(args.output) / "batch" / key
        sub.sample = sub.reports / "sample_request.json"
        write_json(sub.sample, sample)
        code = run(sub)
        child = load_json(sub.reports / "run_report.json")
        report["runs"].append(dict(field_id=sample["field_id"], year=sample["year"], exit_code=code, status=child["status"], valid_obs_count=child.get("valid_obs_count"), cache_hits=child.get("cache_hits", 0)))
        if code:
            issues.append(dict(field_id=sample["field_id"], year=sample["year"], status=child["status"]))
        else:
            report["completed_field_years"] += 1
        for name, target in [("timeseries.csv", observations), ("features.csv", features)]:
            with (sub.output / name).open(encoding="utf-8", newline="") as stream:
                target.extend(csv.DictReader(stream))
        write_json(report_path, report)
    # No silently missing keys or cross-year duplication in downstream handoff.
    feature_keys = [(r["field_id"], r["year"]) for r in features]
    if len(set(feature_keys)) != len(feature_keys):
        raise ValueError("Unexpected duplicate feature keys in batch output")
    write_csv(Path(args.output) / "timeseries.csv", TIMESERIES_COLUMNS, observations)
    write_csv(Path(args.output) / "features.csv", FEATURE_COLUMNS, features)
    report.update(status="partial" if issues else "completed", issues=issues, finished_at_utc=utc_now(), observation_rows=len(observations), feature_rows=len(features))
    write_json(report_path, report)
    return 2 if issues else 0
