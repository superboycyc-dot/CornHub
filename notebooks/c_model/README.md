# C model entry point

Run from repository root. No shared notebook is modified; implementation is in `src/model/pipeline.py`.

```sh
python3 -m src.model.pipeline
python3 -m venv /tmp/cornhub-c-model-venv
/tmp/cornhub-c-model-venv/bin/python -m pip install -r src/model/requirements.txt
/tmp/cornhub-c-model-venv/bin/python -m unittest src.model.test_pipeline
# Only after A confirms permitted label use / official split and real A/B inputs arrive:
/tmp/cornhub-c-model-venv/bin/python -m src.model.pipeline --train
# Optional full-data predictions, explicitly distinct from OOF:
/tmp/cornhub-c-model-venv/bin/python -m src.model.pipeline --train --inference
```

Default interface-only mode requires standard-library Python. It validates and reports actual available inputs, writes header-only predictions and pending metrics. Invalid schema exits 2; missing inputs exit 0 with explicit pending reasons. Training requires the local dependency file. `--data-root`, `--output`, `--report` permit isolated runs; synthetic fixtures must use temporary directories, never team output paths. Tests create and delete their data/results in `TemporaryDirectory`; only test code is committed.

Inputs: `data/processed/core/labels.csv`, `core/validation_folds.csv`, `satellite/features.csv`. Do not substitute the legacy `barc_field_year_labels.csv` or recreate A's IDs/folds. Contract scope is BARC 2021–2023; root README's California scope is a separate later objective.

Model whitelist: ndvi_peak, peak_doy, max_drop_per_day, drop_doy, ndvi_late_mean, valid_obs_count, max_gap_days. All additional input columns ignored; IDs, year, fold_id, labels, quality text and provenance never enter X. No data with quality no_data/insufficient is trained or inferred; limited quality retained and visible upstream. No quality score is a probability reliability score.

RF: 100 trees, depth 4, leaf minimum 2, balanced class weighting, seed 42, one CPU; no tuning. Each outer fold fits its own median imputer (all-missing training columns use zero via keep_empty_features) and forest. Global field-to-fold consistency is validated across all supplied years. A fold lacking either training class abstains and reports excluded rows. Fold IDs are opaque; A must provide only permitted validation folds, preserving official tests separately. We do not assign or reinterpret official test folds.

Outputs: predictions.csv has unique field_id+year+prediction_role, threshold 0.5; OOF uses only other fields for training. Inference is optional, fits eligible labeled rows and predicts usable/limited feature rows, including unlabeled records; its fold_id is blank. metrics.json evaluates OOF exclusively. Inspect merge_report.json for input counts, duplicate keys, schema errors, unmatched keys, quality exclusions, skipped folds and coverage. Undefined macro F1 (truth missing a class), silage precision (no predicted silage), and recall (no true silage) are null with notes; Brier and confusion counts are still defined on available OOF rows.

Rule comparator: fixed calendar day 258 (approximately mid-September) maximum NDVI drop or earlier predicts silage, otherwise grain; missing drop_doy abstains. This is an unvalidated heuristic, not an agronomic cutoff claim. It uses the successful RF OOF cohort with observed drop day, reports its own counts in reports/c_model/harvest_rule_metrics.json; Brier is null because hard labels are not model probabilities. Different comparator coverage must be checked before comparing scores.

Calibration is deliberately disabled in v1: small expected sample, no nested calibration implementation and no reliability claim. All probabilities remain uncalibrated even if more data arrive. Future calibration must use field-grouped splits entirely inside outer training folds. Results are exploratory BARC validation, not California transfer evidence.

## Consume delivered A/B branches before integration

A has delivered canonical inputs in PR #6; latest inspected B feature table in PR #5 is header-only. To consume these without changing A/B directories, fetch the branches and run:

```sh
python3 -m src.model.from_refs --core-ref origin/work/a-data --satellite-ref origin/work/b-satellite --train
```

This resolves each ref once to a commit, extracts only contract inputs into a temporary directory, and runs the same pipeline. Published merge_report.json records both commits and file SHA-256, with logical paths and no temporary machine paths. For exact reproduction use the recorded full SHAs instead of branch names. `--output` / `--report` can redirect a review run; synthetic data must always stay in private temporary output paths. After integration, the normal filesystem command works unchanged.

A now provides one fixed leave-one-farm-out 5-fold assignment as a documented lead-approved exception to the earlier three-field-fold contract; C consumes fold_id 0–4 unchanged. fields.geojson farm_group metadata is checked for cross-fold farm leakage and unknown field IDs across labels/folds/features. No geometry or area calculation is performed by C. If farm_group metadata is not supplied, the audit explicitly reports that farm-level checking was unavailable; field-level checking remains mandatory. Farm IDs never enter model features.

Label counts and full planned fold structure are reported before filtering satellite coverage, separately from actual trained folds and evaluated class counts. Header-only features are a present file with zero input rows, not a missing file; every label row missing features is listed in reports/c_model/exclusions.csv. Current real-data attempt produces pending even with --train because zero eligible rows exist. No placeholder probabilities are written.
