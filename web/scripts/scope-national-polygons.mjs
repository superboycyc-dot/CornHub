// Reproducible, idempotent display scope reduction. Original upstream data is untouched.
import fs from 'node:fs';
import path from 'node:path';
import zlib from 'node:zlib';
import crypto from 'node:crypto';
const root = path.resolve(import.meta.dirname, '../national');
const read = p => JSON.parse(fs.readFileSync(p, 'utf8'));
const index = read(path.join(root, 'polygons-index.json'));
const stateNames={MD:'24',CA:'06'};
const selected=(process.argv.find(v=>v.startsWith('--states='))?.slice(9)||'MD').split(',');
if(!selected.length||selected.some(s=>!stateNames[s]))throw Error('Supported outline states: MD,CA');
const fips=selected.map(s=>stateNames[s]);
const counties = read(path.resolve(root, '../reference/us-counties.geojson')).features.filter(f => fips.includes(f.properties.STATE));
function ringContains([x,y], ring) {
  let inside=false;
  for(let i=0,j=ring.length-1;i<ring.length;j=i++) {
    const [a,b]=ring[i], [c,d]=ring[j];
    if ((b>y)!==(d>y) && x<(c-a)*(y-b)/(d-b)+a) inside=!inside;
  }
  return inside;
}
function stateAt(point) {
  for(const f of counties) {
    const [w,s,e,n]=f.bbox;
    if(point[0]<w || point[0]>e || point[1]<s || point[1]>n) continue;
    const polys=f.geometry.type==='Polygon'?[f.geometry.coordinates]:f.geometry.coordinates;
    if(polys.some(p=>ringContains(point,p[0])&&!p.slice(1).some(r=>ringContains(point,r)))) return f.properties.STATE;
  }
  return null;
}
const counts={'06':0,'24':0}, ids=new Set(), tiles=[];
for(const t of index.tiles) {
  const src=path.join(root,t.path);
  // Decode records without changing their geometry or source identifiers.
  const b=zlib.brotliDecompressSync(fs.readFileSync(src));
  let o=8;const records=[];let vertices=0;
  for(let i=0;i<b.readUInt32LE(4);i++) {
    const start=o, num=b.readBigUInt64LE(o);o+=8;
    const len=b[o++], flags=b[o++], kind=b[o++], np=b.readUInt32LE(o);o+=4;
    let w=180,s=90,e=-180,n=-90, nv=0;
    for(let p=0;p<np;p++) {
      const nr=b.readUInt32LE(o);o+=4;
      for(let r=0;r<nr;r++) {
        const nn=b.readUInt32LE(o);o+=4;let x=0,y=0;nv+=nn;
        for(let j=0;j<nn;j++) {x+=b.readInt32LE(o);y+=b.readInt32LE(o+4);o+=8;w=Math.min(w,x/1e6);e=Math.max(e,x/1e6);s=Math.min(s,y/1e6);n=Math.max(n,y/1e6);}
      }
    }
    const raw=num.toString().padStart(len,'0');
    // CSB candidate IDs retain the source STATEFIPS prefix; CropSight has no state attribute.
    const state=flags&16 ? stateAt([(w+e)/2,(s+n)/2]) : raw.slice(0,2);
    if(!fips.includes(state)) continue;
    counts[state]++;ids.add((flags&16?'cropsight_':'csb_')+raw);records.push(b.subarray(start,o));vertices+=nv;
  }
  if(o!==b.length) throw Error('Invalid geometry offsets: '+t.path);
  if(!records.length) {fs.unlinkSync(src);continue;}
  const h=Buffer.alloc(8);h.write('NPG2');h.writeUInt32LE(records.length,4);
  const packed=zlib.brotliCompressSync(Buffer.concat([h,...records]),{params:{[zlib.constants.BROTLI_PARAM_QUALITY]:8}});
  // Atomic replacement avoids modifying hardlinked publication copies.
  fs.writeFileSync(src+'.tmp',packed);fs.renameSync(src+'.tmp',src);
  tiles.push({...t,count:records.length,bytes:packed.length,sha256:crypto.createHash('sha256').update(packed).digest('hex'),vertices});
}
index.tiles=tiles;index.objects=ids.size;index.vertices=tiles.reduce((n,t)=>n+t.vertices,0);
index.outline_states=selected;index.state_counts=Object.fromEntries(selected.map(s=>[s,counts[stateNames[s]]]));
index.notes='Outlines limited to the configured states in outline_states. CSB uses original source STATEFIPS ID prefix; CropSight uses geometry bbox center within Census county boundaries. All other candidates remain points. Display geometry and source IDs preserved.';
fs.writeFileSync(path.join(root,'polygons-index.json'),JSON.stringify(index));
const points=read(path.join(root,'index.json'));
let total=0, marked=0;
for(const t of points.tiles) {
  const dest=path.join(root,t.path), b=zlib.gunzipSync(fs.readFileSync(dest));
  for(let o=8;o<b.length;o+=14) {
    const raw=b.readBigUInt64LE(o).toString().padStart(b[o+13],'0');
    const id=(b[o+12]&16?'cropsight_':'csb_')+raw;
    const outlined=ids.has(id);b[o+12]=(b[o+12]&~32)|(outlined?32:0);marked+=outlined;total++;
  }
  const encoded=zlib.gzipSync(b,{level:9});
  fs.writeFileSync(dest+'.tmp',encoded);fs.renameSync(dest+'.tmp',dest);
  t.bytes=encoded.length;t.sha256=crypto.createHash('sha256').update(encoded).digest('hex');
}
if(marked!==ids.size) throw Error(`Outline/point identity mismatch ${marked}/${ids.size}`);
points.compressed_bytes=points.tiles.reduce((n,t)=>n+t.bytes,0);
points.outline_flag=32;points.outline_states=selected;
fs.writeFileSync(path.join(root,'index.json'),JSON.stringify(points));
console.log(JSON.stringify({objects:total,outlines:ids.size,states:index.state_counts,polygon_bytes:tiles.reduce((n,t)=>n+t.bytes,0),tiles:tiles.length}));
