import fs from 'node:fs/promises';
import path from 'node:path';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {gzipSync} from 'node:zlib';
import {createHash} from 'node:crypto';
const exec=promisify(execFile);
export async function syncV9(root) {
 const config=JSON.parse(await fs.readFile(path.join(root,'web/v9-handoff.json'),'utf8'));
 const target=path.join(root,'web/public/v9');await fs.rm(target,{recursive:true,force:true});await fs.mkdir(target,{recursive:true});
 const manifest={source_commit:config.commit,branch:config.branch,states:config.states,years:config.years,files:{}};
 for(const name of ['index.json','README.md','verification.json',...config.states.flatMap(s=>config.years.map(y=>`${s}/${y}.csv`))]) {
  let bytes,source;
  try {bytes=await fs.readFile(path.join(root,config.base,name));source='local:'+config.base+'/'+name;}
  catch(e) {if(e.code!=='ENOENT')throw e;
   try {bytes=(await exec('git',['show',`${config.commit}:${config.base}/${name}`],{cwd:root,encoding:'buffer',maxBuffer:25*1024*1024})).stdout;source=`git:${config.commit}:${config.base}/${name}`;}catch{manifest.files[name]={status:'missing',reason:`Fetch origin ${config.branch}; no scores generated.`};continue;}
  }
  const compressed=name.endsWith('.csv'),file=name+(compressed?'.gz':'');
  const dest=path.join(target,file);await fs.mkdir(path.dirname(dest),{recursive:true});
  const output=compressed?gzipSync(bytes,{level:6}):bytes;await fs.writeFile(dest,output);
  manifest.files[name]={status:'available',path:file,source,bytes:bytes.length,sha256:createHash('sha256').update(bytes).digest('hex'),transport_bytes:output.length};
 }
 await fs.writeFile(path.join(target,'manifest.json'),JSON.stringify(manifest,null,2)+'\n');
 console.log(`V9: ${Object.values(manifest.files).filter(f=>f.status==='available').length} files available; missing results remain unavailable`);
 return manifest;
}
