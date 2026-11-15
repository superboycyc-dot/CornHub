"""Actual resource accounting and explicitly conservative expansion estimates."""
import json
from datetime import datetime,timezone
import pandas as pd
from global_v2 import OUT,REPORT,write_json,write_csv,sha

def main():
    run=json.loads((REPORT/'run_report.json').read_text());gap=json.loads((REPORT/'gapfill_report.json').read_text());coverage=pd.read_csv(OUT/'coverage.csv');features=pd.read_csv(OUT/'features.csv')
    cache=REPORT/'.cache';bytes_by_kind={p.name:sum(f.stat().st_size for f in p.rglob('*') if f.is_file()) for p in cache.iterdir() if p.is_dir()}
    first=min(p.stat().st_mtime for p in (cache/'catalog').glob('*.json'));finished=datetime.fromisoformat(gap['completed_at_utc'].replace('Z','+00:00')).timestamp();wall=finished-first
    storage=json.loads((REPORT/'storage_report.json').read_text());cache_bytes=sum(bytes_by_kind.values())
    estimates=[]
    for n in [2000,5000]:
        estimates.append(dict(field_years=n,conservative_linear_checkpoint_bytes=round(cache_bytes*n/200),conservative_linear_crop_bytes=round(storage['downloaded_crop_bytes']*n/200),conservative_wall_hours_at_observed_rate=round(wall*n/200/3600,2),basis='linear upper-planning extrapolation of dispersed per-field catalogs;includes warmup/debug/idle;shared catalog/window optimization can reduce costs;not measured at expanded scale',decision='not_started;coordinate storage and optimize before expansion'))
    write_json(REPORT/'budget_report.json',dict(initial_resume_execution_seconds=run['elapsed_seconds'],gapfill_execution_seconds=gap['elapsed_seconds'],wall_seconds_from_first_catalog_checkpoint_to_gapfill_end=wall,wall_clock_includes='catalog requests;metadata;warmup;restarts;development/idle;not a pure CPU benchmark',first_checkpoint_utc=datetime.fromtimestamp(first,timezone.utc).isoformat().replace('+00:00','Z'),completed_at_utc=gap['completed_at_utc'].replace('+00:00','Z'),cache_bytes_by_kind=bytes_by_kind,checkpoint_bytes=cache_bytes,distinct_European_crop_response_bytes=storage['downloaded_crop_bytes'],small_QA_extra_requests='four Netherlands cross-catalog spotchecks and two four-region alignment passes;not included in crop byte sum',quality_counts=features.quality_flag.value_counts().to_dict(),observed_field_years=int((features.valid_obs_count>0).sum()),ndmi_covered_field_years=int((coverage.ndmi_valid_days>0).sum()),unobservable_reasons=coverage.loc[coverage.valid_obs_count==0,'missing_reason'].value_counts().to_dict(),decision='HOLD expansion:73/200 usable;104 limited and23 unobservable. Improve long gaps and deduplicate shared product catalogs/window reads before 2000-5000. Do not change erosion based on label.',team_storage_limit_bytes=10_000_000_000,estimates=estimates))
    write_csv(REPORT/'expansion_budget.csv',estimates)
    files={}
    for root in [OUT,REPORT]:
        for p in root.rglob('*'):
            if p.is_file() and '.cache' not in p.parts and p.name!='delivery_manifest.json':files[str(p.relative_to(REPORT.parents[2]))]=dict(bytes=p.stat().st_size,sha256=sha(p))
    write_json(REPORT/'delivery_manifest.json',dict(files=files,total_artifact_bytes=sum(v['bytes'] for v in files.values()),raw_large_images_included=False))
    print('Resources',cache_bytes,'checkpoint bytes;',round(wall/60,2),'wall minutes;delivery',sum(v['bytes'] for v in files.values()),'bytes')
if __name__=='__main__':main()
