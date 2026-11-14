# Quick Stats Corn Acreage

This folder contains a reproducible downloader for USDA National Agricultural
Statistics Service (NASS) Quick Stats acreage data. It produces one tidy CSV
with corn grain and corn silage harvested acres plus all-corn planted acres.

## Data Requested

The downloader requests these exact Quick Stats series:

- `CORN, GRAIN - ACRES HARVESTED`
- `CORN, SILAGE - ACRES HARVESTED`
- `CORN - ACRES PLANTED`

NASS publishes a single all-corn planted-acre series rather than separate
grain and silage planted-acre series. Accordingly, planted records use
`crop_use = all_corn`; harvested records use `grain` or `silage`.

It uses county aggregation for the 2012, 2017, and 2022 Census of Agriculture
years. It uses state aggregation in every other year. The default year range is
2012 through the last completed calendar year. Override it with `--start-year`
and `--end-year` when needed.

## Get an API Key

1. Open the [NASS Quick Stats API page](https://quickstats.nass.usda.gov/api).
2. Request a key using the form on that page.
3. Keep the key private. Do not commit it to Git or put it in this repository.

## Run the Download

Python 3.9 or later is sufficient; the script uses only the Python standard
library. In PowerShell, set the API key only for the current terminal session:

```powershell
$env:NASS_API_KEY = "your-key-here"
python .\download_corn_acres.py
```

The default output is `corn_grain_silage_acres_2012_2025.csv` when run during
2026. The ending year changes automatically as calendar years change. To make
the output and scope explicit:

```powershell
python .\download_corn_acres.py `
  --start-year 2012 `
  --end-year 2025 `
  --output .\corn_grain_silage_acres_2012_2025.csv
```

You may instead provide the key directly with `--api-key`, but the environment
variable is preferable because command history can retain command-line values.

## Output Schema

The CSV contains one row per Quick Stats record. `value` is retained as the
source text rather than coerced to a number, because NASS can publish values
such as `(D)` for withheld data. Key columns include:

- `year` and `aggregation_level`
- `state_name`, `state_ansi`, `county_name`, and `county_ansi`
- `crop_use` (`grain` or `silage`) and `measurement` (`planted` or `harvested`)
- `value` and `unit`
- provenance fields such as `source`, `domain`, `frequency`, and
  `short_description`

County fields are blank for state-level records. Preserve the ANSI fields with
leading zeroes when joining the output to geographic data.

## Caveats

- Availability, suppression, and revisions are controlled by NASS. A request
  can return no records for a particular year, geography, or series.
- Data should be omitted from analysis where it is blank or contains a supression disclosure code (e.g. (D),(S),(H), and others) related to privacy or quality.
- Later-year data can be revised after release. Re-run the download when
  preparing final analysis or submission outputs.
- The 2012, 2017, and 2022 county / other-years state rule is encoded
  deliberately. It does not prove that county data are unavailable in every
  other year; it implements the requested Census-year comparison pattern.
- The script retries temporary API and network errors, but it stops with the
  API response for authentication and invalid-query errors.

## Source

USDA NASS Quick Stats: <https://quickstats.nass.usda.gov/>.