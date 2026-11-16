import fs from 'node:fs/promises';import path from 'node:path';import {execFileSync} from 'node:child_process';
export async function syncFieldMetadata(root){
 const config=JSON.parse(await fs.readFile(path.join(root,'web/v9-handoff.json'))),index=JSON.parse(await fs.readFile(path.join(root,'web/public/v9/index.json'))),rows={};
 const files=new Set(index.groups.filter(g=>config.states.includes(g.state)).flatMap(g=>g.geometry));
 for(const file of files){let bytes;try{bytes=await fs.readFile(path.join(root,config.base,file));}catch{bytes=execFileSync('git',['show',`${config.commit}:${config.base}/${file}`],{cwd:root,maxBuffer:20*1024*1024});}for(const f of JSON.parse(bytes).features){const p=f.properties;rows[p.field_id]={area_ha:p.area_ha??null,source_dataset_id:p.source_dataset_id};}}
 await fs.writeFile(path.join(root,'web/public/v9/field-metadata.json'),JSON.stringify(rows));
}
