import React from 'react';

// Maryland annual yields (grain bu/ac, silage US tons/ac) and grain USD/bu.
const benchmarks = {
  2021: [175, 20, 6.39],
  2022: [165, 19, 6.75],
  2023: [165, 17, 4.90],
  2024: [143, 16, 4.70],
  2025: [171, 18, 4.40],
};
const whole = new Intl.NumberFormat('en-US', {maximumFractionDigits:0});
export default function HarvestSummary({stats, fields, year}) {
  if (!stats.ready || !stats.total) return null;
  const areas = new Map(fields?.features.map(({properties:p})=>[p.field_id,p.area_ha]));
  const rows = Object.values(stats.groups).flat();
  const [grainYield,silageYield,grainPrice] = benchmarks[year];
  const crops = ['silage','grain'].map(type=>{
    const group = rows.filter(r=>r.harvest_type===type);
    const hectares = group.map(r=>areas.get(r.field_id));
    const acres = hectares.every(a=>Number.isFinite(a) && a>0)
      ? hectares.reduce((sum,a)=>sum+a,0)*2.4710538147 : null;
    const output = acres===null ? null : acres*(type==='grain'?grainYield:silageYield);
    const value = output===null ? null : output*grainPrice*(type==='grain'?1:8);
    return {type,share:100*group.length/rows.length,output,value};
  });
  return <section className="harvest-summary" aria-label="Predicted harvest mix">
    <h3>Predicted harvest mix</h3>
    <div className="harvest-mix">
      <div aria-hidden="true" className="harvest-ring" style={{'--silage-share':crops[0].share+'%'}}/>
      {[crops[1], crops[0]].map(c=><div key={c.type} className={'harvest-share '+c.type}>
        <span>{c.type}</span><strong>{c.share.toFixed(1)}%</strong>
      </div>)}
    </div>
    <small className="harvest-count">{rows.length} classified fields</small>
    <table><caption>Estimated harvest</caption><thead><tr><th>Use</th><th>Production</th><th>Gross value</th></tr></thead>
      <tbody>{crops.map(c=><tr key={c.type}><th>{c.type}</th><td>{c.output===null?'—':whole.format(c.output)+(c.type==='grain'?' bu':' US tons')}</td><td>{c.value===null?'—':'$'+whole.format(c.value)}</td></tr>)}</tbody>
    </table>
    <details><summary>Estimate assumptions</summary>
      <p>Assumes corn on all classified acres. Each field contributes its full area to its predicted use. Unknown fields are excluded.</p>
      <p>Maryland {year} yields: {grainYield} bu/ac grain and {silageYield} US tons/ac silage. Grain price: ${grainPrice.toFixed(2)}/bu. Silage uses an indicative price of ${(8*grainPrice).toFixed(2)}/US ton (8 × grain price).</p>
      <a href={'https://www.nass.usda.gov/Quick_Stats/Ag_Overview/stateOverview.php?state=MARYLAND&year='+year}>USDA Maryland statistics</a> · <a href="https://extension.psu.edu/dairy-sense-pricing-feed-from-field-moving-past-thumb-rules">Silage pricing method</a>
    </details>
  </section>;
}
