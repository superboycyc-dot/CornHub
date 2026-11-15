"""Exclude predeclared extreme label-composition countries and compare on matched OOF rows."""
import csv,hashlib,json,platform,zipfile
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path

import joblib,numpy as np,pyarrow.parquet as pq,sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score,balanced_accuracy_score,confusion_matrix,f1_score,precision_score,recall_score,roc_auc_score
from sklearn.pipeline import make_pipeline

ROOT=Path(__file__).resolve().parent
SOURCE=Path((ROOT/'latest_step3.txt').read_text().strip())
STEP4=Path((ROOT/'latest_step4_blind.txt').read_text().strip())
RUN=ROOT/'runs'/('step5-trim-extreme-countries-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
RUN.mkdir(parents=True);(RUN/'models').mkdir()
FEATURES=['ndvi_peak','peak_doy','max_drop_per_day','drop_doy','ndvi_late_mean']
PARAMS=dict(n_estimators=100,max_depth=4,min_samples_leaf=2,max_features=1.0,class_weight='balanced',random_state=42,n_jobs=4)
rows=pq.read_table(SOURCE/'training_rows.parquet',columns=['sample_id','country','field_id','year','label','spatial_group',*FEATURES]).to_pylist()
preds=list(csv.DictReader((STEP4/'oof_predictions.csv').open(encoding='utf-8-sig',newline='')))
prev={r['sample_id']:r for r in preds if r['arm']=='ndvi_only'}
if len(prev)!=len(rows):raise RuntimeError('Stage 4 OOF does not match training cohort')
for r in rows:
    if r['sample_id'] not in prev or prev[r['sample_id']]['true_label']!=r['label']:
        raise RuntimeError('Stage 4 predictions do not match frozen labels')
    r['fold_id']=int(prev[r['sample_id']]['fold_id'])
labels_by_country=defaultdict(Counter)
for r in rows:labels_by_country[r['country']][r['label']]+=1
single_label_countries=sorted(c for c,v in labels_by_country.items() if len(v)==1)
skewed_countries=sorted(c for c,v in labels_by_country.items() if max(v.values())/sum(v.values())>=.90)
scenarios={
    'all_countries':lambda r:True,
    'exclude_single_label_countries':lambda r:r['country'] not in single_label_countries,
    'exclude_countries_with_at_least_90pct_one_label':lambda r:r['country'] not in skewed_countries,
}
yall=np.array([int(r['label']=='silage') for r in rows]);Xall=np.array([[np.nan if r[f] is None else float(r[f]) for f in FEATURES] for r in rows],dtype=float)
groups=np.array([r['spatial_group'] for r in rows]);fold_ids=np.array([r['fold_id'] for r in rows]);countries=np.array([r['country'] for r in rows])
if any(len(set(fold_ids[groups==g]))!=1 for g in set(groups)):raise RuntimeError('Group crosses frozen validation folds')

def model():return make_pipeline(SimpleImputer(strategy='median',add_indicator=True,keep_empty_features=True),RandomForestClassifier(**PARAMS))
def metrics(y,p):
    pred=(np.asarray(p)>=.5).astype(int);both=len(set(y))==2
    return dict(n=int(len(y)),correct=int(sum(pred==y)),accuracy=float(accuracy_score(y,pred)),macro_f1=float(f1_score(y,pred,average='macro',labels=[0,1],zero_division=0)),balanced_accuracy=float(balanced_accuracy_score(y,pred)) if both else None,silage_precision=float(precision_score(y,pred,zero_division=0)),silage_recall=float(recall_score(y,pred,zero_division=0)) if 1 in y else None,roc_auc=float(roc_auc_score(y,p)) if both else None,confusion_matrix=confusion_matrix(y,pred,labels=[0,1]).tolist(),class_counts={'grain':int(sum(y==0)),'silage':int(sum(y==1))},majority_class_baseline=float(max(sum(y==0),sum(y==1))/len(y)),has_both_classes=both)
def write(name,obj):(RUN/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

all_indices=np.arange(len(rows));baseline_p=np.array([float(prev[r['sample_id']]['p_silage']) for r in rows])
baseline_all=metrics(yall,baseline_p);reports={};fold_reports=[];prediction_rows=[]
for name,keep_fn in scenarios.items():
    selected=np.array([i for i,r in enumerate(rows) if keep_fn(r)],dtype=int)
    if not len(selected):raise RuntimeError('Empty trimming scenario '+name)
    selected_y=yall[selected];selected_country=countries[selected]
    p_old=baseline_p[selected];p_new=np.full(len(selected),np.nan);where={int(i):j for j,i in enumerate(selected)}
    old_metrics=metrics(selected_y,p_old)
    for fold in sorted(set(fold_ids[selected])):
        test=selected[fold_ids[selected]==fold]
        if not len(test):continue
        train=selected[fold_ids[selected]!=fold]
        if not len(train):raise RuntimeError('Empty train fold '+name)
        if len(set(yall[train]))<2:raise RuntimeError(f'Training fold misses a class: {name}, fold {fold}')
        if set(groups[train])&set(groups[test]):raise RuntimeError('Spatial group leakage '+name)
        m=model();m.fit(Xall[train],yall[train]);p=m.predict_proba(Xall[test])[:,list(m.classes_).index(1)]
        path=RUN/'models'/f'{name}_fold_{fold}.joblib';joblib.dump(dict(model=m,features=FEATURES,threshold=.5,parameters=PARAMS,excluded_countries=sorted(set(countries)-set(selected_country))),path)
        check=joblib.load(path)['model'].predict_proba(Xall[test])[:,list(m.classes_).index(1)];np.testing.assert_allclose(check,p,rtol=0,atol=1e-12)
        for i,v in zip(test,p):p_new[where[int(i)]]=v
        fold_reports.append(dict(scenario=name,fold_id=int(fold),n_train=len(train),n_test=len(test),metrics=metrics(yall[test],p)))
    if not np.isfinite(p_new).all():raise RuntimeError('Missing filtered-cohort OOF: '+name)
    new_metrics=metrics(selected_y,p_new)
    country_metrics={}
    for c in sorted(set(selected_country)):
        loc=np.flatnonzero(selected_country==c)
        country_metrics[c]=dict(previous_all_country_model=metrics(selected_y[loc],p_old[loc]),refit_filtered_model=metrics(selected_y[loc],p_new[loc]))
    reports[name]=dict(n=len(selected),countries=sorted(set(selected_country)),label_counts=dict(Counter(r['label'] for r in (rows[i] for i in selected))),previous_all_country_model_on_same_rows=old_metrics,refit_filtered_model=new_metrics,accuracy_change_pp=100*(new_metrics['accuracy']-old_metrics['accuracy']),country_macro_accuracy_previous=float(np.mean([v['previous_all_country_model']['accuracy'] for v in country_metrics.values()])),country_macro_accuracy_refit=float(np.mean([v['refit_filtered_model']['accuracy'] for v in country_metrics.values()])),by_country=country_metrics,excluded_countries=sorted(set(countries)-set(selected_country)),fold_ids=sorted(set(fold_ids[selected].tolist())))
    for i,v in zip(selected,p_new):
        r=rows[i];prediction_rows.append(dict(scenario=name,sample_id=r['sample_id'],country_for_reporting_only=r['country'],field_id=r['field_id'],year=r['year'],true_label=r['label'],previous_all_country_p_silage=float(baseline_p[i]),filtered_model_p_silage=float(v),fold_id=int(r['fold_id'])))
    full=model();full.fit(Xall[selected],yall[selected]);joblib.dump(dict(model=full,features=FEATURES,threshold=.5,parameters=PARAMS,excluded_countries=reports[name]['excluded_countries']),RUN/'models'/f'{name}_full_model.joblib')
    probe=selected[:min(100,len(selected))];a=full.predict_proba(Xall[probe])[:,list(full.classes_).index(1)];b=joblib.load(RUN/'models'/f'{name}_full_model.joblib')['model'].predict_proba(Xall[probe])[:,list(full.classes_).index(1)];np.testing.assert_allclose(a,b,rtol=0,atol=1e-12)

with (RUN/'oof_predictions.csv').open('w',encoding='utf-8-sig',newline='') as h:
    w=csv.DictWriter(h,fieldnames=list(prediction_rows[0]));w.writeheader();w.writerows(prediction_rows)
write('metrics.json',dict(status='completed',stage=5,full_cohort_rows=len(rows),full_cohort_label_counts=dict(Counter(r['label'] for r in rows)),country_label_distribution={c:dict(v) for c,v in labels_by_country.items()},single_label_countries=single_label_countries,predeclared_extreme_rule='country excluded when one observed label has >=90% share; second sensitivity scenario removes only countries with one observed label',scenarios=reports,full_cohort_stage4_ndvi_only_baseline=baseline_all,parameters=PARAMS,features=FEATURES,threshold=.5,same_rows_for_previous_model_comparison=True,same_frozen_fold_assignment=True,limitations=['only repository subset with NDVI and labels; not worldwide coverage','country used only to define sample-exclusion scenarios and post-hoc summaries, never as model feature or sample weight','same row and fold-matched predictions compare the old all-country OOF model against refits trained on filtered countries','filtered-country test accuracy is conditional on the countries retained; it does not establish generalization to excluded countries','no cutoff or hyperparameter tuning after observing scores']))
write('fold_metrics.json',fold_reports)
write('verification.json',dict(all_source_fold_assignments_reused=True,spatial_groups_stay_in_one_fold=True,previous_oof_row_and_label_keys_match=True,filtered_models_use_only_ndvi_features=True,no_country_feature_or_weights=True,all_filtered_rows_have_oof=True,fold_models_reload_equal=True,full_models_reload_equal=True,threshold_fixed=.5,random_seed_fixed=42,excluded_countries_chosen_by_predeclared_label_composition_rules=True))
write('input_manifest.json',[dict(path=str(SOURCE/'training_rows.parquet'),sha256=hashlib.sha256((SOURCE/'training_rows.parquet').read_bytes()).hexdigest()),dict(path=str(STEP4/'oof_predictions.csv'),sha256=hashlib.sha256((STEP4/'oof_predictions.csv').read_bytes()).hexdigest())])
write('environment.json',dict(hostname=platform.node(),python=platform.python_version(),numpy=np.__version__,sklearn=sklearn.__version__,parameters=PARAMS,execution='NVIDIA Brev CPU; filtered source experiments'))
write('model_checksums.json',{str(p.relative_to(RUN)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (RUN/'models').glob('*.joblib')})
with zipfile.ZipFile(RUN/'trained_models.zip','w',zipfile.ZIP_DEFLATED) as z:
    for p in (RUN/'models').glob('*.joblib'):z.write(p,p.relative_to(RUN))
    for n in ['metrics.json','environment.json','model_checksums.json']:z.write(RUN/n,n)
lines=['# 第五次实验：排除极端标签构成国家','','仅用 NDVI 曲线特征训练，不输入国家、不按国家加权。先根据训练样本标签分布，预先定义两个筛选情景：','',f'- 单一标签国家：{", ".join(single_label_countries)}。','- 极端偏斜国家：某国90%或以上记录属于同一收获标签；本批数据中为'+', '.join(skewed_countries)+'。','', '沿用第四次实验已冻结的随机分折，同一田块/农场组仍只在一个折中。每个筛选情景都和第四步原模型在完全相同的保留田块、同一测试折上比较；训练参数、种子42和0.5阈值不变。', '', '## 结果', '', '|筛选情景|保留国家|记录数|旧全数据模型在保留行|筛后重训模型|准确率差|', '|---|---|---:|---:|---:|---:|']
for name,v in reports.items():lines.append(f'|{name}|{", ".join(v["countries"])}|{v["n"]}|{v["previous_all_country_model_on_same_rows"]["accuracy"]:.2%}|{v["refit_filtered_model"]["accuracy"]:.2%}|{v["accuracy_change_pp"]:+.2f}个百分点|')
lines+=['','这些结果只评价保留国家中的样本。剔除某国后得到的准确率不能说明模型能预测那个被剔除的国家；加拿大单一籽粒标签尤其无法检验青贮识别。不要只根据总体准确率选模型；同时查看宏F1、青贮召回和每国分项。', '', '没有在看到分数后更改极端阈值、数据行、参数或折分。完整模型与逐行预测保存在 NVIDIA 本次运行目录。']
(RUN/'README.md').write_text('\n'.join(lines)+'\n')
(ROOT/'latest_step5_trim.txt').write_text(str(RUN))
print(json.dumps(dict(run=str(RUN),single_label_countries=single_label_countries,skewed_countries=skewed_countries,scenarios=reports),ensure_ascii=False,indent=2))
