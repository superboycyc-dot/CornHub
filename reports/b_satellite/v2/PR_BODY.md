## Global satellite v2: real 200-field-year pilot

Adds versioned B-only code and artifacts for a seeded, area-stratified European
2023 pilot. Each of be2/be3/bg/si contributes 25 grain and 25 silage records.
Inputs are pinned to `a8ccadff2fa3a2e53c1469e2c243d7dab98d7466`;
`data/global_maize/` remains identical on the newly advanced input branch.
No v1, A-label, C-model or D/E result is changed.

Real PC L2A acquisition produced **4,586 scene rows, 177/200 field-years with
valid NDVI and NDMI, 73 usable, 104 limited, 23 unobservable**. A bounded,
label-independent 202-window long-gap pass improved usable count from 60 to 73.
Product XML supplies offsets/quantification/nodata; responses are verified on
native B04 grids, with explicit B11/SCL nearest resampling and independent
index supports. No synthetic observations, interpolation or accuracy claims.

C reads `data/processed/v2/satellite/features.csv` and `timeseries.csv`, keyed
by entity_id/year; labels stay in the acceptance report. The 134 Netherlands
fields and 1,072 legacy rows are reused separately, with 113 fields having
valid NDVI. Four cross-catalog checks agree to legacy rounding and are not
counted twice. Netherlands early-season/NDMI gaps remain explicit.

Validation: unique joins/physical products, dates/ranges/support counts, 857
product XML hash/calibration/baseline checks, 15,263 real pixel calculations,
four real-array count/median and boundary-overlay checks, independent daily
count/peak recomputation, and signed-URL scan passed. Commands and definitions
are in `reports/b_satellite/v2/README.md`; source/input/merge/coverage/resource
reports accompany the data.

Observed European crop payloads: 28.7 MB; local ignored checkpoints: 551 MB.
Elapsed wall time from first catalog checkpoint to gap-fill completion: 28.83
minutes, including warmup, debugging and idle time. Delivered artifacts are
about 9.2 MB. Expansion is held: only 73/200 are usable, and the current
per-field catalog cache must be deduplicated before 2,000–5,000. Shared
neighbor-window reads are a remaining optimization. Raw large images and
cache are excluded from Git. C should confirm the supplied global entity-ID
namespace before combining it with the separate BARC/CSB proposal.
