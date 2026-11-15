import fs from 'node:fs';
import path from 'node:path';
import zlib from 'node:zlib';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {parseV9,confidenceColor,V9_COLORS,v9Key} from '../src/v9.js';
import {decodePolygons} from '../src/national.js';
const root=path.resolve(import.meta.dirname,'..');
const config=JSON.parse(fs.readFileSync(path.join(root,'v9-handoff.json')));
const manifest=JSON.parse(fs.readFileSync(path.join(root,'public/v9/manifest.json')));
const index=JSON.parse(fs.readFileSync(path.join(root,'public/v9/index.json')));
const fields=JSON.parse(fs.readFileSync(path.join(root,'public/data/core/fields.geojson')));
const polygons=JSON.parse(fs.readFileSync(path.join(root,'national/polygons-index.json')));
const identities=new Set(fields.features.map(f=>v9Key(f.properties.source_dataset_id,f.properties.field_id,0)));
for(const tile of polygons.tiles) for(const [id] of decodePolygons(zlib.brotliDecompressSync(fs.readFileSync(path.join(root,'national',tile.path))))) identities.add(v9Key(id.startsWith('csb_')?'csb_corn_2021_2023':'cropsight_corn_2021_2023',id,0));
const groups=[];let total=0,scored=0;
for(const state of config.states)for(const year of config.years) {
 const name=`${state}/${year}.csv`,file=manifest.files[name];assert.equal(file.status,'available');
 const bytes=zlib.gunzipSync(fs.readFileSync(path.join(root,'public/v9',file.path)));
 assert.equal(crypto.createHash('sha256').update(bytes).digest('hex'),file.sha256);
 const original=execFileSync('git',['show',`${config.commit}:${config.base}/${name}`],{cwd:path.dirname(root),maxBuffer:25*1024*1024});assert.deepEqual(bytes,original);
 const rows=parseV9(bytes.toString(),state,year),colors={red:0,yellow:0,green:0,missing:0},status={};
 for(const r of rows) {
  total++;status[r.status]=(status[r.status]||0)+1;
  const color=Object.keys(V9_COLORS).find(k=>V9_COLORS[k]===confidenceColor(r));colors[color]++;
  if(color!=='missing'){scored++;assert.ok(identities.has(v9Key(r.source_dataset_id,r.field_id,0)),`Missing map identity ${r.field_id}`);}
 }
 const expected=index.groups.find(g=>g.state===state&&g.year===year);assert.equal(rows.length,expected.rows);assert.deepEqual(status,expected.counts);
 groups.push({state,year,rows:rows.length,colors});
}
assert.equal(total,index.groups.reduce((n,g)=>n+g.rows,0));assert.equal(scored,(index.totals.predicted||0)+(index.totals.conditional_prediction||0));
const report={status:'passed',source_commit:config.commit,total_rows:total,scored_rows:scored,groups,checks:['All 10 compressed annual CSVs decompress byte-exactly to pinned upstream files','Every real scored record joins an existing map boundary with source namespace unchanged','Runtime parser validated all records, score ranges, classes, uniqueness and state/year/role','Strict >60 and >80 boundaries, null handling and OOF separation covered by tests'],browser_verification:'Not performed: supported browser tool unavailable'};
fs.writeFileSync(path.resolve(root,'../reports/e_web/v9-integration-verification.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));
