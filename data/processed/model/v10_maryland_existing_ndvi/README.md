# V10 Maryland 2021–2025 — existing NDVI only

V10 is the user-confirmed alias for frozen V9 + US-only confidence calibration. No new imagery downloads or feature extraction. Includes only Maryland field-years with available cached NDVI at the input snapshot; not statewide coverage.

predictions.csv combines five annual CSVs. Join fields.geojson by field_id. confidence_score is experimental estimated correctness (0–100); raw_self_confidence is uncalibrated class probability ×100. Calibration uses Maryland farm-group development validation, not independent external validation. training_overlap flags training field-years. These are inference outputs, not an accuracy benchmark. conditional_prediction means annual maize eligibility is unknown; prediction is conditional on maize. Missing context features remain missing under the frozen model.
