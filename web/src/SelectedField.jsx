import React,{useEffect,useState} from 'react';
export default function SelectedField({id,source,row,area,year,role}){
 const [metadata,setMetadata]=useState({});
 useEffect(()=>{const a=new AbortController();fetch('/v9/field-metadata.json',{signal:a.signal}).then(r=>{if(!r.ok)throw Error();return r.json();}).then(setMetadata).catch(()=>{});return()=>a.abort();},[]);
 const p=typeof row?.p_silage==='number'?row.p_silage:null;
 const label=row?.harvest_type||row?.predicted_label;
 const probability=role==='inference'?(row?.probability??null):(p===null?null:label==='grain'?1-p:p);
 const size=area??metadata[id]?.area_ha;
 return <div className="selected-field-detail">
  <section className="selected-field-primary">
   <span className="section-kicker">HARVEST USE PREDICTION</span>
   <h3>{label==='silage'?'Silage':label==='grain'?'Grain':'Not computed'}</h3>
   <div className="selected-field-probability">{probability===null?'—':`${(probability*100).toFixed(1)}%`}</div>
   <p className="metric-caption">Probability of predicted harvest use</p>
   <dl><dt>Area</dt><dd>{size!=null&&Number.isFinite(Number(size))?`${Number(size).toFixed(2)} ha`:'Not provided'}</dd><dt>Field ID</dt><dd>{id||'No field selected'}</dd></dl>
   <small>Scroll for source details ↓</small>
  </section>
  <section className="selected-field-source"><span className="section-kicker">SOURCE DATASET</span><p>{source||metadata[id]?.source_dataset_id||'Not provided'}</p><dl><dt>Year / role</dt><dd>{year} / {role}</dd><dt>Model silage probability</dt><dd>{p===null?'Not computed':`${(p*100).toFixed(1)}%`}</dd><dt>Model version</dt><dd>{row?.model_version||'Not provided'}</dd></dl><p>Map colors show the v3final probability of the predicted harvest use.</p>{row?.status==='conditional_prediction'&&<p>Conditional on maize; annual crop eligibility unverified.</p>}<p>Harvest date not provided. Model probability is not validated accuracy.</p></section>
 </div>;
}
