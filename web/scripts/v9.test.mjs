import {test} from 'node:test';
import assert from 'node:assert/strict';
import {confidenceColor,V9_COLORS,parseV9,v9Record,v9Key} from '../src/v9.js';
const row={status:'predicted',prediction_role:'inference',p_silage:.9};
test('V9 confidence boundaries are strict and missing/OOF results stay white',()=>{
 for(const [n,key] of [[0,'red'],[60,'red'],[60.0001,'yellow'],[80,'yellow'],[90,'yellow'],[90.0001,'green'],[100,'green']])assert.equal(confidenceColor({...row,confidence_score:n}),V9_COLORS[key]);
 for(const r of [null,{...row,confidence_score:null},{...row,confidence_score:99,prediction_role:'oof'},{...row,confidence_score:99,status:'pending_observations'}])assert.equal(confidenceColor(r),V9_COLORS.missing);
 assert.equal(confidenceColor({...row,status:'conditional_prediction',confidence_score:70}),V9_COLORS.yellow);
});
const header='field_id,source_dataset_id,state,year,confidence_score,raw_self_confidence,p_silage,status,harvest_type,prediction_role,model_version';
const record='csb_061623001006171,csb_corn_2021_2023,CA,2022,28.48,99,0.99,predicted,silage,inference,V9';
test('V9 parser preserves IDs and keeps model probability distinct from confidence',()=>{
 const [r]=parseV9(header+'\n'+record,'CA',2022);assert.equal(r.field_id,'csb_061623001006171');assert.equal(r.confidence_score,28.48);assert.equal(r.p_silage,.99);assert.equal(confidenceColor(r),V9_COLORS.red);
 assert.throws(()=>parseV9(header+'\n'+record,'MD',2022),/mismatch/);
 assert.throws(()=>parseV9(header+'\n'+record+'\n'+record,'CA',2022),/Duplicate/);
 assert.throws(()=>parseV9(header+'\n'+record.replace(',28.48,',',101,'),'CA',2022),/Invalid/);
 assert.throws(()=>parseV9(header+'\n'+record.replace(',predicted,',',pending_observations,'),'CA',2022),/Uncomputed/);
 const empty=record.replace('28.48,99,0.99,predicted,silage',',,,pending_observations,');assert.equal(parseV9(header+'\n'+empty,'CA',2022)[0].confidence_score,null);
 const rows=new Map([[v9Key(r.source_dataset_id,r.field_id,r.year),r]]);const v9={year:2022,status:'ready',rows};
 assert.equal(v9Record(v9,r.source_dataset_id,r.field_id,2022,'inference'),r);
 assert.equal(v9Record(v9,r.source_dataset_id,r.field_id,2023,'inference'),null);
 assert.equal(v9Record(v9,r.source_dataset_id,r.field_id,2022,'oof'),null);
 assert.equal(v9Record(v9,'different',r.field_id,2022,'inference'),null);
});
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import zlib from 'node:zlib';
import {syncV9} from './sync-v9.mjs';
test('V9 sync keeps source CSV bytes and missing files; repeated sync removes stale copies',async()=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'cornhub-v9-'));
 try {
  await fs.mkdir(path.join(root,'web'),{recursive:true});await fs.mkdir(path.join(root,'data/processed/model/v9_states/CA'),{recursive:true});
  await fs.writeFile(path.join(root,'web/v9-handoff.json'),JSON.stringify({base:'data/processed/model/v9_states',commit:'unavailable',branch:'data/v9-ca-md-2021-2025',states:['CA'],years:[2022]}));
  const src=path.join(root,'data/processed/model/v9_states/CA/2022.csv'),bytes=Buffer.from(header+'\r\n'+record+'\r\n');await fs.writeFile(src,bytes);
  const first=await syncV9(root);assert.equal(first.files['CA/2022.csv'].status,'available');assert.equal(first.files['index.json'].status,'missing');
  assert.deepEqual(zlib.gunzipSync(await fs.readFile(path.join(root,'web/public/v9/CA/2022.csv.gz'))),bytes);
  await fs.rm(src);const second=await syncV9(root);assert.equal(second.files['CA/2022.csv'].status,'missing');await assert.rejects(fs.access(path.join(root,'web/public/v9/CA/2022.csv.gz')));
 }finally{await fs.rm(root,{recursive:true,force:true});}
});
test('Maryland-only publication excludes California even when local California CSVs exist',async()=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'cornhub-md-scope-'));
 try {
  await fs.mkdir(path.join(root,'web'),{recursive:true});
  await fs.writeFile(path.join(root,'web/v9-handoff.json'),JSON.stringify({base:'data/processed/model/v9_states',commit:'unavailable',branch:'data/v9-ca-md-2021-2025',states:['MD'],years:[2022]}));
  for(const state of ['MD','CA']) {const dir=path.join(root,'data/processed/model/v9_states',state);await fs.mkdir(dir,{recursive:true});await fs.writeFile(path.join(dir,'2022.csv'),state+' source bytes\r\n');}
  const m=await syncV9(root);assert.deepEqual(m.states,['MD']);assert.equal(m.files['MD/2022.csv'].status,'available');assert.equal(m.files['CA/2022.csv'],undefined);await assert.rejects(fs.access(path.join(root,'web/public/v9/CA')));
 }finally{await fs.rm(root,{recursive:true,force:true});}
});
