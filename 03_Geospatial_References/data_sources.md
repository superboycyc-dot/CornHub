# Open Geospatial Data Reference

This guide is for the UC Davis Hackathon challenge: infer whether a corn field
was harvested for silage or grain using only public data. It is a menu of
starting points, not a required technology stack. Teams may use any public
geospatial source, catalog, sensor, processing method, or feature set that
supports a defensible approach. No source below is a field-level silage/grain
label. Validate each source's meaning, coverage, timing, resolution, and
processing history, then document every assumption.

## Possible Data Pathways

| Need | Open source | How to use it |
| --- | --- | --- |
| Corn-field candidate mask | [USDA Cropland Data Layer (CDL)](https://www.nass.usda.gov/Research_and_Science/Cropland/SARS1a.php) | Restrict analysis to pixels mapped as corn in the target year. CDL is a crop-type map, not a harvest-type label. |
| Seasonal crop signal | [Sentinel-2 L2A](https://dataspace.copernicus.eu/explore-data/data-collections/sentinel-data/sentinel-2) | Ten-meter red, near-infrared, and scene-classification bands support NDVI trajectories and cloud masking. |
| Longer historical coverage | [Landsat Collection 2 Level-2](https://www.usgs.gov/landsat-missions/landsat-collection-2-level-2-science-products) | Thirty-meter imagery extends the time series before Sentinel-2. |
| Public catalog access | [Microsoft Planetary Computer](https://planetarycomputer.microsoft.com/catalog) or [Earth Search](https://www.element84.com/earth-search/) | Query STAC catalogs rather than manually downloading scenes. The starter notebook uses Planetary Computer. |
| Weather context | [gridMET](https://www.climatologylab.org/gridmet.html) or [Daymet](https://daymet.ornl.gov/) | Add precipitation, temperature, growing-degree days, and frost context around expected harvest dates. |
| Aggregate context | [USDA NASS Quick Stats](https://quickstats.nass.usda.gov/) | Compare regional planted and harvested acreage; it is not a field label. |
| Boundaries and basemaps | [US Census TIGER/Line](https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html), [USGS National Map](https://www.usgs.gov/the-national-map-data-delivery) | Use for counties, roads, and reference geography. |

## What Students Should Look For

Silage and grain are hypotheses about a field's seasonal behavior, not a
single-pixel signature.

- **Earlier loss of greenness:** silage is often cut in late summer while the
  plant is still green, potentially producing an earlier and sharper NDVI drop.
- **Late-season persistence:** grain often remains through later dry-down,
  shifting the timing of sustained greenness loss later in the fall.
- **Post-harvest surface:** grain can retain more residue than silage. Test
  this with reflectance, red-edge/SWIR features when available, and image
  interpretation; do not treat it as a definitive rule.
- **Weather and location:** heat, rainfall, irrigation, variety, planting date,
  elevation, and management can shift the signal. A timing rule that works in
  one county may fail elsewhere.

## Suggested Student Workflow

1. Select a bounded study area and a target year. Choose data sources that are
   appropriate for the hypothesis; the table above and the starter notebook
   are examples, not constraints.
2. Use CDL to identify likely corn fields, then choose a small set of field
   polygons for rapid iteration.
3. Query Sentinel-2 scenes from July through November. Mask cloud, cloud
   shadow, and snow before computing field summaries.
4. Build a per-field time series: median NDVI, date of peak NDVI, first
   sustained decline, decline magnitude, and late-season NDVI.
5. Compare time series visually before fitting a classifier. Label only fields
   with defensible external evidence; otherwise call results `silage-like` and
   `grain-like` hypotheses rather than ground truth.
6. Validate across years and counties. Split validation geographically so
   neighboring fields cannot inflate performance.
7. Report uncertainty, missing observations, cloud cover, and cases where the
   method abstains. Include source URLs, acquisition dates, spatial and
   temporal resolution, processing level, known limitations, and why each
   source supports the claimed inference.

## Labeling and Evaluation

The central difficulty is limited public field-level labels. Reasonable
validation options include a small manually interpreted sample, collaborator-
provided labels that may be used only if challenge rules permit them, or
aggregated comparison to county totals. Do not present county-level Quick Stats
acreage as individual-field truth.

For a binary model, report precision, recall, F1, confusion matrix, and
calibration. Also report performance by year and region. A useful baseline is a
transparent rule based on the date of a sustained NDVI decline; a more advanced
model should beat that baseline on held-out geography.

## Data Access Notes

- Follow each provider's terms, attribution guidance, and service limits.
- Prefer analysis-ready Level-2 surface reflectance products.
- Keep raw downloads and derived outputs separate. Record catalog URL, query
  dates, collection names, band names, cloud threshold, CRS, and processing
  choices in your submission.
- Satellite observations can be absent during cloudy periods. Any interpolation or imputation methods must be clearly described. 

## Starter Notebook

[sentinel-2_starter_notebook.ipynb](sentinel-2_starter_notebook.ipynb) provides a small, field-first
Sentinel-2 workflow. Put a polygon or multipolygon GeoJSON named
`field_aoi.geojson` next to the notebook before running it. Start with one
field, inspect the returned scene count, then expand to multiple fields.
