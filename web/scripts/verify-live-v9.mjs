import fs from 'node:fs';
import path from 'node:path';
import zlib from 'node:zlib';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {parseV9,confidenceColor,V9_COLORS} from '../src/v9.js';
const root=path.resolve(import.meta.dirname,'..'),url='https://cornhub-field-evidence.feistydegu3.chatgpt.site';
const get=p=>execFileSync('curl',['-f','-sS','--max-time','45',url+p],{maxBuffer:25*1024*1024});
const resources=[];
function exact(p,file) {const bytes=get(p);assert.deepEqual(bytes,fs.readFileSync(file));resources.push({path:p,bytes:bytes.length,sha256:crypto.createHash('sha256').update(bytes).digest('hex')});return bytes;}
const release=JSON.parse(exact('/reference/release.json',path.join(root,'reference/release.json')));assert.equal(release.confidence_field,'confidence_score');assert.equal(release.default_prediction_role,'inference');
const html=exact('/',path.join(root,'dist/index.html')).toString(),asset=html.match(/src="(\/assets\/[^\"]+\.js)"/)[1];
const js=exact(asset,path.join(root,'dist',asset)).toString();assert.ok(js.includes('V9 experimental confidence'));for(const color of Object.values(V9_COLORS))assert.ok(js.includes(color));
const css=html.match(/href="(\/assets\/[^\"]+\.css)"/)[1];exact(css,path.join(root,'dist',css));
const manifest=JSON.parse(exact('/v9/manifest.json',path.join(root,'public/v9/manifest.json')));assert.equal(manifest.source_commit,release.v9_source_commit);
exact('/v9/index.json',path.join(root,'public/v9/index.json'));
const colors={red:0,yellow:0,green:0,missing:0};let rows=0;
for(const [name,file] of Object.entries(manifest.files)) {
 if(!name.endsWith('.csv'))continue;assert.equal(file.status,'available');
 const bytes=exact('/v9/'+file.path,path.join(root,'public/v9',file.path));
 const raw=zlib.gunzipSync(bytes);assert.equal(crypto.createHash('sha256').update(raw).digest('hex'),file.sha256);
 const [state,year]=name.split('/');
 for(const r of parseV9(raw.toString(),state,Number(year.slice(0,4)))){rows++;const key=Object.keys(V9_COLORS).find(k=>V9_COLORS[k]===confidenceColor(r));colors[key]++;}
}
assert.equal(rows,341550);assert.equal(colors.red+colors.yellow+colors.green,67);
const report={verified_at:new Date().toISOString(),url,status:'passed',sites_version:14,release:release.release,source_commit:'3e9b21bcbb84f1c50e21d77c4882e25d6f3e6d49',upstream_commit:release.v9_source_commit,deployment_id:'appgdep_6af932fef2c48191a9af5a5c24ce9b81',http_without_cache_busting:true,rows,colors,resources,browser_verification:'Not performed: supported browser tool unavailable'};
fs.writeFileSync(path.resolve(root,'../reports/e_web/v9-live-verification.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));
