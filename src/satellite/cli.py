import argparse
from pathlib import Path

from .pipeline import run


def main(argv=None):
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description="CornHub B: contract-validated real Sentinel-2 smoke pipeline")
    parser.add_argument("command", choices=["preflight", "smoke", "batch"])
    parser.add_argument("--fields", type=Path, default=root / "data/processed/core/fields.geojson")
    parser.add_argument("--sample", type=Path, default=root / "data/processed/core/smoke_sample.json")
    notebook = root / "03_Geospatial_References/sentinel-2_starter_notebook.ipynb"
    if not notebook.is_file():
        notebook = root / "notebooks/b_satellite/starter_notebook.ipynb"
    parser.add_argument("--notebook", type=Path, default=notebook)
    parser.add_argument("--output", type=Path, default=root / "data/processed/satellite")
    parser.add_argument("--reports", type=Path, default=root / "reports/b_satellite")
    parser.add_argument("--max-window-pixels", type=int, default=2_000_000)
    parser.add_argument("--notebook-reviewed", action="store_true", help="Record that the actual supplied official notebook code was reviewed")
    parser.add_argument("--workers", type=int, default=4, help="Concurrent field-window reads (1–4), no full-scene downloads")
    parser.add_argument("--cache", type=Path, default=root / "reports/b_satellite/.cache", help="Small derived per-scene receipts for interrupted-run resume")
    parser.add_argument("--labels", type=Path, default=root / "data/processed/core/labels.csv")
    parser.add_argument("--smoke-report", type=Path, default=root / "reports/b_satellite/run_report.json")
    parser.add_argument("--dry-run", action="store_true", help="Validate A's complete label list and emit a batch plan without reading imagery")
    parser.add_argument("--limit", type=int, help="Explicitly process only the first N A label keys; report scope remains explicit")
    parser.add_argument("--offline", action="store_true", help="Resume only from recorded scene inventory and verified derived receipts; missing scenes remain explicit blockers")
    parser.add_argument("--reuse-inventory", action="store_true", help="Resume missing remote reads from the recorded, geometry/window-validated real STAC search")
    args = parser.parse_args(argv)
    if args.max_window_pixels <= 0 or args.max_window_pixels > 2_000_000:
        parser.error("max-window-pixels must be in [1, 2000000] to guard storage/memory")
    if not 1 <= args.workers <= 4:
        parser.error("workers must be in [1,4]")
    if args.limit is not None and args.limit <= 0:
        parser.error("limit must be positive")
    if args.command == "batch":
        from .batch import run_batch
        return run_batch(args)
    return run(args)
