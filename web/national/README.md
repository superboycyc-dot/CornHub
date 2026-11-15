# US candidate field display and prediction interface

All 6,112,209 CSB objects and 15,939 CropSight objects from A commit 83fc31f4a6f1fcd3555935c9fb4b286665b8b9ee are registered, with the original candidate_id and source_dataset_id. Sources can overlap; 6,128,148 is an object count, not unique surveyed farms. CSB covers the contiguous US, not Alaska/Hawaii. Crop classes do not provide silage/grain ground truth.

At close zoom (Leaflet zoom 12+), white fills and outlines are limited to Maryland and California and come from the actual source polygons, with topology-preserving display simplification (0.0001 degrees, roughly 11 m in latitude). Other states show individual white display points at close zoom. No rectangles are invented. At smaller scales, including a ruler around 50 km, the layer remains visible as white points/count clusters. Display points use quantized bounding-box centers; they do not replace source polygons. Invalid source geometry flags are retained. Year flags come from cdlYYYY=1 for CSB or the original observation year for CropSight. 2024/2025 are unavailable. No original ID is renamed into field_id or joined to BARC.

## Prediction slot available for every object

Edit the source prediction-config.json to set a HTTPS or same-origin endpoint and exact model_version, then rebuild and publish. No API secrets belong in this public file. Null configuration means Not computed; it does not generate probabilities. BARC retains its independent official predictions.csv interface for all 83 reference boundaries.

POST JSON request:

```json
{"source_revision":"83fc31f4a6f1fcd3555935c9fb4b286665b8b9ee","source_dataset_id":"csb_corn_2021_2023","candidate_id":"csb_351623000000046","candidate_ids":["csb_351623000000046"],"year":2022,"prediction_role":"inference","model_version":"YOUR_VERSION"}
```

Response: {"predictions":[]} when no computed result exists. Otherwise return one row containing the same source_dataset_id, candidate_id, integer year, prediction_role, model_version, plus p_silage (null or finite 0–1) and predicted_label (grain/silage consistent with the 0.5 threshold). Missing remains null. Different IDs/years/roles/versions, duplicate rows or invalid probabilities are rejected. The endpoint retrieves separately computed outputs; this page does not train a national model. Any future prediction source must establish eligibility, features and model applicability, not reuse BARC probabilities.

## Rebuild

Install scripts/requirements-national.txt in an isolated Python environment, fetch work/a-external-corn, then run scripts/build-national-index.py with a clean scratch directory. It reads source blobs through Git, verifies each upstream Parquet hash and row count, and writes 170 compressed spatial tiles. Source provenance and the complete-object validation are in index.json and reports/e_web/national-index-validation.json. Tiles load only for the visible region; no samples replace the complete inventory.

Attribution: USDA NASS Crop Sequence Boundaries 2016–2023 rev23 (U.S. Public Domain); Zhou, Liu & Diao, CropSight-US v1.0.1 (CC-BY-4.0), https://doi.org/10.5194/essd-18-3069-2026 . Original geometry, area and author confidence fields remain in A's GeoParquet; author crop confidence is not a silage probability.

Polygon rebuild: run scripts/build-national-polygons.py in the same Python environment. polygons-index.json contains actual per-tile source extents (including edge-crossing shapes); only intersecting files are fetched. The prediction keys and universal per-object API slots are unchanged.

Transport packaging: after polygon generation, run scripts/compress-national-polygons.py. Final NPG2 preserves all object IDs, rings and vertices on a 1e-6 degree display grid (max coordinate rounding about 6 cm). Brotli is lossless relative to this defined display representation. Browser decoding uses a dynamically loaded decoder and is independently checked against the native Brotli decoder. No fields or vertices are removed by this transport step.

NPG2 display coordinates retain every vertex and use a 1e-6 degree grid (maximum rounding shift about 6 cm in latitude), well below the display simplification and source raster resolution. IDs, flags, rings and vertex counts are unchanged. pack-national-geometry.py and compact-display-grid.py produce this compact representation.

Final serving: finalize-national-transport.py generates fine regional overview counts from all points and recompresses polygon bytes at quality 8. Overview markers represent regions, not individual invented field positions. Individual-point transport files are build inputs only and are excluded from the website. Full per-object IDs and vertices remain in polygon tiles. County JSON is gzip transported without any data change.

## Regional publication scope (2026-11-15)

The national layer is on by default and can be hidden. Maryland has 49,902 and California 18,434 candidate objects with outlines (source objects can overlap). Original 83 BARC reference boundaries remain independent. Below zoom 12, all regions use counted white points/clusters, including at the 50 km ruler. Every candidate retains its prediction slot.

After generating complete polygon assets, run `node scripts/scope-national-polygons.mjs`, then `node scripts/check-national-scope.mjs` and `npm run build`. The scope command is repeatable; expanding to another state requires rebuilding complete source geometry first. CSB is assigned using its original state FIPS ID prefix; CropSight is assigned by geometry bounding-box center within Census county geometry. These are display scope rules, not clipped cadastral boundaries. Point flag 32 indicates a published outline; all original bits and IDs remain unchanged.
