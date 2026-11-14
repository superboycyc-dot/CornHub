# D analysis entry point

Run from the repository root:

```sh
python3 src/analysis/analysis.py --year 2022 --prediction-role oof --review-budget 3
```

The tested functions live in src/analysis/analysis.py; no notebook kernel or
third-party dependency is required. See reports/d_analysis/README.md for the
input/output contract, parameter template, sources and blockers. Select each
year/role explicitly; keep separate output directories for multiple runs.
