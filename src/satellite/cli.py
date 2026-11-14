import argparse
from pathlib import Path

from .pipeline import run


def main(argv=None):
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description="CornHub B: contract-validated real Sentinel-2 smoke pipeline")
    parser.add_argument("command", choices=["preflight", "smoke"])
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
    args = parser.parse_args(argv)
    if args.max_window_pixels <= 0 or args.max_window_pixels > 2_000_000:
        parser.error("max-window-pixels must be in [1, 2000000] to guard storage/memory")
    return run(args)
