"""Download matching partitions and extract them. Optional args: region [year]."""
import csv
import subprocess
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parent
with (root / "inventory.csv").open() as stream:
    inventory = list(csv.DictReader(stream))
for row in inventory:
    if row["codes_identified"] != "1":
        continue
    if sys.argv[1:] and row["region"] != sys.argv[1]:
        continue
    if sys.argv[2:] and row["year"] != sys.argv[2]:
        continue
    url = row["upstream_url"]
    with tempfile.TemporaryDirectory() as temp:
        local = Path(temp) / url.rsplit("/", 1)[1]
        subprocess.run(["curl", "-fLsS", "--retry", "3", url, "-o", str(local)], check=True)
        subprocess.run([sys.executable, str(root / "extract.py"), str(local)], check=True)
