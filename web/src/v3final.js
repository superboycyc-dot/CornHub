import Papa from 'papaparse';
export {v9Key, v9Record} from './v9.js';
export function band(row) {
  if (!row || row.prediction_role !== 'inference' || !['grain','silage'].includes(row.harvest_type) || !Number.isFinite(row.probability)) return 'unknown';
  if (row.probability >= .9) return 'green';
  if (row.probability >= .6) return 'yellow';
  return 'red';
}
const colors = {green:'#61df8c',yellow:'#ffda42',red:'#ff5b5b',unknown:'#ffffff'};
export const probabilityColor = row => colors[band(row)];
export function parseFinal(csv,year) {
  const parsed = Papa.parse(csv,{header:true,skipEmptyLines:true});
  if (parsed.errors.length) throw Error(parsed.errors[0].message);
  return parsed.data.filter(r=>r.year===String(year)).map(r=>({
    ...r, source_dataset_id:'barc_corn_2021_2023_challenge', model_version:'v3final',
    prediction_role:'inference', training_overlap:r.v3_training_overlap,
    status:!r.harvest_type?'unknown':r.maize_status==='unconfirmed'?'conditional_prediction':'predicted',
    probability:r.probability ? Number(r.probability) : null,
    p_silage:r.p_silage ? Number(r.p_silage) : null
  }));
}
export function v9Details(row) {
  if (!row) return ['v3final · Unknown'];
  return [
    `v3final · ${row.year} · ${row.harvest_type || 'Unknown'}`,
    `Predicted class probability: ${row.probability==null?'Unknown':(100*row.probability).toFixed(1)+'%'}`,
    ...(row.status==='conditional_prediction'?['Conditional on maize; annual eligibility unverified.']:[]),
    ...(row.training_overlap?.toLowerCase()==='true'?['Training overlap: yes']:[])
  ];
}
