"""Run with Python + pyarrow: python extract.py /path/to/region_year.parquet"""
import csv
import json
import shapely
import sys
from pathlib import Path
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

root = Path(__file__).resolve().parent
source = Path(sys.argv[1])
region, year = source.stem.split("_")
with (root / "codebook.csv").open() as stream:
    rules = {r["original_code"]: r for r in csv.DictReader(stream) if r["nuts"] == region}
if not rules:
    raise SystemExit("No reviewed codes for " + region)
dataset = pq.ParquetFile(source)
folder = root / "parcels" / source.stem
folder.mkdir(parents=True, exist_ok=True)
count = 0
for batch in dataset.iter_batches(batch_size=20000):
    codes = pc.cast(batch.column("original_code"), pa.string())
    keep = pc.is_in(codes, value_set=pa.array(list(rules)))
    table = pa.Table.from_batches([batch.filter(keep)])
    if not table.num_rows:
        continue
    geometry = json.loads(table.schema.metadata[b"geo"])["primary_column"]
    shapes = shapely.from_wkb(table[geometry].to_pylist())
    table = table.filter(pa.array(shapely.is_valid(shapes) & ~shapely.is_empty(shapes)))
    if not table.num_rows:
        continue
    matches = [rules[str(code)] for code in table["original_code"].to_pylist()]
    for col, key in [("harvest_label", "label"), ("source_crop_name", "original_name")]:
        table = table.append_column(col, pa.array([r[key] for r in matches]))
    table = table.append_column("source_region", pa.array([region] * len(matches)))
    table = table.append_column("source_year", pa.array([int(year)] * len(matches)))
    if b"geo" not in table.schema.metadata:
        raise ValueError("Missing GeoParquet geometry metadata")
    pq.write_table(table, folder / f"{count:06d}.parquet", compression="zstd")
    count += 1
print(source.stem, count, "parts")
