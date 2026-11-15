# B global satellite v2: retrospective pilot

Final pilot: **200 field-years processed, 177 with valid NDVI, 4,586 real scene
rows; 73 usable, 104 limited, 23 geometrically unobservable**. The initial pass
made 4,954 field-scene jobs; a single bounded gap-fill pass added 202 windows
and increased usable coverage from 60 to 73. No HTTP failures remained.

Status is in `run_report.json`, `gapfill_report.json` and `coverage_by_region_label.csv`. A feature row
with `no_data` is an explicit failed/unobservable record, not a successful field.
No classification model was trained. Declared grain/silage use is not proof of
the final actual harvest use.

## Inputs and interface

Frozen label branch: `data/global-maize-fields` at
`a8ccadff2fa3a2e53c1469e2c243d7dab98d7466`. Main contract inspected at
`a7d843f5047a8fb86510a6139c086a5ed01efb61`, then rechecked at latest main
`884f8ad91a5b0e469d38662dca2ad1868dcc8b93`; only historical-reference links
were added. No AGENTS.md found in either
checkout or applicable workspace ancestors. V1 B implementation inspected at
`05a81a7d1634c80d3c56b66cf9eb9acb9527fc9b`; v1 files/results are unchanged.
The input branch advanced to `49807d67f7e1fb54ad9c1879019e0f7c3a058933`
during execution, but a Git tree comparison confirms `data/global_maize/`
is unchanged. This run keeps the original input SHA and does not consume the
newly added `data/americas/` point samples.
C's `work/c-model-v2-plan` is a proposal for BARC/CSB, not an agreed global
contract. This PR uses the user's global contract. C must confirm the new
namespace before combining datasets; no C code/folds/model is changed.

`data/processed/v2/satellite/{selection,timeseries,features,coverage,feature_dictionary}.csv`
are the European 200-record interface. Labels and original IDs are separate in
`reports/b_satellite/v2/labels_for_acceptance.csv`. C can read with pandas and
join strictly on `entity_id,year`, `validate='one_to_one'`. Only the seven NDVI
statistics are feature candidates; IDs, year, quality, provenance and all label
columns are excluded from predictors. NDMI is delivered in the time series;
no unvalidated extra NDMI/harvest feature is invented.

The Netherlands 134-field legacy dataset is **separate** under
`data/processed/v2/satellite/netherlands_legacy/`. It reuses all 1,072 existing
real rows and preserves the narrower SCL4/5 policy. It is not counted as part of
the new European 200. Its NDMI is unknown, not zero. Twenty-one fields have no
usable legacy NDVI. April/May, long gaps and NDMI require further work; see the
explicit `netherlands_gapfill_queue.json`. No legacy curve is relabelled as a
new full-season v2 acquisition.

## Selection and pixels

The four dual-class European regions (be2, be3, bg, si) each contribute 25 grain
and 25 silage field-years. Within each region/class, sort by source area and
cropfield, split into five rank quintiles, sample five without replacement with
seed 20261114. Single-class regions and Quebec are excluded from this pilot.
Source geometry is EPSG:3035; always_xy reprojection to EPSG:4326 precedes STAC
search. Original off_id is retained separately; cropfield is the source key.

All labels share the fixed [Apr1,Dec1) window. The initial acquisition budget
selects one candidate per fixed ten-day bin, ranked by catalog cloud cover then
time/ID. This is a candidate prioritization policy, **not** local cloud QA or
complete archive extraction. Full per-field inventories are checkpointed, so
missing/poor bins can be revisited without a new query. No temporal interpolation.
One versioned pass subsequently targets accepted-NDVI gaps >30 days: one unread
physical product in the middle third of each gap, ranked by footprint coverage,
catalog cloud, midpoint distance and ID. The locked 202-job selection is in
`gapfill_selection.csv`; reruns reuse it rather than starting another pass.
The same date window and quality rules apply to both labels.

PC collection and assets are checked against current official STAC/OpenAPI.
Only native-grid field rectangles are requested from the provider's COG crop
endpoint, with raw `unscale=false` and verified transform, CRS, dimensions.
No full scene is downloaded. Product XML supplies quantification, explicit
band offsets and raw nodata. Float64 conversion precedes calibration. No
shooting-date or baseline-only offset guess. Product metadata is cached once
per scene, crop statistics once per scene+geometry+algorithm. PC container SAS
is reused in memory only. Concurrency starts at three and is capped at six after a stable warm-up, with bounded retries
and backoff. Same product is not acquired from a second catalog. Reprocessing
duplicates are reduced before candidate selection; same-day features choose
max NDVI valid fraction, then scene_id, exactly as v1.

Erode the true polygon inward by 10m; native B04 10m pixel centers define the
interior (`all_touched=False`). No alternative edge rule for small fields.
Fewer than three total centers means unobservable; fewer than three valid
centers gives null index. Denominator includes cloudy, nodata and uncovered
interior centers. SCL4/5/6/7 preserves bare soil; all other SCL classes are
excluded. B11 and SCL 20m are aligned by nearest neighbor to B04 native10m;
resampling provides no new 10m information. Separate finite band support,
positive denominator and [-1,1] ratio checks determine NDVI and NDMI counts.
The combined output alpha is ignored so each raw band is masked independently.

## Features and evidence

`feature_dictionary.csv` defines every formula, unit and minimum observation
requirement. `v2_features.py` snapshots the unchanged v1 seven-statistic
algorithm. Daily valid fraction threshold is 0.5. Late mean is [Sep1,Dec1).
Gaps include query boundaries; no-data gap is 244 days here. Quality flags are
data coverage heuristics, not model reliability. The largest observed NDVI
drop is not called an observed harvest date.

`scene_manifest.json` retains unsigned product references, asset grids and XML
calibration hashes/values. `pixel_calculation_evidence.json` traces real DN to
reflectance/indices. `alignment_evidence/` contains small real arrays and
boundary overlays, with independent median/count checks. Empty artifacts or
missing region plots indicate unfinished acquisition, never fabricated values.

## Reproduce

Use Python 3.11+ and `pip install -r src/satellite/requirements-v2.txt`.
Clone the input branch in a separate read-only checkout and check out the exact
SHA above. From the CornHub repository:

```sh
python src/satellite/global_v2.py prepare --input ../CornHub-v2
python src/satellite/v2_netherlands_reuse.py --input ../CornHub-v2
python src/satellite/v2_acquire.py --workers 6
python src/satellite/v2_export.py
python src/satellite/v2_gapfill.py
python src/satellite/v2_export.py
python src/satellite/v2_alignment.py
python src/satellite/v2_check_legacy.py --input ../CornHub-v2
python src/satellite/v2_document.py
python src/satellite/v2_validate.py
python src/satellite/v2_budget.py
```

Re-running acquisition resumes cached catalogs/XML/derived observations.
Keep `.cache/` locally; it is ignored by Git and contains no SAS tokens.
Raw large images are not committed. Expansion to 2,000–5,000 is held until
coverage, runtime, storage and unresolved gaps are reviewed. Budget numbers
must be based on actual run/storage reports, not an assumed success rate.
The four Netherlands cross-catalog checks differ by <0.000005, consistent with
legacy five-decimal rounding; counterpart products are not appended as
independent observations. Final European window payloads total about 28.7 MB,
with about 551 MB of local checkpoints. Most storage is repeated STAC JSON;
shared catalog deduplication and neighboring-window reuse need optimization
before expansion. The linear budget is a planning estimate, not a measured
expanded run. No 2,000–5,000-field acquisition has started.
