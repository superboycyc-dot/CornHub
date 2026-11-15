import fs from 'node:fs';
import path from 'node:path';
import zlib from 'node:zlib';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {decodeTile,decodePolygons} from '../src/national.js';
const root=path.resolve(import.meta.dirname,'../national');
const index=JSON.parse(fs.readFileSync(path.join(root,'index.json')));
const polygons=JSON.parse(fs.readFileSync(path.join(root,'polygons-index.json')));
const ids=new Set();let objects=0,flagged=0;
for(const t of polygons.tiles) {
 const packed=fs.readFileSync(path.join(root,t.path));
 assert.equal(crypto.createHash('sha256').update(packed).digest('hex'),t.sha256);
 const rows=decodePolygons(zlib.brotliDecompressSync(packed));assert.equal(rows.length,t.count);
 for(const [id] of rows) {assert.ok(!ids.has(id));ids.add(id);if(id.startsWith('csb_'))assert.ok(['06','24'].includes(id.slice(4,6)));}
}
for(const t of index.tiles) {
 const packed=fs.readFileSync(path.join(root,t.path));
 assert.equal(crypto.createHash('sha256').update(packed).digest('hex'),t.sha256);
 const bytes=zlib.gunzipSync(packed);
 const original=zlib.gunzipSync(execFileSync('git',['show','f223ef8:web/national/'+t.path],{cwd:path.resolve(root,'../..'),maxBuffer:20*1024*1024}));
 const compare=Buffer.from(bytes);
 for(let o=8;o<compare.length;o+=14) compare[o+12]&=~32;
 assert.deepEqual(compare,original,'Original IDs, coordinates, years and validity must remain unchanged');
 const arr=bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength);
 for(const f of decodeTile(arr,t,index.tile_zoom)) {assert.equal(!!(f.flags&32),ids.has(f.candidate_id));objects++;flagged+=!!(f.flags&32);}
}
assert.equal(objects,6128148);assert.equal(flagged,polygons.objects);assert.equal(ids.size,flagged);
const report={status:'passed',objects,outlined:flagged,state_counts:polygons.state_counts,polygon_bytes:polygons.tiles.reduce((n,t)=>n+t.bytes,0),point_bytes:index.compressed_bytes,checks:['All point IDs, coordinates, annual eligibility and geometry validity byte-equal to original','Only MD/CA CSB IDs in outline inventory; CropSight classified against Census county geometry by generator','Every outline identity occurs exactly once and has point suppression flag','All transport hashes and row counts verified'],browser_verification:'Not performed: supported browser tool unavailable'};
fs.writeFileSync(path.resolve(root,'../../reports/e_web/national-scope-verification.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));
