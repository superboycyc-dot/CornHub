import Papa from 'papaparse';
export const V9_COLORS={red:'#ff5b5b',yellow:'#ffa447',green:'#61df8c',missing:'#ffffff'};
export function probabilityColor(row) {
 if(!row || !['predicted','conditional_prediction'].includes(row.status) || row.prediction_role!=='inference' || row.p_silage==null) return V9_COLORS.missing;
 const n=row.p_silage;
 return n>0.9?V9_COLORS.green:n>0.6?V9_COLORS.yellow:V9_COLORS.red;
}
export function v9Key(source,id,year) {return JSON.stringify([source,id,Number(year)]);}
export function v9Record(v9,source,id,year,role) {
 if(role!=='inference'||String(v9.year)!==String(year)||v9.status!=='ready') return null;
 return v9.rows.get(v9Key(source,id,year))||null;
}
export function parseV9(csv,state,year) {
 const parsed=Papa.parse(csv,{header:true,skipEmptyLines:true});
 if(parsed.errors.length)throw Error('Invalid V9 CSV: '+parsed.errors[0].message);
 const required=['field_id','source_dataset_id','year','state','confidence_score','raw_self_confidence','p_silage','status','harvest_type','prediction_role','model_version'];
 if(required.some(k=>!parsed.meta.fields.includes(k)))throw Error('Missing V9 schema columns');
 const seen=new Set();
 return parsed.data.map(raw=>{
  if(raw.state!==state||Number(raw.year)!==Number(year)||raw.prediction_role!=='inference'||!raw.field_id||!raw.source_dataset_id||!raw.model_version)throw Error('V9 identity/year/role mismatch');
  const key=v9Key(raw.source_dataset_id,raw.field_id,year);if(seen.has(key))throw Error('Duplicate V9 prediction');seen.add(key);
  const row={...raw};
  for(const k of ['confidence_score','raw_self_confidence','p_silage']) {
   row[k]=raw[k]===''?null:Number(raw[k]);
   if(row[k]!==null&&(!Number.isFinite(row[k])||row[k]<0||row[k]>(k==='p_silage'?1:100)))throw Error('Invalid V9 score');
  }
  const scored=['predicted','conditional_prediction'].includes(row.status);
  if(scored) {
   if(row.p_silage===null)throw Error('Incomplete V9 prediction');
   if(row.harvest_type!==(row.p_silage>=.5?'silage':'grain'))throw Error('V9 class mismatch');
  } else if(row.harvest_type||[row.p_silage,row.confidence_score,row.raw_self_confidence].some(n=>n!==null))throw Error('Uncomputed V9 row contains scores');
  return row;
 });
}
export function v9Details(row) {
 if(!row)return ['V9 inference: Not computed / no matching result'];
 return [
  `V9 ${row.year} inference · ${row.model_version}`,
  `Predicted class: ${row.harvest_type||'Not computed'}`,
  `Model silage probability: ${row.p_silage==null?'Not computed':(row.p_silage*100).toFixed(1)+'%'}`,
  `Experimental confidence score: ${row.confidence_score==null?'Not computed':row.confidence_score.toFixed(1)+'/100'}`,
  `Raw uncalibrated class probability: ${row.raw_self_confidence==null?'Not computed':row.raw_self_confidence.toFixed(1)+'%'}`,
  `Status: ${row.status}`,
  `Confidence version: ${row.confidence_version||"Not provided"}`,
  ...(row.status==='conditional_prediction'?['Conditional on maize: annual corn eligibility unverified.']:[]),
  ...(row.training_overlap?.toLowerCase()==='true'?['Training overlap: yes · not an independent evaluation']:[]),
  `Satellite quality: ${row.quality_flag||'Not provided'}`,
  ...(row.missing_reason?[`Source note: ${row.missing_reason}`]:[]),
  'Experimental score, not validated accuracy. CA transfer not independently validated.',
 ];
}
