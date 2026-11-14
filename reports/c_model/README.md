# C first-round delivery

Branch: work/c-model. Only C-owned paths edited; existing 05_Model notebook and legacy data preserved. Read README, collaboration/submission rules and docs/team-contract.md; no AGENTS.md found in repository. Use contract BARC scope as explicitly requested, despite older root README California scope.

Actual production run: `python3 -m src.model.pipeline`.
Current inputs missing: core/labels.csv, core/validation_folds.csv, satellite/features.csv (under data/processed). No actual joins or real training possible. Header-only predictions.csv and pending metrics.json contain no synthetic predictions or evaluation scores. Detailed machine-readable missing-file report: merge_report.json. Existing legacy labels are not silently substituted for A's canonical contract files.

Need A: canonical labels, field-fixed folds and confirmation of official label-use/test restrictions. Need B: real features with quality flags/missing reasons. Once ready, run documented --train command; add --inference only when full-data predictions are needed. No real validation result is claimed in this round.

Implementation and commands, feature whitelist, exclusions, fold behavior, heuristic rule, calibration limits and role separation are documented in notebooks/c_model/README.md. Internal checks exercise implementation with temporary synthetic inputs; their predictions and metrics are never copied to published outputs and are not scientific validation.

Actual checks completed: `/tmp/cornhub-c-model-venv/bin/python -m unittest src.model.test_pipeline` — 6 tests passed (pending/header-only outputs; duplicate and cross-year field-fold rejection; unmatched and quality exclusions; undefined metrics; per-fold imputer fit sizes and role uniqueness; missing training class abstention). Training fixture used 16 rows per outer training fold versus 24 for optional final inference fit. This checks isolation, not real-world performance. Environment: Python 3.13, numpy 2.5.4, scikit-learn 1.9.1. `git diff --check` passed. Re-ran production interface after tests; status remains pending with three missing files. Dependency installation used a temporary environment; no environment directory is included.
