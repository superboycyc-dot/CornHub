"""Select the annual NASS Quick Stats corn acreage series used by CornHub."""

from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "01_QuickStats" / "corn_grain_silage_acres_2012_2025_raw.csv"
DESTINATION = (
    ROOT
    / "data"
    / "processed"
    / "usda_nass"
    / "california_corn_acreage_annual_reference_2012_2025.csv"
)
CENSUS_YEARS = {2012, 2017, 2022}
TARGET_STATE = "CALIFORNIA"
TARGET_DESCRIPTIONS = {
    "CORN - ACRES PLANTED",
    "CORN, GRAIN - ACRES HARVESTED",
    "CORN, SILAGE - ACRES HARVESTED",
}


def is_reference_record(row: dict[str, str]) -> bool:
    try:
        year = int(row["year"])
    except (KeyError, ValueError):
        return False

    expected_level = "COUNTY" if year in CENSUS_YEARS else "STATE"
    expected_source = "CENSUS" if year in CENSUS_YEARS else "SURVEY"
    return (
        row.get("short_description") in TARGET_DESCRIPTIONS
        and row.get("state_name", "").strip().upper() == TARGET_STATE
        and row.get("reference_period") == "YEAR"
        and row.get("frequency") == "ANNUAL"
        and row.get("domain") == "TOTAL"
        and row.get("domain_category") == "NOT SPECIFIED"
        and row.get("aggregation_level") == expected_level
        and row.get("source") == expected_source
    )


def main() -> None:
    with SOURCE.open(newline="", encoding="utf-8-sig") as source_file:
        reader = csv.DictReader(source_file)
        if not reader.fieldnames:
            raise ValueError(f"No CSV header found in {SOURCE}")
        rows = [row for row in reader if is_reference_record(row)]

    rows.sort(
        key=lambda row: (
            int(row["year"]),
            row["aggregation_level"],
            row["state_ansi"],
            row["county_ansi"],
            row["crop_use"],
            row["measurement"],
        )
    )

    seen: set[tuple[str, ...]] = set()
    for row in rows:
        key = (
            row["year"],
            row["aggregation_level"],
            row["state_ansi"],
            row["county_ansi"],
            row["short_description"],
        )
        if key in seen:
            raise ValueError(f"Duplicate selected NASS series: {key}")
        seen.add(key)

    if not rows:
        raise ValueError("No matching annual NASS reference records found.")

    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    with DESTINATION.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=reader.fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(
        f"Wrote {len(rows):,} {TARGET_STATE.title()} records to "
        f"{DESTINATION.relative_to(ROOT)}"
    )


if __name__ == "__main__":
    main()
