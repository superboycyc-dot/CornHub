"""Extract whole-field maize operations with explicit crop and equipment evidence."""
import csv
import hashlib
import io
import re
import sqlite3
import zipfile
from datetime import datetime
from pathlib import Path
from pypdf import PdfReader

root = Path(__file__).resolve().parent
gpkg = root.parents[2] / '04_Evaluation/BARC_Corn.2021-2023.gpkg'
db = sqlite3.connect(gpkg)
query = 'SELECT OBJECTID,FARM,FIELD,Corn_2021,Corn_2022,Corn_2023 FROM barc_silage_grain_corn20212023'
fields = {}
normalize = lambda text: re.sub(r'\s+', '', text).casefold()
for obj, farm, field, *labels in db.execute(query):
    key = normalize(farm), normalize(field)
    assert key not in fields
    fields[key] = obj, labels
archive = root / 'BARCFarmMgmt.zip'
with (root / 'harvest_operations.csv').open('w') as output, zipfile.ZipFile(archive) as z:
    writer = csv.writer(output)
    writer.writerow(['pdf','page','farm','field','date','acres','harvest_label','basis','source_record','matching_boundary_id','challenge_year_label'])
    for filename in sorted(z.namelist()):
        farm, field = Path(filename).stem.split('_',1)
        for page, pdfpage in enumerate(PdfReader(io.BytesIO(z.read(filename))).pages,1):
            text = pdfpage.extract_text()
            if 'Harvest Report' not in text:
                continue
            text = text.partition('1-866-761-8001')[0]
            entries = re.split(r'(?m)^(\d{1,2}/\d{1,2}/\d{2})\s*$',text)
            for rawdate, content in zip(entries[1::2],entries[2::2]):
                row = ' '.join(content.split()).split('_____')[0].strip()
                match = re.match(r'(.+?) Whole Field ([\d,.]+) (.+)',row)
                if not match or normalize(match[1]) != normalize(field):
                    continue
                if '(CSIL)' in row and 'Chopper' in row:
                    label,basis = 'silage','CSIL + chopper'
                elif '(FLDCRN)' in row and 'Combine' in row:
                    label,basis = 'grain','field corn + combine'
                else:
                    continue
                date = datetime.strptime(rawdate,'%m/%d/%y').date()
                obj, labels = fields.get((normalize(farm),normalize(field)),('',[]))
                existing = labels[date.year-2021] if labels and 2021<=date.year<=2023 else ''
                writer.writerow([filename,page,farm,field,date,match[2],label,basis,row,'barc_'+str(obj) if obj!='' else '',existing])
