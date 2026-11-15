"""Global labeled-data experiment with explicit missingness and regional validation."""
import csv
from collections import Counter,defaultdict
from datetime import datetime,timezone,date
import gzip,hashlib,json,os,platform,shutil,subprocess,tarfile,tempfile,zipfile
from pathlib import Path
import joblib,numpy as np,pyarrow as pa,pyarrow.parquet as pq,sklearn
from pyproj import Geod
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score,balanced_accuracy_score,confusion_matrix,f1_score,precision_score,recall_score,brier_score_loss,roc_auc_score
from sklearn.pipeline import make_pipeline

ROOT=Path(__file__).resolve().parent
RUN=ROOT/'runs'/('step3-global-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'));RUN.mkdir(parents=True)
INPUT=RUN/'inputs';INPUT.mkdir();(RUN/'models').mkdir()
FEATURES=['ndvi_peak','peak_doy','max_drop_per_day','drop_doy','ndvi_late_mean','nearest_dairy_distance_km']
PARAMS=dict(n_estimators=100,max_depth=4,min_samples_leaf=2,max_features=1.0,class_weight=None,random_state=42,n_jobs=4)
env=dict(os.environ);env['GIT_SSH_COMMAND']=f'ssh -i {ROOT}/keys/github_readonly -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile={ROOT}/keys/known_hosts'
# Use the existing repository-only read credential; no new access is created.
cache=ROOT/'repository.git'
def git(*args,capture=False):return subprocess.run(['git','--git-dir',str(cache),*args],env=env,check=True,stdout=subprocess.PIPE if capture else None).stdout
def write(name,value):(RUN/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def read_csv(p):
 with p.open(encoding='utf-8-sig',newline='') as h:return list(csv.DictReader(h))
def csvout(name,rows,cols=None):
 with (RUN/name).open('w',encoding='utf-8-sig',newline='') as h:
  w=csv.DictWriter(h,fieldnames=cols or list(rows[0]));w.writeheader();w.writerows(rows)
def fnum(value):
 try:
  x=float(value);return x if np.isfinite(x) else None
 except (TypeError,ValueError):return None

sources={
 'data/global-maize-fields':['data/global_maize/','data/americas/'],
 'main':['reports/training/step1_ndvi_maryland/','reports/training/step2_ndvi_dairy_distance_maryland_v2/','data/processed/maryland_field_dairy_distances/dairy_locations.csv'],
}
git('fetch','--depth=1','origin',*[f'+refs/heads/{b}:refs/remotes/origin/{b}' for b in sources])
commits={b:git('rev-parse',f'refs/remotes/origin/{b}',capture=True).decode().strip() for b in sources}
manifest=[]
for branch,prefixes in sources.items():
 entries=git('ls-tree','-r','--name-only',commits[branch],capture=True).decode().splitlines();paths=[p for p in entries if any(p.startswith(pre) for pre in prefixes)]
 with tempfile.TemporaryFile() as h:
  subprocess.run(['git','--git-dir',str(cache),'archive',commits[branch],'--',*paths],env=env,stdout=h,check=True);h.seek(0)
  with tarfile.open(fileobj=h) as z:z.extractall(INPUT,filter='data')
 for p in paths:manifest.append(dict(path=p,branch=branch,commit=commits[branch],sha256=hashlib.sha256((INPUT/p).read_bytes()).hexdigest()))
write('input_manifest.json',manifest);shutil.copyfile(__file__,RUN/'train_step3.py')
base=INPUT/'reports/training/step1_ndvi_maryland'
retained=INPUT/'reports/training/step2_ndvi_dairy_distance_maryland_v2'
official=read_csv(retained/'frozen_training_rows.csv');official_map={(r['field_id'],int(r['year'])):r for r in official}
if len(official_map)!=44 or len({k[0] for k in official_map})!=34:raise RuntimeError('Official Maryland cohort changed')
farm_locations=read_csv(INPUT/'data/processed/maryland_field_dairy_distances/dairy_locations.csv')
if len(farm_locations)!=67 or any(f['state']!='MD' for f in farm_locations):raise RuntimeError('Unexpected dairy geography')
farm_lon=np.array([float(f['longitude']) for f in farm_locations]);farm_lat=np.array([float(f['latitude']) for f in farm_locations]);geod=Geod(ellps='WGS84')
americas=read_csv(INPUT/'data/americas/field_harvest.csv')
nl=read_csv(INPUT/'data/global_maize/netherlands_2025/field_index.csv')

observations=defaultdict(lambda:defaultdict(list))
observation_sources=defaultdict(set)
def add_obs(country,fid,year,day,ndvi,source):
 v=fnum(ndvi)
 if v is None or not -1<=v<=1:return
 d=date.fromisoformat(day[:10]);year=int(year)
 if d.year!=year:raise RuntimeError('Observation year mismatch')
 if not date(year,4,1)<=d<date(year,12,1):return
 key=(country,str(fid),year);observations[key][d].append(v);observation_sources[key].add(source)
for r in read_csv(INPUT/'data/americas/satellite/us_existing_sentinel2.csv'):
 if (fnum(r['valid_pixel_fraction']) or 0)>=.5:add_obs('US',r['field_id'],r['year'],r['date'],r['ndvi'],'S2_field')
with gzip.open(INPUT/'data/americas/satellite/point_samples.csv.gz','rt',encoding='utf-8-sig',newline='') as h:
 for r in csv.DictReader(h):
  if r['status']=='valid' and (fnum(r['valid_pixels']) or 0)>0:add_obs(r['country'],r['field_id'],r['year'],r['date'],r['ndvi'],'S2_point')
for r in read_csv(INPUT/'data/americas/satellite/us_2015_landsat8.csv'):
 if r['status']=='valid' and (fnum(r['valid_pixels']) or 0)>0:add_obs('US',r['field_id'],r['year'],r['date'],r['ndvi'],'L8_point')
for r in read_csv(INPUT/'data/global_maize/netherlands_2025/ndvi_all.csv'):
 valid=fnum(r['valid_pixels']) or 0;interior=fnum(r['interior_pixels']) or 0
 if valid>=3 and interior>0 and valid/interior>=.5:add_obs('NL',r['field_id'],2025,r['date'],r['ndvi_median'],'S2_field')

def extract(key):
 days=sorted((d,float(np.median(v))) for d,v in observations.get(key,{}).items())
 result={name:None for name in FEATURES}
 if not days:return result,0
 peak=max(v for d,v in days);peak_day=next(d for d,v in days if v==peak)
 result.update(ndvi_peak=peak,peak_doy=peak_day.timetuple().tm_yday)
 late=[v for d,v in days if d.month>=9]
 if late:result['ndvi_late_mean']=float(np.mean(late))
 if len(days)>=2:
  drops=[(max(0.,(a[1]-b[1])/(b[0]-a[0]).days),b[0]) for a,b in zip(days,days[1:])];drop=max(v for v,d in drops)
  result['max_drop_per_day']=drop
  if drop>0:result['drop_doy']=min(d for v,d in drops if np.isclose(v,drop,rtol=1e-12,atol=1e-12)).timetuple().tm_yday
 return result,len(days)

us_farm_names={r['field_id']:''.join(r['farm'].lower().split()) for r in americas if r['country']=='US'}
all_rows=[];seen=set();official_seen=set();conflicts=[]
def add(row):
 if row['sample_id'] in seen:raise RuntimeError('Duplicate source-specific field-year '+row['sample_id'])
 seen.add(row['sample_id']);all_rows.append(row)
for r in americas:
 country=r['country'];fid=r['field_id'];year=int(r['year']);label=r['harvest_method'];key=(country,fid,year)
 feat,n=extract(key);lon=fnum(r['longitude']);lat=fnum(r['latitude'])
 is_official=country=='US' and (fid,year) in official_map;conflicted=False
 if is_official:
  original=official_map[(fid,year)];official_seen.add((fid,year))
  if label!=original['label']:
   conflicts.append(dict(country=country,field_id=fid,year=year,official_label=original['label'],external_label=label,external_operations=r['operations_labels'],handling='Excluded from global training/scoring; retained only as original official benchmark test label'))
   label=original['label'];conflicted=True
  for name in FEATURES:feat[name]=fnum(original[name])
 if country=='US' and feat['nearest_dairy_distance_km'] is None and lon is not None and lat is not None:
  _,_,m=geod.inv(np.full(67,lon),np.full(67,lat),farm_lon,farm_lat);feat['nearest_dairy_distance_km']=float(np.min(m))/1000
 if country=='US':group='US:farm:'+''.join(r['farm'].lower().split())
 elif lon is not None and lat is not None:group=f'{country}:cell:{int(np.floor(lon/.1))}:{int(np.floor(lat/.1))}'
 else:group=f'{country}:field:{fid}'
 status='benchmark_only_conflicted_evidence' if conflicted else 'eligible' if label in ['grain','silage'] and any(feat[n] is not None for n in FEATURES[:5]) else 'label_conflict_or_unknown' if label not in ['grain','silage'] else 'no_valid_ndvi'
 add(dict(sample_id=f'{country}:{fid}:{year}',country=country,region=r['region'],field_id=fid,year=year,label=label,spatial_group=group,longitude=lon,latitude=lat,evidence_status=r['evidence_status'],official_maryland=is_official,ndvi_valid_dates=n,observation_support='official_frozen_features' if is_official else '|'.join(sorted(observation_sources[key])),status=status,**feat))
if official_seen!=set(official_map):raise RuntimeError('Not all 44 official Maryland rows present')
if conflicts:csvout('label_conflicts.csv',conflicts)
for r in nl:
 fid=r['field_id'];year=int(r['year']);feat,n=extract(('NL',fid,year));lon=float(r['inside_lon']);lat=float(r['inside_lat'])
 add(dict(sample_id=f'NL:{fid}:{year}',country='NL',region='southeast_sample',field_id=fid,year=year,label=r['harvest_label'],spatial_group=f'NL:cell:{int(np.floor(lon/.05))}:{int(np.floor(lat/.05))}',longitude=lon,latitude=lat,evidence_status='declared',official_maryland=False,ndvi_valid_dates=n,observation_support='S2_field',status='eligible' if n else 'no_valid_ndvi',**feat))
regions={'be2':'BE','be3':'BE','bg':'BG','cz':'CZ','de4':'DE','dk':'DK','si':'SI','sk':'SK'}
for path in sorted((INPUT/'data/global_maize/eurocrops/parcels').rglob('*.parquet')):
 table=pq.read_table(path,columns=['cropfield','source_region','source_year','harvest_label'])
 for r in table.to_pylist():
  region=str(r['source_region']);year=int(r['source_year']);fid=str(r['cropfield']);label=r['harvest_label']
  add(dict(sample_id=f'EU:{region}:{fid}:{year}',country=regions[region],region=region,field_id=fid,year=year,label=label,spatial_group=f'EU:{region}:{fid}',longitude=None,latitude=None,evidence_status='declared',official_maryland=False,ndvi_valid_dates=0,observation_support='',status='no_valid_ndvi' if label in ['grain','silage'] else 'label_conflict_or_unknown',**{n:None for n in FEATURES}))

pq.write_table(pa.Table.from_pylist(all_rows),RUN/'global_labeled_inventory.parquet',compression='zstd')
eligible=[r for r in all_rows if r['status'] in ['eligible','benchmark_only_conflicted_evidence']];trainable=np.array([r['status']=='eligible' for r in eligible]);y=np.array([int(r['label']=='silage') for r in eligible]);country=np.array([r['country'] for r in eligible]);group=np.array([r['spatial_group'] for r in eligible]);X=np.array([[np.nan if r[n] is None else r[n] for n in FEATURES] for r in eligible],dtype=float)
if any(r['country']!='US' and r['nearest_dairy_distance_km'] is not None for r in eligible):raise RuntimeError('Invented non-US dairy distance')
if not len(eligible) or len(set(y[trainable]))!=2:raise RuntimeError('Insufficient labeled usable data')
pq.write_table(pa.Table.from_pylist([r for r in eligible if r['status']=='eligible']),RUN/'training_rows.parquet',compression='zstd')
coverage=[]
for c,region in sorted({(r['country'],r['region']) for r in all_rows}):
 subset=[r for r in all_rows if r['country']==c and r['region']==region];selected=[r for r in subset if r['status']=='eligible'];conflicted=[r for r in subset if r['status']=='benchmark_only_conflicted_evidence']
 coverage.append(dict(country=c,region=region,labeled_records=len(subset),grain=sum(r['label']=='grain' for r in subset),silage=sum(r['label']=='silage' for r in subset),conflicted=len(conflicted),eligible=len(selected),excluded_no_valid_ndvi=sum(r['status']=='no_valid_ndvi' for r in subset),median_valid_ndvi_dates=(float(np.median([r['ndvi_valid_dates'] for r in selected])) if selected else None)))
csvout('coverage_by_region.csv',coverage)
missing=[dict(feature=f,missing_eligible=int(np.isnan(X[trainable,j]).sum()),eligible_total=int(sum(trainable))) for j,f in enumerate(FEATURES)];csvout('missingness.csv',missing)
excluded_inventory=[]
cached=(ROOT/'workspace').resolve()/'data/processed/external_corn'
for folder in ['csb','cropsight']:
 paths=list((cached/folder).rglob('*.parquet'));count=sum(pq.read_metadata(p).num_rows for p in paths)
 excluded_inventory.append(dict(source=folder,records=count,reason='No silage/grain ground-truth labels; corn presence is not a harvest-use label',input_path=str(cached/folder)))
 write('unlabeled_sources_excluded.json',excluded_inventory)
write('protocol.json',dict(features=FEATURES,parameters=PARAMS,threshold=.5,partial_missing='fold-local median imputation + missing indicators; all-missing training columns retained as zero',all_feature_missing='retain null candidate row and abstain; do not train/score with no informative NDVI',sample_weight='class-balanced, then equal-country contribution within each class; weights fit on training rows only',validation=['five deterministic farm/spatial-group folds','leave-one-country-out for observed US/CA/NL','same official Maryland 44 rows with foreign training augmentation and original five farm folds'],negative_labels_not_inferred=True,region_or_country_not_predictors=True,no_hyperparameter_or_threshold_search=True,global_scope='repository multi-country subset, not worldwide coverage',limitations=['Canadian eligible records are grain-only','Netherlands is a small local sample dominated by silage','Europe has labels but missing NDVI and dairy distances: pending enrichment, not measured accuracy','Point vs field NDVI and sparse vs dense sampling differ by source','Missingness can proxy source; source-held-out results are essential','2026 Maryland dairy locations not independently verified for historical years','No claim of new blind-test accuracy for repeatedly viewed Maryland data']))
print('Dataset prepared:',len(all_rows),'labeled records;',int(sum(trainable)),'eligible;',Counter(zip(country[trainable],y[trainable])),flush=True)

def model():return make_pipeline(SimpleImputer(strategy='median',add_indicator=True,keep_empty_features=True),RandomForestClassifier(**PARAMS))
def weights(indices):
 countries_by_class={label:set(country[indices][y[indices]==label]) for label in [0,1]};counts=Counter(zip(country[indices],y[indices]));return np.array([len(indices)/(2*len(countries_by_class[y[i]])*counts[(country[i],y[i])]) for i in indices])
def fit(indices):
 if len(set(y[indices]))!=2:raise RuntimeError('Training set lacks a class')
 m=model();m.fit(X[indices],y[indices],randomforestclassifier__sample_weight=weights(indices));return m
def probability(m,indices):return m.predict_proba(X[indices])[:,list(m.classes_).index(1)]
def score(indices,p):
 truth=y[indices];pred=(np.asarray(p)>=.5).astype(int);both=len(set(truth))==2
 return dict(n=len(indices),correct=int(sum(truth==pred)),accuracy=float(accuracy_score(truth,pred)),macro_f1=float(f1_score(truth,pred,average='macro',labels=[0,1],zero_division=0)) if both else None,balanced_accuracy=float(balanced_accuracy_score(truth,pred)) if both else None,silage_precision=float(precision_score(truth,pred,zero_division=0)),silage_recall=float(recall_score(truth,pred,zero_division=0)) if 1 in truth else None,roc_auc=float(roc_auc_score(truth,p)) if both else None,brier_score=float(brier_score_loss(truth,p)),confusion_matrix=confusion_matrix(truth,pred,labels=[0,1]).tolist(),confusion_order=['grain','silage'],class_counts={'grain':int(sum(truth==0)),'silage':int(sum(truth==1))},always_grain_accuracy=float(np.mean(truth==0)),test_has_both_classes=both)
def serial_predictions(indices,p,role,fold):
 return [dict(sample_id=eligible[i]['sample_id'],country=eligible[i]['country'],field_id=eligible[i]['field_id'],year=eligible[i]['year'],true_label=eligible[i]['label'],p_silage=float(value),predicted_label='silage' if value>=.5 else 'grain',prediction_role=role,fold_id=str(fold)) for i,value in zip(indices,p)]

fold_ids=np.array([int(hashlib.sha256(g.encode()).hexdigest()[:8],16)%5 for g in group]);oof=np.full(len(eligible),np.nan);fold_reports=[];prediction_rows=[]
for fold in range(5):
 train=np.flatnonzero((fold_ids!=fold)&trainable);test=np.flatnonzero((fold_ids==fold)&trainable)
 if not len(test):continue
 if set(group[train])&set(group[test]):raise RuntimeError('Spatial/farm group leakage')
 if {eligible[i]['country']+':'+eligible[i]['field_id'] for i in train}&{eligible[i]['country']+':'+eligible[i]['field_id'] for i in test}:raise RuntimeError('Field across years leaked')
 m=fit(train);p=probability(m,test);oof[test]=p;joblib.dump(dict(model=m,features=FEATURES,threshold=.5),RUN/'models'/f'global_group_fold_{fold}.joblib')
 np.testing.assert_allclose(probability(joblib.load(RUN/'models'/f'global_group_fold_{fold}.joblib')['model'],test),p,rtol=0,atol=1e-12)
 fold_reports.append(dict(fold_id=fold,n_train=len(train),n_test=len(test),test_groups=len(set(group[test])),metrics=score(test,p)));prediction_rows+=serial_predictions(test,p,'spatial_group_oof',fold)
 print('Spatial fold',fold,score(test,p)['accuracy'],flush=True)
if not np.isfinite(oof[trainable]).all():raise RuntimeError('Incomplete group OOF')
all_indices=np.flatnonzero(trainable);regional={c:score(np.flatnonzero((country==c)&trainable),oof[(country==c)&trainable]) for c in sorted(set(country[trainable]))}
group_metrics=dict(pooled=score(all_indices,oof[trainable]),by_country=regional,country_macro_accuracy=float(np.mean([r['accuracy'] for r in regional.values()])),warning='Pooled accuracy is dominated by grain-only Quebec; report country and class metrics alongside it')
write('spatial_group_metrics.json',group_metrics);write('spatial_fold_metrics.json',fold_reports)

transfer={};transfer_rows=[]
for c in sorted(set(country)):
 train=np.flatnonzero((country!=c)&trainable);test=np.flatnonzero((country==c)&trainable);m=fit(train);p=probability(m,test);joblib.dump(dict(model=m,features=FEATURES,threshold=.5),RUN/'models'/f'country_holdout_{c}.joblib')
 transfer[c]=dict(train_countries=sorted(set(country[train])),test_country=c,metrics=score(test,p));transfer_rows+=serial_predictions(test,p,'country_holdout',c)
 print('Country holdout',c,transfer[c]['metrics']['accuracy'],flush=True)
write('country_holdout_metrics.json',dict(by_country=transfer,country_macro_accuracy=float(np.mean([r['metrics']['accuracy'] for r in transfer.values()])),warning='Only countries with usable observed features are scored; no Europe-all-null accuracy claim'))

official_indices=np.array([i for i,r in enumerate(eligible) if r['official_maryland']],dtype=int)
if len(official_indices)!=44:raise RuntimeError('Lost official benchmark rows')
foreign=np.flatnonzero((country!='US')&trainable);md_probs=np.full(44,np.nan);md_rows=[]
for fold in sorted({official_map[(eligible[i]['field_id'],eligible[i]['year'])]['fold_id'] for i in official_indices}):
 test=np.array([i for i in official_indices if official_map[(eligible[i]['field_id'],eligible[i]['year'])]['fold_id']==fold],dtype=int);local_train=np.array([i for i in official_indices if official_map[(eligible[i]['field_id'],eligible[i]['year'])]['fold_id']!=fold and trainable[i]],dtype=int);train=np.concatenate([local_train,foreign])
 test_farms={official_map[(eligible[i]['field_id'],eligible[i]['year'])]['farm_group'] for i in test};train_farms={official_map[(eligible[i]['field_id'],eligible[i]['year'])]['farm_group'] for i in local_train}
 if test_farms&train_farms:raise RuntimeError('Official benchmark farm leakage')
 m=fit(train);p=probability(m,test);positions=[int(np.where(official_indices==i)[0][0]) for i in test];md_probs[positions]=p;md_rows+=serial_predictions(test,p,'maryland_foreign_augmented_oof',fold);joblib.dump(dict(model=m,features=FEATURES,threshold=.5),RUN/'models'/f'maryland_augmented_fold_{fold}.joblib')
if not np.isfinite(md_probs).all():raise RuntimeError('Incomplete official benchmark')
baseline=json.loads((retained/'metrics.json').read_text())['metrics']['ndvi_distance'];clean_official=trainable[official_indices];md_metrics=dict(retained_step2_accuracy=baseline['accuracy'],foreign_augmented=score(official_indices,md_probs),clean_official_without_conflict=score(official_indices[clean_official],md_probs[clean_official]),accuracy_change_pp=100*(score(official_indices,md_probs)['accuracy']-baseline['accuracy']),same_44_test_rows_and_outer_farm_folds=True,conflicted_rows_excluded_from_training=len(conflicts),warning='One conflicted official row excluded from training but original benchmark test label retained; global missingness representation and source/class weights also differ from retained model')
write('maryland_benchmark.json',md_metrics)

pq.write_table(pa.Table.from_pylist(prediction_rows),RUN/'spatial_oof_predictions.parquet',compression='zstd');pq.write_table(pa.Table.from_pylist(transfer_rows),RUN/'country_holdout_predictions.parquet',compression='zstd');csvout('maryland_augmented_predictions.csv',md_rows)
full=fit(all_indices);joblib.dump(dict(model=full,features=FEATURES,threshold=.5,parameters=PARAMS,missing_policy='median + indicators; abstain when all NDVI missing',scope='eligible repository US/CA/NL observations, not worldwide validated'),RUN/'models/global_full_model.joblib')
probe=all_indices[:min(100,len(all_indices))];np.testing.assert_allclose(probability(joblib.load(RUN/'models/global_full_model.joblib')['model'],probe),probability(full,probe),rtol=0,atol=1e-12)
csvout('feature_importance.csv',[dict(feature=n,importance=float(v)) for n,v in zip(full.named_steps['simpleimputer'].get_feature_names_out(FEATURES),full.named_steps['randomforestclassifier'].feature_importances_)])
summary=dict(status='trained_and_evaluated',stage=3,labeled_candidate_records=len(all_rows),eligible_records=len(all_indices),eligible_class_counts={'grain':int(sum(y[trainable]==0)),'silage':int(sum(y[trainable]==1))},countries_with_observed_features=sorted(set(country[trainable])),excluded_no_ndvi=sum(r['status']=='no_valid_ndvi' for r in all_rows),excluded_conflicted=sum(r['status'] in ['label_conflict_or_unknown','benchmark_only_conflicted_evidence'] for r in all_rows),spatial_group_oof=group_metrics,country_holdout_macro_accuracy=float(np.mean([r['metrics']['accuracy'] for r in transfer.values()])),country_holdout={c:r['metrics'] for c,r in transfer.items()},maryland_benchmark=md_metrics,retained_model_replaced=False,scope='Existing repository multi-country subset; no full-world coverage or independent global accuracy claim')
write('metrics.json',summary);write('environment.json',dict(hostname=platform.node(),python=platform.python_version(),numpy=np.__version__,sklearn=sklearn.__version__,pyarrow=pa.__version__,parameters=PARAMS,commits=commits,execution='NVIDIA Brev CPU, four forest workers'))
write('verification.json',dict(unique_source_field_year_keys=True,official_44_preserved=True,no_national_corn_presence_labels_used_as_harvest_labels=True,no_overseas_to_maryland_dairy_distances_invented=True,missing_labels_not_imputed=True,all_null_ndvi_abstains=True,fold_local_imputation_and_weights=True,spatial_farm_and_field_groups_disjoint=True,country_holdout_train_test_disjoint=True,all_eligible_rows_have_oof=True,saved_group_fold_and_full_models_reload_equal=True,retained_8182_model_unchanged=True,probability_reload_absolute_tolerance=1e-12))
write('model_checksums.json',{str(p.relative_to(RUN)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (RUN/'models').glob('*.joblib')})
(RUN/'requirements.lock.txt').write_text(subprocess.check_output([str(ROOT/'venv/bin/python'),'-m','pip','freeze'],text=True))
lines=['# 第三步：现有跨国数据训练','',f'全部在NVIDIA Brev执行。读取{len(all_rows):,}条有用途标签或冲突待核记录；实际有可用特征、可训练及验证的为{len(all_indices):,}条。有效国家为'+', '.join(sorted(set(country[trainable])))+'。其他欧洲地区用途标签已保留，但没有NDVI，因此全部相关特征为null，暂不训练或评分。全国CSB和CropSight只有玉米类别，没有青贮/籽粒真值，不冒充用途标签。','', '|来源|可训练记录|籽粒|青贮|','|---|---:|---:|---:|']
for c in sorted(set(country)):
 idx=np.flatnonzero((country==c)&trainable);lines.append(f'|{c}|{len(idx):,}|{sum(y[idx]==0):,}|{sum(y[idx]==1):,}|')
lines+=['', '## 实际验证','', '|来源|同地区空间/农场分组OOF准确率|整国留出准确率|整国留出宏平均F1|','|---|---:|---:|---:|']
for c in sorted(set(country)):
 t=transfer[c]['metrics'];f1=f'{t["macro_f1"]:.4f}' if t['macro_f1'] is not None else '不定义：仅一个真实类别';lines.append(f'|{c}|{regional[c]["accuracy"]:.2%}|{t["accuracy"]:.2%}|{f1}|')
lines+=['',f'空间分组OOF的混合准确率为{group_metrics["pooled"]["accuracy"]:.2%}，全部猜籽粒也有{group_metrics["pooled"]["always_grain_accuracy"]:.2%}；混合分数受到大量加拿大籽粒样本影响，不能作为全世界泛化准确率。各国家等权平均准确率：同地区分组{group_metrics["country_macro_accuracy"]:.2%}，整国留出{summary["country_holdout_macro_accuracy"]:.2%}。', '',f'原44条马里兰基准在相同留出农场上加入外国训练样本后，准确率{md_metrics["foreign_augmented"]["accuracy"]:.2%}（{md_metrics["foreign_augmented"]["correct"]}/44）；保留的本地模型为81.82%，差值{md_metrics["accuracy_change_pp"]:+.2f}个百分点。**不替换用户选定的81.82%模型。**','',f'发现{len(conflicts)}条官方标签与整合作业证据冲突（barc_248/2023）；它们不参与全球训练、全球评分或马里兰训练折，只保留原官方测试标签作44条历史基准。排除冲突后的43条马里兰测试结果另见maryland_benchmark.json，训练集合与原44条完整训练设置有所区别。','', '## 缺失值与限制','', '5个NDVI衍生特征加最近奶牛场距离。部分缺失用每个训练折中位数加缺失指示器，整列在训练折缺失时保留为零和缺失标记；真实标签绝不填补。全部NDVI缺失的候选记录保留null且拒绝评分。海外距离未知仍为null，未用到马里兰奶牛场的跨洲距离替代。', '', '按国家和类别平衡训练样本权重，避免加拿大样本数量压倒其他来源。空间验证的划分以农场/空间块为单位，整国留出完全排除测试国家；马里兰44条基准保持原五折，额外美国作业记录不混入该基准训练。参数、种子、阈值固定，没有根据第三步验证结果调参。', '', '加拿大此次只有籽粒，荷兰仅局部样本；欧洲申报用途不等于逐田实收确认。单点NDVI与整田NDVI不同，2个日期的最大值不等于完整生长季峰值。缺测模式可代理来源地区，整国留出指标尤其重要。来源缺失、地域和年份迁移尚未解决，本次不是世界范围验证。历史马里兰数据已多次用于开发，不是新盲测。', '', '数据清单、完整候选和训练Parquet、逐田预测、模型及源码在NVIDIA运行目录中保存。Git交付含报告、覆盖率、源哈希、逐田预测压缩包和模型包；原始输入可按input_manifest.json复取。代码放到/home/ubuntu/cornhub-compute/，用venv/bin/python train_step3.py运行，或用控制器train-step3任务。']
(RUN/'README.md').write_text('\n'.join(lines)+'\n')
with zipfile.ZipFile(RUN/'trained_models.zip','w',zipfile.ZIP_DEFLATED) as z:
 for p in (RUN/'models').glob('*.joblib'):z.write(p,p.relative_to(RUN))
 for name in ['environment.json','metrics.json','model_checksums.json']:z.write(RUN/name,name)
with zipfile.ZipFile(RUN/'prediction_data.zip','w',zipfile.ZIP_DEFLATED) as z:
 for name in ['spatial_oof_predictions.parquet','country_holdout_predictions.parquet','training_rows.parquet','global_labeled_inventory.parquet']:z.write(RUN/name,name)
(ROOT/'latest_step3.txt').write_text(str(RUN));print(json.dumps(summary,ensure_ascii=False,indent=2));print('Results:',RUN)
