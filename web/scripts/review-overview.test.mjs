import {test} from 'node:test';
import assert from 'node:assert/strict';
import {reviewGroups} from '../src/review-overview.js';
test('Review percentages count available same-year inference records and preserve threshold edges',()=>{
 const rows=new Map([.6,.9,.91,null].map((p,i)=>[i,{field_id:String(i),year:2021,prediction_role:'inference',status:p===null?'pending_observations':'predicted',p_silage:p}]));rows.set(5,{field_id:'other',year:2022,prediction_role:'inference',status:'predicted',p_silage:.99});
 const v={year:2021,status:'ready',rows};const s=reviewGroups(v,2021,'inference');assert.equal(s.total,3);assert.equal(s.unavailable,1);assert.deepEqual(Object.values(s.groups).map(r=>r.length),[1,1,1]);assert.equal(reviewGroups(v,2021,'oof').total,0);assert.equal(reviewGroups(v,2022,'inference').ready,false);
});
