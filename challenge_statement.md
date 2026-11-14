# UC Davis Hackathon Challenge: Silage or Grain?

## Detecting Corn Harvest Type with Open Geospatial Data

### The Question

Can we determine from the sky whether a corn field was harvested for **silage**
or **grain**?

Build a data-driven method that distinguishes silage corn fields from grain
corn fields using **only publicly available geospatial data**. Your method may
use satellite imagery, weather or climate data, public agricultural datasets,
or other open geospatial sources.

There is no single public dataset that directly labels every field as silage or
grain. The goal is therefore to develop and validate a defensible inference
from observable signals.

## Why This Is Challenging

Silage and grain corn can follow different harvest schedules and leave
potentially different post-harvest surfaces:

- **Silage corn** is often cut in late summer while plants are still green.
- **Grain corn** often remains in the field longer, commonly into October or
  November, to dry down before harvest.
- Grain harvest may leave more standing or surface residue, while silage
  harvest can leave a more open post-harvest field.

These patterns can be subtle and vary with location, planting date, hybrid,
irrigation, weather, management, and imagery availability. A difference seen
in one field or year is not automatically evidence of harvest type.

This is complex and ongoing field of study. Your efforts during this short challenge period will help identify approaches that extend prior work.

## Your Task

Create a reproducible workflow that estimates whether corn fields are
silage-like or grain-like. Your submission should:

1. State a clear hypothesis about the signals that distinguish harvest type.
2. Use only public data sources and document how each source was obtained.
3. Build features or a model from geospatial evidence.
4. Validate the approach against the provided evaluation data.
5. Report where the method works, where it fails, and how uncertain it is.

Teams are welcome to choose their own tools, sensors, catalogs, and modeling
strategies. The starter materials are examples, not a required technology
stack.

## Possible Evidence

Potential approaches include, but are not limited to:

- **Seasonal vegetation trajectories:** an earlier or steeper decline in NDVI,
  EVI, red-edge, or related indices may indicate earlier harvest.
- **Harvest-date detection:** estimate a field's change point or sustained
  post-peak decline, then test whether timing separates the two labels.
- **Post-harvest residue:** use optical or radar signals to investigate
  differences in remaining crop residue or bare soil.
- **Optical imagery:** Landsat, Sentinel-2, and harmonized products offer
  repeat observations of surface reflectance.
- **Radar imagery:** Sentinel-1 can complement optical data in cloudy periods
  and may capture structural changes around harvest.
- **Weather context:** precipitation, temperature, growing-degree days, or
  frost may help explain timing differences and reduce false inferences.
- **Public agricultural context:** USDA Cropland Data Layer and NASS Quick
  Stats can support crop masks and aggregate interpretation, but do not provide
  field-level harvest-use labels.

## Data Rules

- Use **publicly available** data only.
- Understand the source meaning, spatial and temporal resolution, processing level,
  coverage, and known limitations before relying on a piece of data.
- Record source URLs, acquisition dates, query parameters, preprocessing, and
  derived features so another team can reproduce the analysis.
- Do not treat a proxy feature as a label. For example, an early NDVI decline
  is a hypothesis about harvest timing, not proof of silage harvest.

## Evaluation

The `04_Evaluation` folder contains BARC field polygons with reference Grain
and Silage labels for 2021-2023. Use the evaluation data only for labeled
field-year records; blank labels are not negative examples.

At a minimum, report:

- A confusion matrix
- Precision and recall for both Grain and Silage
- The number of evaluated fields by year and class
- Your validation split design
- Important sources of error, uncertainty, and geographic or temporal limits

Avoid a purely random field split when nearby fields may share management or
imagery conditions. Prefer holding out a year, a spatially separated group of
fields, or both when sample size allows.

## What a Strong Submission Looks Like

A strong submission is not necessarily the most complex model. It makes a
clear claim, tests it honestly, explains the data and assumptions, and shows
whether the result transfers beyond the fields used to develop it. Transparent
baselines, thoughtful validation, and careful uncertainty reporting matter as
much as predictive accuracy.

## Starter Materials

- `02_QuickStats`: reproducible corn planted and harvested acreage downloads
- `03_Geospatial_References`: open-data references and a Sentinel-2 starter
  notebook
- `04_Evaluation`: BARC labeled field data for the state of Maryland and an exploration notebook
- **Prior_Work**: annotated readings on harvest timing, phenology, radar, and
  residue methods
