# B satellite execution report

Status: `blocked`

Valid observation days: None

- `a_fields_missing`: A must provide data/processed/core/fields.geojson from the official BARC data.
- `a_smoke_sample_missing`: A must provide data/processed/core/smoke_sample.json selected by the contract; B does not invent field_id, year or labels.

Official notebook is now available in the repository as `03_Geospatial_References/sentinel-2_starter_notebook.ipynb`; see `notebook_review.md`. No manual download is currently required.

If unavailable in another checkout, download `03_Geospatial_References/starter_notebook.ipynb` from the team JupyterLab to `notebooks/b_satellite/starter_notebook.ipynb`.

A owns the official BARC boundary/label extraction and must deliver `data/processed/core/fields.geojson` and `smoke_sample.json`.

Missing inputs are not evidence of zero cloud-free observations. Header-only handoff tables contain no invented fields, labels or observations.
