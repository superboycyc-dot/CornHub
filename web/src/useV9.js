import {useState,useEffect} from 'react';
import {parseFinal,v9Key} from './v3final';
const empty=new Map();
export default function useV9(year,role) {
 const [state,setState]=useState({status:'loading',year,rows:empty});
 useEffect(()=>{
  if(role!=='inference'){setState({status:'unavailable',year,rows:empty,message:'v3final has inference only; no OOF probability colors'});return;}
  const abort=new AbortController();setState({status:'loading',year,rows:empty});
  (async()=>{
   const response=await fetch('/v3final/v3final.csv',{signal:abort.signal});
   if(!response.ok)throw Error('CSV HTTP '+response.status);
   const records=parseFinal(await response.text(),year);
   if(abort.signal.aborted)return;
   const rows=new Map(records.map(r=>[v9Key(r.source_dataset_id,r.field_id,year),r]));
   if(rows.size!==83 || records.length!==83)throw Error('Expected 83 unique BARC fields');
   setState({status:'ready',year,rows});
  })().catch(e=>{if(e.name!=='AbortError')setState({status:'error',year,rows:empty,message:'v3final data loading failed: '+e.message});});
  return()=>abort.abort();
 },[year,role]);
 return String(state.year)===String(year)&&role==='inference'?state:{status:role==='inference'?'loading':'unavailable',year,rows:empty,message:role==='inference'?'Loading V9…':'v3final inference only · no OOF probability colors'};
}
