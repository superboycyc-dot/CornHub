"""Convert one original BDPPAD ZIP. Requires pyogrio, pyarrow and pyproj."""
import sys
from pathlib import Path
import json
import pyogrio
import pyarrow as pa
import pyarrow.parquet as pq
from pyproj import CRS
import shapely

source = "/vsizip/" + str(Path(sys.argv[1]).resolve())
query = "NBPRO = 1 AND PRCSUPPR1 = 100 AND CODPRO1 IN ('MGR','MAF')"
meta, table = pyogrio.read_arrow(source, where=query)
geometry = meta["geometry_name"] or "wkb_geometry"
geoms = shapely.from_wkb(table[geometry].to_pylist())
keep = shapely.is_valid(geoms) & ~shapely.is_empty(geoms)
table = table.filter(pa.array(keep))
labels = ["grain" if code == "MGR" else "forage_unspecified" for code in table["CODPRO1"].to_pylist()]
table = table.append_column("harvest_label", pa.array(labels))
geo = {"version":"1.0.0", "primary_column":geometry, "columns":{geometry:{
    "encoding":"WKB", "geometry_types":[], "crs":CRS(meta["crs"]).to_json_dict()}}}
table = table.replace_schema_metadata({b"geo":json.dumps(geo).encode()})
year = table["AN"][0].as_py()
for i, batch in enumerate(table.to_batches(max_chunksize=20000)):
    dest = Path(__file__).parent / f"qc_{year}_{i:03d}.parquet"
    pq.write_table(pa.Table.from_batches([batch]), dest, compression="zstd")
from collections import Counter
print(year, Counter(labels), "discarded geometries", len(geoms)-len(table))
