# Data directory

## USDA NASS corn benchmarks

`raw/usda_nass/crop_production_2025_summary.pdf` is the official USDA National Agricultural Statistics Service (NASS) *Crop Production 2025 Summary*, released January 12, 2026. The report contains state and national planted/harvested area, yield, and production tables.

`processed/usda_nass/corn_state_benchmarks_2025.csv` is a compact, machine-readable extract for the United States and California. It is for unit checks, aggregate sanity checks, and the California example in the project brief. It is **not** a field-level training set and must not be used as if it supplied field labels.

### Units and interpretation

- Area columns are thousand acres.
- Grain yield is bushels per acre; grain production is thousand bushels.
- Silage yield is tons per acre; silage production is thousand tons.
- `corn_planted_all_purpose` includes corn planted for all uses. Grain and silage harvested acres are reported separately; do not assume they must sum exactly to planted acres.
- USDA NASS estimates are annual aggregate reference values. They are not near-real-time supply measurements.

### Provenance

- Official NASS report: <https://release.nass.usda.gov/reports/cropan26.pdf>
- California state overview: <https://www.nass.usda.gov/Quick_Stats/Ag_Overview/stateOverview.php?state=California&year=2025>
- Data are attributed to USDA NASS. Consult the linked source for publication notes, revisions, definitions, and reuse terms.

All values in the CSV are from the same January 2026 NASS summary report and preserve its published rounding.
