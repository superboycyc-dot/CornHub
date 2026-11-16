import fs from 'node:fs/promises';
import path from 'node:path';
import {brotliDecompressSync} from 'node:zlib';
import {decodePolygons} from '../src/national.js';
export async function syncFieldLocations(root){
 const rows={};
 function add(id,geometry,name){let w=180,e=-180,s=90,n=-90;function walk(c){if(typeof c[0]==='number'){w=Math.min(w,c[0]);e=Math.max(e,c[0]);s=Math.min(s,c[1]);n=Math.max(n,c[1]);}else c.forEach(walk);}walk(geometry.coordinates);rows[id]={name:name||id,lat:(s+n)/2,lng:(w+e)/2,location_type:'Source boundary bounding-box center'};}
 const index=JSON.parse(await fs.readFile(path.join(root,'web/national/polygons-index.json')));
 for(const tile of index.tiles)for(const [id,flags,geometry] of decodePolygons(brotliDecompressSync(await fs.readFile(path.join(root,'web/national',tile.path)))))add(id,geometry);
 try{const fields=JSON.parse(await fs.readFile(path.join(root,'web/public/data/core/fields.geojson')));for(const f of fields.features)add(f.properties.field_id,f.geometry,f.properties.name);}catch(e){if(e.code!=='ENOENT')throw e;}
 await fs.writeFile(path.join(root,'web/public/v9/locations.json'),JSON.stringify(rows));
}
