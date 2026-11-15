import {test} from 'node:test';
import assert from 'node:assert/strict';
import {build} from 'esbuild';
import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import React from 'react';
import {renderToString} from 'react-dom/server';
test('Review overview renders with production JSX transform in loading, populated and OOF states',async()=>{
 const out=path.resolve(import.meta.dirname,'../.review-render-check.mjs');
 try{
  await build({entryPoints:[path.resolve(import.meta.dirname,'../src/ReviewOverview.jsx')],bundle:true,platform:'node',format:'esm',packages:'external',outfile:out});
  const {default:Component}=await import(pathToFileURL(out));
  for(const status of ['loading','ready'])for(const role of ['inference','oof']){
   const rows=new Map([['barc_1',{field_id:'barc_1',year:2021,prediction_role:'inference',status:'predicted',p_silage:.95}]]);
   const html=renderToString(React.createElement(Component,{v9:{status,year:2021,rows},year:2021,role,controller:{current:null},onOpen:()=>{}}));
   assert.ok(html.includes('First review'));assert.ok(html.includes('Suggested review'));
   if(status==='ready'&&role==='inference')assert.ok(html.includes('100.0%'));
  }
 }finally{await fs.rm(out,{force:true});}
});
