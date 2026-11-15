import {useState,useEffect} from 'react';
import {parseV9,v9Key} from './v9';
const empty=new Map();
export default function useV9(year,role) {
 const [state,setState]=useState({status:'loading',year,rows:empty});
 useEffect(()=>{
  if(role!=='inference'){setState({status:'unavailable',year,rows:empty,message:'V9 has inference only; no OOF probability colors'});return;}
  const abort=new AbortController();setState({status:'loading',year,rows:empty});
  (async()=>{
   const r=await fetch('/v9/manifest.json',{signal:abort.signal});if(!r.ok)throw Error(`Manifest HTTP ${r.status}`);const manifest=await r.json();
   if(!Array.isArray(manifest.states)||manifest.states.length!==1||manifest.states[0]!=='MD')throw Error('Expected Maryland-only prediction scope');
   const chunks=await Promise.all(manifest.states.map(async state=>{
    const file=manifest.files[`${state}/${year}.csv`];if(file?.status!=='available')throw Error(`${state} ${year} data not provided`);
    const r=await fetch('/v9/'+file.path,{signal:abort.signal});if(!r.ok)throw Error(`${state} HTTP ${r.status}`);
    const bytes=await r.arrayBuffer();const text=new Uint8Array(bytes)[0]===31?await new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'))).text():new TextDecoder().decode(bytes);
    return parseV9(text,state,year);
   }));
   if(abort.signal.aborted)return;
   const rows=new Map(chunks.flat().map(r=>[v9Key(r.source_dataset_id,r.field_id,r.year),r]));
   setState({status:'ready',year,rows,message:'MD V9 partial processing · inference only',source_commit:manifest.source_commit});
  })().catch(e=>{if(e.name!=='AbortError')setState({status:'error',year,rows:empty,message:'V9 data loading failed: '+e.message});});
  return()=>abort.abort();
 },[year,role]);
 return String(state.year)===String(year)&&role==='inference'?state:{status:role==='inference'?'loading':'unavailable',year,rows:empty,message:role==='inference'?'Loading V9…':'V9 inference only · no OOF probability colors'};
}
