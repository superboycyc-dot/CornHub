"""Download NASS Quick Stats corn grain and silage acreage records."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from datetime import date
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen


API_URL = "https://quickstats.nass.usda.gov/api/api_GET/"
SERIES = (
    ("harvested", "AREA HARVESTED"),
    ("planted", "AREA PLANTED"),
)
COUNTY_CENSUS_YEARS = {2012, 2017, 2022}
OUTPUT_COLUMNS = (
    "year",
    "aggregation_level",
    "state_name",
    "state_ansi",
    "county_name",
    "county_ansi",
    "commodity",
    "crop_use",
    "measurement",
    "statistic",
    "unit",
    "value",
    "cv_percent",
    "source",
    "domain",
    "domain_category",
    "reference_period",
    "frequency",
    "short_description",
)


def parse_arguments() -> argparse.Namespace:
    completed_year = date.today().year - 1
    parser = argparse.ArgumentParser(
        description=(
            "Download NASS Quick Stats corn grain and silage planted and harvested "
            "acres: county-level in Census years and state-level otherwise."
        )
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("NASS_API_KEY"),
        help="NASS Quick Stats API key. Defaults to the NASS_API_KEY environment variable.",
    )
    parser.add_argument(
        "--start-year",
        type=int,
        default=2012,
        help="First year to retrieve. Default: 2012.",
    )
    parser.add_argument(
        "--end-year",
        type=int,
        default=completed_year,
        help=f"Last year to retrieve. Default: {completed_year}.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).with_name(
            f"corn_grain_silage_acres_2012_{completed_year}.csv"
        ),
        help="Destination CSV path.",
    )
    return parser.parse_args()


def fetch_records(
    api_key: str,
    year: int,
    aggregation_level: str,
    statistic: str,
) -> list[dict[str, Any]]:
    parameters = {
        "key": api_key,
        "format": "JSON",
        "sector_desc": "CROPS",
        "group_desc": "FIELD CROPS",
        "commodity_desc": "CORN",
        "statisticcat_desc": statistic,
        "unit_desc": "ACRES",
        "agg_level_desc": aggregation_level,
        "year": str(year),
    }
    request_url = f"{API_URL}?{urlencode(parameters)}"

    for attempt in range(3):
        try:
            with urlopen(request_url, timeout=60) as response:
                payload = json.load(response)
            return payload.get("data", [])
        except HTTPError as error:
            error_body = error.read().decode("utf-8", errors="replace")
            if error.code in {429, 500, 502, 503, 504} and attempt < 2:
                time.sleep(2**attempt)
                continue
            raise RuntimeError(
                f"Quick Stats request failed for {year} {aggregation_level} {statistic}: "
                f"HTTP {error.code}: {error_body}"
            ) from error
        except URLError as error:
            if attempt < 2:
                time.sleep(2**attempt)
                continue
            raise RuntimeError(
                f"Could not reach Quick Stats for {year} {aggregation_level}: {error.reason}"
            ) from error

    raise AssertionError("Unreachable retry state")


def normalize_record(record: dict[str, Any]) -> dict[str, str]:
    return {
        "year": record.get("year", ""),
        "aggregation_level": record.get("agg_level_desc", ""),
        "state_name": record.get("state_name", ""),
        "state_ansi": record.get("state_ansi", ""),
        "county_name": record.get("county_name", ""),
        "county_ansi": record.get("county_ansi", ""),
        "commodity": record.get("commodity_desc", ""),
        "crop_use": crop_use(record),
        "measurement": (
            "harvested" if "HARVESTED" in record.get("short_desc", "") else "planted"
        ),
        "statistic": record.get("statisticcat_desc", ""),
        "unit": record.get("unit_desc", ""),
        "value": record.get("Value", ""),
        "cv_percent": record.get("CV (%)", ""),
        "source": record.get("source_desc", ""),
        "domain": record.get("domain_desc", ""),
        "domain_category": record.get("domaincat_desc", ""),
        "reference_period": record.get("reference_period_desc", ""),
        "frequency": record.get("freq_desc", ""),
        "short_description": record.get("short_desc", ""),
    }


def crop_use(record: dict[str, Any]) -> str:
    short_description = record.get("short_desc", "")
    if "GRAIN" in short_description:
        return "grain"
    if "SILAGE" in short_description:
        return "silage"
    return "all_corn"


def is_requested_series(record: dict[str, Any]) -> bool:
    short_description = record.get("short_desc", "")
    if record.get("statisticcat_desc") == "AREA PLANTED":
        return short_description == "CORN - ACRES PLANTED"
    return "CORN, GRAIN" in short_description or "CORN, SILAGE" in short_description


def main() -> int:
    arguments = parse_arguments()
    if not arguments.api_key:
        print(
            "Missing API key. Set NASS_API_KEY or pass --api-key. "
            "See methodology_and_caveats.md for setup instructions.",
            file=sys.stderr,
        )
        return 2
    if arguments.start_year > arguments.end_year:
        print("--start-year must be less than or equal to --end-year.", file=sys.stderr)
        return 2

    records: list[dict[str, str]] = []
    for year in range(arguments.start_year, arguments.end_year + 1):
        aggregation_level = "COUNTY" if year in COUNTY_CENSUS_YEARS else "STATE"
        for measurement, statistic in SERIES:
            print(f"Requesting {year} {aggregation_level.lower()} {measurement} data...")
            response_records = fetch_records(
                arguments.api_key, year, aggregation_level, statistic
            )
            records.extend(
                normalize_record(record)
                for record in response_records
                if is_requested_series(record)
            )

    records.sort(
        key=lambda record: (
            int(record["year"]),
            record["aggregation_level"],
            record["state_name"],
            record["county_name"],
            record["crop_use"],
            record["measurement"],
        )
    )
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    with arguments.output.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(records)

    print(f"Wrote {len(records):,} records to {arguments.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())