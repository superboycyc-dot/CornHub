import {band} from './v3final.js';
export function reviewGroups(v9,year,role){
 const groups={red:[],yellow:[],green:[]};
 if(v9.status!=='ready'||String(v9.year)!==String(year)||role!=='inference')return {groups,total:0,unavailable:0,ready:false};
 let unavailable=0;
 for(const row of v9.rows.values()){
  if(String(row.year)!==String(year)||row.prediction_role!==role)continue;
  const group=band(row);
  if(group==='unknown'){unavailable++;continue;}
  groups[group].push(row);
 }
 for(const list of Object.values(groups))list.sort((a,b)=>a.probability-b.probability||a.field_id.localeCompare(b.field_id));
 return {groups,unavailable,total:Object.values(groups).reduce((n,g)=>n+g.length,0),ready:true};
}
