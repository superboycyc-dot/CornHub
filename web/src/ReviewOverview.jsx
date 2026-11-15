import {useState,useEffect,useMemo} from 'react';
import {reviewGroups} from './review-overview';
const labels={red:'First review',orange:'Suggested review',green:'Green'};
export default function ReviewOverview({v9,year,role,controller,onOpen}){
 const [active,setActive]=useState(null),[locations,setLocations]=useState({}),[error,setError]=useState('');
 const stats=useMemo(()=>reviewGroups(v9,year,role),[v9,year,role]);
 useEffect(()=>{const a=new AbortController();fetch('/v9/locations.json',{signal:a.signal}).then(r=>{if(!r.ok)throw Error('Location data unavailable');return r.json();}).then(setLocations).catch(e=>{if(e.name!=='AbortError')setError(e.message);});return()=>a.abort();},[]);
 useEffect(()=>{const close=e=>{if(e.key==='Escape')setActive(null);};document.addEventListener('keydown',close);return()=>document.removeEventListener('keydown',close);},[]);
 return <>
  <section className="review-overview" aria-label="Prediction review overview">
   <div className="review-scope">MARYLAND · {year} · {stats.ready?`${stats.total} predicted field records`:'Predictions unavailable for this view'}</div>
   <div className="review-cards">{Object.entries(labels).map(([key,label])=><button key={key} className={`review-card ${key}`} aria-pressed={active===key} onClick={()=>{setActive(active===key?null:key);onOpen();}}>
    <span>{label}</span><strong>{stats.ready&&stats.total?`${(stats.groups[key].length/stats.total*100).toFixed(1)}%`:'—'}</strong><small>{stats.ready?stats.groups[key].length:'—'} fields · {key==='red'?'≤60%':key==='orange'?'>60–90%':'>90%'}</small>
   </button>)}</div>
   <small className="review-note">Share of available predictions, including conditional maize results. Color-based review groups; not estimated error rates.</small>
  </section>
  {active&&<section className="review-list" aria-label={`${labels[active]} field list`}>
   <header><div><small>{year} · MARYLAND · {role.toUpperCase()}</small><h2>{labels[active]} <span>{stats.groups[active].length}</span></h2></div><button aria-label="Close field list" onClick={()=>setActive(null)}>×</button></header>
   <p>Source ID is shown when no field name is supplied. Locations are boundary centers; harvest dates have not been supplied.</p>
   {error&&<p role="alert">{error}</p>}
   <div className="review-list-scroll">{!stats.groups[active].length?<p>No predictions in this group for the selected year and role.</p>:stats.groups[active].map(r=>{const loc=locations[r.field_id];return <article key={`${r.source_dataset_id}:${r.field_id}`}>
    <div className="review-row-heading"><strong>{loc?.name||r.field_id}</strong><b>{(r.p_silage*100).toFixed(1)}%</b></div>
    <p>Model silage probability · predicted use: <strong>{r.harvest_type==='silage'?'Silage':'Grain'}</strong></p>
    <p>{loc?`Maryland · ${loc.lat.toFixed(5)}, ${loc.lng.toFixed(5)} (boundary center)`:'Location not provided'}</p>
    <small>{r.source_dataset_id} · {r.status==='conditional_prediction'?'Conditional on maize; annual eligibility unverified':r.status}{r.training_overlap?.toLowerCase()==='true'?' · Training overlap':''}</small>
    {loc&&<button onClick={()=>{controller.current?.setView([loc.lat,loc.lng],16);setActive(null);}}>Locate on map ↗</button>}
   </article>;})}</div>
  </section>}
 </>;
}
