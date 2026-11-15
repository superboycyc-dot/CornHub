"""Stage 4: paired group-randomized models, with country hidden from fitting."""
import csv,hashlib,json,platform,zipfile
from datetime import datetime,timezone
from pathlib import Path

import joblib,numpy as np,pyarrow.parquet as pq,sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score,balanced_accuracy_score,confusion_matrix,f1_score,precision_score,recall_score,roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline

ROOT=Path(__file__).resolve().parent
SOURCE=Path((ROOT/'latest_step3.txt').read_text().strip())
RUN=ROOT/'runs'/('step4-blind-ndvi-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
RUN.mkdir(parents=True);(RUN/'models').mkdir()
NDVI=['ndvi_peak','peak_doy','max_drop_per_day','drop_doy','ndvi_late_mean']
ARMS={'ndvi_only':NDVI,'ndvi_plus_distance':NDVI+['nearest_dairy_distance_km']}
PARAMS=dict(n_estimators=100,max_depth=4,min_samples_leaf=2,max_features=1.0,class_weight='balanced',random_state=42,n_jobs=4)
TABLE=pq.read_table(SOURCE/'training_rows.parquet',columns=['sample_id','country','field_id','year','label','spatial_group',*ARMS['ndvi_plus_distance']])
rows=TABLE.to_pylist()
if not rows or any(r['label'] not in ('grain','silage') for r in rows):raise RuntimeError('Training table has invalid labels')
if any(all(r[f] is None for f in NDVI) for r in rows):raise RuntimeError('All-null NDVI row must abstain, not enter training')
y=np.array([int(r['label']=='silage') for r in rows],dtype=int)
X={arm:np.array([[np.nan if r[f] is None else float(r[f]) for f in fs] for r in rows],dtype=float) for arm,fs in ARMS.items()}
groups=np.array([r['spatial_group'] for r in rows],dtype=str)
countries=np.array([r['country'] for r in rows],dtype=str)
if len(set(groups))<5:raise RuntimeError('Need at least five independent spatial/farm groups')

def model():return make_pipeline(SimpleImputer(strategy='median',add_indicator=True,keep_empty_features=True),RandomForestClassifier(**PARAMS))
def metrics(indices,p):
    truth=y[indices];pred=(np.asarray(p)>=.5).astype(int);both=len(set(truth))==2
    return dict(n=int(len(indices)),correct=int(sum(pred==truth)),accuracy=float(accuracy_score(truth,pred)),macro_f1=float(f1_score(truth,pred,average='macro',labels=[0,1],zero_division=0)),balanced_accuracy=float(balanced_accuracy_score(truth,pred)) if both else None,silage_precision=float(precision_score(truth,pred,zero_division=0)),silage_recall=float(recall_score(truth,pred,zero_division=0)) if 1 in truth else None,roc_auc=float(roc_auc_score(truth,p)) if both else None,confusion_matrix=confusion_matrix(truth,pred,labels=[0,1]).tolist(),class_counts={'grain':int(sum(truth==0)),'silage':int(sum(truth==1))},majority_class_baseline=float(max(sum(truth==0),sum(truth==1))/len(truth)),has_both_classes=both)
def write(name,value):(RUN/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

splitter=GroupKFold(n_splits=5,shuffle=True,random_state=42)
oof={arm:np.full(len(rows),np.nan) for arm in ARMS};folds=[];predictions=[]
for fold,(train,test) in enumerate(splitter.split(X['ndvi_only'],y,groups),start=0):
    if set(groups[train])&set(groups[test]):raise RuntimeError('Spatial group leakage')
    for arm,features in ARMS.items():
        m=model();m.fit(X[arm][train],y[train]);p=m.predict_proba(X[arm][test])[:,list(m.classes_).index(1)];oof[arm][test]=p
        path=RUN/'models'/f'{arm}_group_fold_{fold}.joblib';joblib.dump(dict(model=m,features=features,threshold=.5,country_used_for_prediction=False),path)
        check=joblib.load(path)['model'].predict_proba(X[arm][test])[:,list(m.classes_).index(1)]
        np.testing.assert_allclose(check,p,rtol=0,atol=1e-12)
        folds.append(dict(arm=arm,fold_id=fold,n_train=len(train),n_test=len(test),n_test_groups=len(set(groups[test])),metrics=metrics(test,p)))
        for i,value in zip(test,p):
            r=rows[i];predictions.append(dict(sample_id=r['sample_id'],arm=arm,country_for_reporting_only=r['country'],field_id=r['field_id'],year=r['year'],true_label=r['label'],p_silage=float(value),predicted_label='silage' if value>=.5 else 'grain',fold_id=fold))
if any(not np.isfinite(p).all() for p in oof.values()):raise RuntimeError('Incomplete out-of-fold predictions')
all_idx=np.arange(len(rows));overall={arm:metrics(all_idx,p) for arm,p in oof.items()}
by_country={}
for c in sorted(set(countries)):
    ix=np.flatnonzero(countries==c);by_country[c]={arm:metrics(ix,p[ix]) for arm,p in oof.items()}
macro={arm:float(np.mean([v[arm]['accuracy'] for v in by_country.values()])) for arm in ARMS}
for arm,features in ARMS.items():
    full=model();full.fit(X[arm],y);path=RUN/'models'/f'{arm}_full_model.joblib';joblib.dump(dict(model=full,features=features,threshold=.5,parameters=PARAMS,country_used_for_prediction=False),path)
    probe=np.arange(min(100,len(rows)));pr=full.predict_proba(X[arm][probe])[:,list(full.classes_).index(1)];pr2=joblib.load(path)['model'].predict_proba(X[arm][probe])[:,list(full.classes_).index(1)]
    np.testing.assert_allclose(pr,pr2,rtol=0,atol=1e-12)
with (RUN/'oof_predictions.csv').open('w',encoding='utf-8-sig',newline='') as h:
    w=csv.DictWriter(h,fieldnames=list(predictions[0]));w.writeheader();w.writerows(predictions)
write('fold_metrics.json',folds)
distance_gain=100*(overall['ndvi_plus_distance']['accuracy']-overall['ndvi_only']['accuracy'])
summary=dict(status='completed',stage=4,cohort_rows=len(rows),countries_for_posthoc_reporting=sorted(set(countries)),feature_arms=ARMS,parameters=PARAMS,threshold=.5,overall_group_random_oof=overall,by_country=by_country,country_macro_accuracy=macro,distance_gain_pp=distance_gain,paired_same_rows_folds_parameters=True,country_used_for_training_features_or_weights=False,previous_stage3_comparison='descriptive only; stage 3 used country-class weights and a different split',limitations=['repository subset, not worldwide ground truth','Canadian rows are grain-only','country is retained only for reporting and group integrity checks; no country/region/source feature or country-based sample weight is used for fitting','field/farm/spatial groups are held out','NDVI-only and NDVI-plus-distance arms use exact same rows, group folds, parameters and threshold','historical Maryland rows have been repeatedly used in development; this is not an independent blind test'])
write('metrics.json',summary)
write('verification.json',dict(country_not_in_features=True,country_not_used_for_weights=True,ndvi_only_arm_has_only_five_curve_features=True,distance_only_in_paired_control=True,group_disjoint=True,all_rows_have_oof=True,fold_models_reload_equal=True,full_models_reload_equal=True,all_null_ndvi_rows_excluded_for_abstention=True,threshold_fixed=.5,seed=42,paired_arms_same_rows_folds_parameters=True))
write('input_manifest.json',[dict(path=str(SOURCE/'training_rows.parquet'),sha256=hashlib.sha256((SOURCE/'training_rows.parquet').read_bytes()).hexdigest()),dict(path=str(SOURCE/'input_manifest.json'),sha256=hashlib.sha256((SOURCE/'input_manifest.json').read_bytes()).hexdigest())])
write('environment.json',dict(hostname=platform.node(),python=platform.python_version(),numpy=np.__version__,sklearn=sklearn.__version__,parameters=PARAMS,execution='NVIDIA Brev CPU; country-blind paired models'))
write('model_checksums.json',{str(p.relative_to(RUN)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (RUN/'models').glob('*.joblib')})
with zipfile.ZipFile(RUN/'trained_models.zip','w',zipfile.ZIP_DEFLATED) as z:
    for p in (RUN/'models').glob('*.joblib'):z.write(p,p.relative_to(RUN))
    for n in ['metrics.json','environment.json','model_checksums.json']:z.write(RUN/n,n)
summary_lines=['# 第四次实验：隐藏国家的 NDVI-only 配对对照','','主实验模型只看5个历史 NDVI 曲线指标：峰值、峰值日期、最大下降速度、下降日期、9月后均值。标签是籽粒/青贮。国家、地区、数据来源和奶牛场距离均不提供给主模型；训练不按国家加权。','','为了检验去掉距离是否有帮助，另跑一个只多出最近奶牛场距离的配对对照。两个模型使用完全相同的田块、5折随机分组、随机种子42、随机森林参数和阈值0.5；所以这组差值只对应距离特征。分折按空间/农场组进行，同一组不会同时落入训练和验证。国家只用于完成预测后的成绩分表。','','## 同一分折上的验证结果','','|输入|记录数|正确|准确率|宏平均F1|青贮召回率|','|---|---:|---:|---:|---:|---:|']
for arm,m in overall.items():summary_lines.append(f'|{arm}|{m["n"]}|{m["correct"]}|{m["accuracy"]:.2%}|{m["macro_f1"]:.4f}|{m["silage_recall"]:.2%}|')
summary_lines+=['',f'距离特征相对 NDVI-only 的准确率差：{distance_gain:+.2f} 个百分点。国家等权准确率：NDVI-only {macro["ndvi_only"]:.2%}，NDVI+距离 {macro["ndvi_plus_distance"]:.2%}。','', '## 按国家汇总（仅用于检查迁移表现）','', '|国家|记录数|NDVI-only准确率|NDVI+距离准确率|NDVI-only青贮召回|','|---|---:|---:|---:|---:|']
for c,v in by_country.items():summary_lines.append(f'|{c}|{v["ndvi_only"]["n"]}|{v["ndvi_only"]["accuracy"]:.2%}|{v["ndvi_plus_distance"]["accuracy"]:.2%}|{(v["ndvi_only"]["silage_recall"] or 0):.2%}|')
summary_lines+=['','跨国家合并准确率受加拿大39,653条全为籽粒的记录主导，全部猜籽粒本身已有较高基线；因此重点看宏平均F1、青贮召回和分国家成绩。加拿大只有籽粒标签，不能测其青贮识别。','', '与第三步整体结果不作严格增减比较：第三步按国家和类别加权，使用不同分折。这次两个实验臂之间是严格配对比较。历史马里兰数据已反复用于开发，不是独立盲测。', '', '模型、分折预测、协议和哈希保存在 NVIDIA 本次运行目录；Git报告会保存代码、指标和逐田 OOF 预测。']
(RUN/'README.md').write_text('\n'.join(summary_lines)+'\n')
(ROOT/'latest_step4_blind.txt').write_text(str(RUN))
print(json.dumps(dict(overall=overall,country_macro_accuracy=macro,by_country=by_country,distance_gain_pp=distance_gain,run=str(RUN)),ensure_ascii=False,indent=2))
