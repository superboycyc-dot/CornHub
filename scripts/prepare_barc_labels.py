"""Export only labeled BARC field-years as a tidy, geometry-free label table."""

from __future__ import annotations

import csv
import sqlite3
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "04_Evaluation" / "BARC_Corn.2021-2023.gpkg"
LAYER = "barc_silage_grain_corn20212023"
DESTINATION = ROOT / "data" / "processed" / "barc_field_year_labels.csv"
LABEL_COLUMNS = {2021: "Corn_2021", 2022: "Corn_2022", 2023: "Corn_2023"}
OUTPUT_COLUMNS = ("field_id", "year", "harvest_type", "acres")


def main() -> None:
    if not SOURCE.exists():
        raise FileNotFoundError(SOURCE)

    rows: list[dict[str, str]] = []
    connection = sqlite3.connect(f"file:{SOURCE}?mode=ro", uri=True)
    try:
        table_exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (LAYER,)
        ).fetchone()
        if table_exists is None:
            raise ValueError(f"GeoPackage layer {LAYER!r} was not found.")

        for year, label_column in LABEL_COLUMNS.items():
            query = (
                f'SELECT "OBJECTID", "ACRES", "{label_column}" '
                f'FROM "{LAYER}" '
                f'WHERE "{label_column}" IN (?, ?) '
                f'ORDER BY "OBJECTID"'
            )
            for field_id, acres, harvest_type in connection.execute(
                query, ("Grain", "Silage")
            ):
                rows.append(
                    {
                        "field_id": str(field_id),
                        "year": str(year),
                        "harvest_type": harvest_type,
                        "acres": f"{acres:.6f}",
                    }
                )
    finally:
        connection.close()

    if not rows:
        raise ValueError("No Grain/Silage field-year labels found in the source layer.")

    rows.sort(key=lambda row: (int(row["year"]), int(row["field_id"])))
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    with DESTINATION.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    by_year_class = Counter((row["year"], row["harvest_type"]) for row in rows)
    unique_fields = len({row["field_id"] for row in rows})
    print(
        f"Wrote {len(rows)} labeled field-years from {unique_fields} fields to "
        f"{DESTINATION.relative_to(ROOT)}"
    )
    for year in LABEL_COLUMNS:
        print(
            f"{year}: Grain={by_year_class[(str(year), 'Grain')]}, "
            f"Silage={by_year_class[(str(year), 'Silage')]}"
        )


if __name__ == "__main__":
    main()
