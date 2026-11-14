# Model prototype

## BARC Sentinel-2 baseline

`barc_sentinel2_baseline.ipynb` is a methodology prototype using the Hack the Harvest BARC sample in Maryland. It retrieves public Sentinel-2 L2A scenes, masks to vegetation and bare-soil SCL classes, computes field-level NDVI curves and seasonal summaries, then evaluates a Random Forest with farm-grouped folds.

This sample is small and imbalanced (44 labeled field-years, 34 fields, 5 farms). Results are exploratory and do not estimate performance in California. The out-of-fold probabilities are not calibrated. The notebook records scene coverage and valid-pixel fractions so missing or cloudy observations remain visible.

Run it from the repository root in Jupyter. The first notebook cell installs the geospatial Python packages. Scene discovery and raster reads require network access to Microsoft Planetary Computer. Outputs are written under `data/processed/sentinel2/`; satellite imagery itself is not copied into the repository.

## Next model milestone

Before fitting a California model, obtain California field polygons and verified harvest-use labels with year, field identifier, acres, and a source citation. Split evaluation by farm or geographic block, and keep a final held-out group. Do not treat CDL corn pixels, BARC Maryland labels, NASS county statistics, or a predicted harvest date as California ground truth. Report per-class precision/recall/F1, confusion matrix, class counts, coverage, and uncertainty alongside any area estimate.
