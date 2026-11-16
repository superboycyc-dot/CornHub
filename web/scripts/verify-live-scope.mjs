import fs from 'node:fs';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import zlib from 'node:zlib';
import {decodePolygons} from '../src/national.js';
const root=path.resolve(import.meta.dirname,'..');
const url='https://cornhub-field-evidence.feistydegu3.chatgpt.site';
const get=p=>execFileSync('curl',['-f','-sS','--max-time','45',url+p],{maxBuffer:20*1024*1024});
const results=[];
function exact(remote,local) {const b=get(remote);assert.deepEqual(b,fs.readFileSync(local));results.push({path:remote,bytes:b.length,sha256:crypto.createHash('sha256').update(b).digest('hex')});return b;}
const release=JSON.parse(exact('/reference/release.json',path.join(root,'reference/release.json')));
assert.deepEqual(release.outline_states,['MD','CA']);
const html=exact('/',path.join(root,'dist/index.html')).toString();
const asset=html.match(/src="(\/assets\/[^\"]+\.js)"/)[1];
const js=exact(asset,path.join(root,'dist',asset)).toString();
assert.ok(js.includes('MD + CA outlines'));
const polygons=JSON.parse(exact('/national/polygons-index.json',path.join(root,'national/polygons-index.json')));
const points=JSON.parse(exact('/national/index.json',path.join(root,'national/index.json')));
exact('/national/overview.json',path.join(root,'national/overview.json'));
for(const state of ['06','24']) {
 const tile=polygons.tiles.find(t=>decodePolygons(zlib.brotliDecompressSync(fs.readFileSync(path.join(root,'national',t.path)))).some(([id])=>id.startsWith('csb_'+state)));
 assert.ok(tile,'State outline exists');exact('/national/'+tile.path,path.join(root,'national',tile.path));
}
for(const t of [points.tiles[0],points.tiles.find(t=>t.x===35 && t.y===48)||points.tiles.at(-1)]) exact('/national/'+t.path,path.join(root,'national',t.path));
const report={verified_at:new Date().toISOString(),url,release:release.release,sites_version:13,source_commit:'8feefd206ffc073cb1c3cb86f5c2f50ece6fea8f',deployment_id:'appgdep_6af92649e8308191bdcfd9909171c115',status:'live HTTP bytes match local build',resources:results,visual_browser_verification:'Not performed: supported browser tool unavailable'};
fs.writeFileSync(path.resolve(root,'../reports/e_web/deployment-scope-verification.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));
