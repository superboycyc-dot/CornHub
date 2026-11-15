export function reviewGroups(v9,year,role){
 const groups={red:[],orange:[],green:[]};
 if(v9.status!=='ready'||String(v9.year)!==String(year)||role!=='inference')return {groups,total:0,ready:false};
 for(const row of v9.rows.values()){
  if(String(row.year)!==String(year)||row.prediction_role!==role||!['predicted','conditional_prediction'].includes(row.status)||typeof row.p_silage!=='number'||!Number.isFinite(row.p_silage))continue;
  groups[row.p_silage>.9?'green':row.p_silage>.6?'orange':'red'].push(row);
 }
 for(const list of Object.values(groups))list.sort((a,b)=>a.p_silage-b.p_silage||a.field_id.localeCompare(b.field_id));
 return {groups,total:Object.values(groups).reduce((n,g)=>n+g.length,0),ready:true};
}
