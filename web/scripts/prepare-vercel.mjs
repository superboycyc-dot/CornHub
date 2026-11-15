// Prepare a static deployment from the already-built app; credentials are never copied.
import fs from 'node:fs/promises';
import path from 'node:path';
const root=path.resolve(import.meta.dirname,'..');
const target=path.join(root,'.vercel-static');
await fs.rm(target,{recursive:true,force:true});await fs.mkdir(target,{recursive:true});
for(const entry of ['index.html','assets','national','reference','v9'])await fs.cp(path.join(root,'dist',entry),path.join(target,entry),{recursive:true});
const manifest=JSON.parse(await fs.readFile(path.join(root,'dist/data/manifest.json')));
const handoffs=JSON.parse(await fs.readFile(path.join(root,'data-handoffs.json')));
const allowed=new Set(handoffs.handoffs.flatMap(h=>h.files));
const files=Object.fromEntries(Object.entries(manifest.files).filter(([name])=>allowed.has(name)));
await fs.mkdir(path.join(target,'data'),{recursive:true});
for(const [name,info] of Object.entries(files))if(info.status==='available'){await fs.mkdir(path.dirname(path.join(target,'data',name)),{recursive:true});await fs.copyFile(path.join(root,'dist/data',name),path.join(target,'data',name));}
await fs.writeFile(path.join(target,'data/manifest.json'),JSON.stringify({files},null,2)+'\n');
await fs.writeFile(path.join(target,'vercel.json'),JSON.stringify({version:2,buildCommand:null,outputDirectory:'.',cleanUrls:false},null,2)+'\n');
console.log('Static deployment prepared in web/.vercel-static. Deploy from that directory with an authenticated Vercel CLI.');
