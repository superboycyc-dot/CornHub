"""Brev-only paired experiment: frozen Maryland NDVI baseline + nearest dairy distance."""
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tarfile
import tempfile
import zipfile

import joblib
import numpy as np
import sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, balanced_accuracy_score, brier_score_loss, confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.pipeline import make_pipeline

ROOT=Path(__file__).resolve().parent
RUN=ROOT/'runs'/('step2-ndvi-distance-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
RUN.mkdir(parents=True)
INPUT=RUN/'inputs';INPUT.mkdir()
BASE_DIR='reports/training/step1_ndvi_maryland'
DIST_DIR='data/processed/maryland_field_dairy_distances'
NDVI=['ndvi_peak','peak_doy','max_drop_per_day','drop_doy','ndvi_late_mean']
DISTANCE='nearest_dairy_distance_km'
FEATURES=[*NDVI,DISTANCE]
PARAMETERS=dict(n_estimators=100,max_depth=4,min_samples_leaf=2,class_weight='balanced',random_state=42,n_jobs=1)
env=dict(os.environ)
env['GIT_SSH_COMMAND']=f'ssh -i {ROOT}/keys/github_readonly -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile={ROOT}/keys/known_hosts'
cache=ROOT/'repository.git'
def git(*args,capture=False):
    return subprocess.run(['git','--git-dir',str(cache),*args],env=env,check=True,stdout=subprocess.PIPE if capture else None).stdout
def write_json(name,value):
    (RUN/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def read_csv(path):
    with path.open(encoding='utf-8-sig',newline='') as h:return list(csv.DictReader(h))
def write_csv(name,rows):
    with (RUN/name).open('w',encoding='utf-8-sig',newline='') as h:
        writer=csv.DictWriter(h,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
def key(row):return (row['field_id'],row['year'])

# Download only the committed step-1 report and Maryland distance artifacts.
git('fetch','--depth=1','origin','+refs/heads/main:refs/remotes/origin/main')
commit=git('rev-parse','refs/remotes/origin/main',capture=True).decode().strip()
with tempfile.TemporaryFile() as h:
    subprocess.run(['git','--git-dir',str(cache),'archive',commit,'--',BASE_DIR,DIST_DIR],env=env,stdout=h,check=True)
    h.seek(0)
    with tarfile.open(fileobj=h) as archive:archive.extractall(INPUT,filter='data')
manifest=[dict(path=str(p.relative_to(INPUT)),commit=commit,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(INPUT.rglob('*')) if p.is_file()]
write_json('input_manifest.json',manifest)
shutil.copyfile(__file__,RUN/'train_step2.py')
base=INPUT/BASE_DIR;dist=INPUT/DIST_DIR
baseline=json.loads((base/'metrics.json').read_text())
baseline_env=json.loads((base/'environment.json').read_text())
if baseline['features']!=NDVI or baseline_env['parameters']!=PARAMETERS:raise RuntimeError('Baseline protocol differs')
if baseline_env['sklearn']!=sklearn.__version__ or baseline_env['numpy']!=np.__version__:raise RuntimeError('Library versions changed; baseline reproduction must be reviewed')
rows=read_csv(base/'frozen_training_rows.csv')
baseline_oof=read_csv(base/'oof_predictions.csv')
baseline_by_key={key(r):r for r in baseline_oof}
all_distances=read_csv(dist/'field_year_farm_distances.csv')
nearest_saved={key(r):r for r in read_csv(dist/'nearest_dairy_by_field_year.csv')}
farm_index=read_csv(dist/'dairy_locations.csv')
if len(rows)!=44 or len({key(r) for r in rows})!=44 or len({r['field_id'] for r in rows})!=34:raise RuntimeError('Wrong official Maryland cohort')
if set(baseline_by_key)!={key(r) for r in rows} or set(nearest_saved)!=set(baseline_by_key):raise RuntimeError('Unmatched sample keys')
if len(farm_index)!=67 or any(f['state']!='MD' for f in farm_index):raise RuntimeError('Dairy locations are not the frozen Maryland set')
farms={r['farm_id']:r for r in farm_index}
if len(farms)!=67:raise RuntimeError('Duplicate dairy location IDs')
grouped={k:[] for k in baseline_by_key}
for r in all_distances:
    if key(r) not in grouped or r['farm_id'] not in farms:raise RuntimeError('Unexpected distance row')
    value=float(r['distance_km'])
    if not np.isfinite(value) or value<0:raise RuntimeError('Invalid distance')
    grouped[key(r)].append(r)
for k,values in grouped.items():
    if len(values)!=67 or len({r['farm_id'] for r in values})!=67:raise RuntimeError('Incomplete per-field dairy distances')
    closest=min(values,key=lambda r:(float(r['distance_km']),r['farm_id']))
    if abs(float(closest['distance_km'])-float(nearest_saved[k]['distance_km']))>1e-6:raise RuntimeError('Nearest-distance mismatch')
    nearest_saved[k]['distance_km']=closest['distance_km']
    nearest_saved[k]['farm_id']=closest['farm_id']

distance_rows=[]
for r in rows:
    b=baseline_by_key[key(r)]
    if r['label']!=b['true_label'] or r['fold_id']!=b['fold_id'] or r['farm_group']!=b['farm_group']:raise RuntimeError('Baseline labels/splits changed')
    nearest=nearest_saved[key(r)]
    r[DISTANCE]=float(nearest['distance_km'])
    farm=farms[nearest['farm_id']]
    distance_rows.append(dict(field_id=r['field_id'],year=r['year'],nearest_farm_id=farm['farm_id'],nearest_farm_name=farm['farm_name'],nearest_distance_km=r[DISTANCE],location_precision=farm['location_precision']))
write_csv('distance_features.csv',distance_rows)
write_csv('frozen_training_rows.csv',rows)
X=np.array([[np.nan if r[n] in ('',None) else float(r[n]) for n in FEATURES] for r in rows])
y=np.array([int(r['label']=='silage') for r in rows])
folds=np.array([r['fold_id'] for r in rows]);field_ids=np.array([r['field_id'] for r in rows]);farm_groups=np.array([r['farm_group'] for r in rows])
if len(set(folds))!=5:raise RuntimeError('Expected same five folds')
for ids in [field_ids,farm_groups]:
    for identity in set(ids):
        if len(set(folds[ids==identity]))!=1:raise RuntimeError('Field/farm leakage across folds')
for fid in set(field_ids):
    if len(set(X[field_ids==fid,-1]))!=1:raise RuntimeError('Distance changed across years for same field')

def score(truth,probs):
    pred=(np.asarray(probs)>=.5).astype(int)
    return dict(n=len(truth),accuracy=float(accuracy_score(truth,pred)),correct=int(sum(pred==truth)),balanced_accuracy=float(balanced_accuracy_score(truth,pred)) if len(set(truth))==2 else None,macro_f1=float(f1_score(truth,pred,labels=[0,1],average='macro',zero_division=0)) if len(set(truth))==2 else None,silage_precision=float(precision_score(truth,pred,zero_division=0)),silage_recall=float(recall_score(truth,pred,zero_division=0)) if 1 in truth else None,brier_score=float(brier_score_loss(truth,probs)),roc_auc=float(roc_auc_score(truth,probs)) if len(set(truth))==2 else None,confusion_matrix=confusion_matrix(truth,pred,labels=[0,1]).tolist(),confusion_order=['grain','silage'])

baseline_prob=np.array([float(baseline_by_key[key(r)]['p_silage']) for r in rows])
with zipfile.ZipFile(base/'trained_models.zip') as archive:
    for fold in sorted(set(folds)):
        indices=np.flatnonzero(folds==fold)
        model=joblib.load(io.BytesIO(archive.read(f'models/fold_{fold}.joblib')))
        check=model.predict_proba(X[indices,:5])[:,list(model.classes_).index(1)]
        np.testing.assert_allclose(check,baseline_prob[indices],rtol=0,atol=1e-15)
baseline_recomputed=score(y,baseline_prob)
if baseline_recomputed['accuracy']!=baseline['accuracy'] or baseline_recomputed['confusion_matrix']!=baseline['confusion_matrix']:raise RuntimeError('Baseline metrics do not reproduce')

prob=np.full(len(rows),np.nan);reports=[]
models=RUN/'models';models.mkdir()
for fold in sorted(set(folds)):
    train=np.flatnonzero(folds!=fold);test=np.flatnonzero(folds==fold)
    assert not set(field_ids[train])&set(field_ids[test])
    assert not set(farm_groups[train])&set(farm_groups[test])
    if len(set(y[train]))!=2:raise RuntimeError('Training fold lacks a class')
    model=make_pipeline(SimpleImputer(strategy='median',keep_empty_features=True),RandomForestClassifier(**PARAMETERS))
    model.fit(X[train],y[train]);prob[test]=model.predict_proba(X[test])[:,list(model.classes_).index(1)]
    path=models/f'fold_{fold}.joblib';joblib.dump(model,path)
    np.testing.assert_allclose(joblib.load(path).predict_proba(X[test])[:,list(model.classes_).index(1)],prob[test],rtol=0,atol=0)
    reports.append(dict(fold_id=fold,n_train=len(train),n_test=len(test),train_class_counts=np.bincount(y[train],minlength=2).tolist(),test_class_counts=np.bincount(y[test],minlength=2).tolist(),step1=score(y[test],baseline_prob[test]),step2=score(y[test],prob[test]),test_farm_groups=sorted(set(farm_groups[test])),imputer_statistics=model.named_steps['simpleimputer'].statistics_.tolist()))
    print(f'Fold {fold}: step1 {sum((baseline_prob[test]>=.5)==y[test])}/{len(test)}, step2 {sum((prob[test]>=.5)==y[test])}/{len(test)}',flush=True)
if not np.isfinite(prob).all():raise RuntimeError('Incomplete OOF evaluation')
pred=(prob>=.5).astype(int);old=(baseline_prob>=.5).astype(int)
paired=[]
for i,r in enumerate(rows):
    paired.append(dict(field_id=r['field_id'],year=r['year'],fold_id=r['fold_id'],farm_group=r['farm_group'],true_label=r['label'],step1_label='silage' if old[i] else 'grain',step2_label='silage' if pred[i] else 'grain',step1_p_silage=float(baseline_prob[i]),step2_p_silage=float(prob[i]),step1_correct=bool(old[i]==y[i]),step2_correct=bool(pred[i]==y[i]),nearest_dairy_distance_km=float(X[i,-1]),quality_flag=r['quality_flag'],prediction_role='oof'))
write_csv('paired_oof_predictions.csv',paired)
write_csv('oof_predictions.csv',[dict(field_id=r['field_id'],year=r['year'],fold_id=r['fold_id'],true_label=r['true_label'],predicted_label=r['step2_label'],p_silage=r['step2_p_silage'],correct=r['step2_correct'],prediction_role='oof') for r in paired])
full=make_pipeline(SimpleImputer(strategy='median',keep_empty_features=True),RandomForestClassifier(**PARAMETERS));full.fit(X,y)
joblib.dump(dict(model=full,features=FEATURES,threshold=.5,class_mapping={0:'grain',1:'silage'},parameters=PARAMETERS),models/'ndvi_distance_full_model.joblib')
np.testing.assert_allclose(joblib.load(models/'ndvi_distance_full_model.joblib')['model'].predict_proba(X),full.predict_proba(X),rtol=0,atol=0)
write_csv('feature_importance.csv',[dict(feature=f,importance=float(v)) for f,v in zip(FEATURES,full.named_steps['randomforestclassifier'].feature_importances_)])
metrics=score(y,prob)
metrics.update(status='trained_and_evaluated',stage=2,region='Maryland BARC only',sample_count=44,unique_fields=34,class_counts={'grain':int(sum(y==0)),'silage':int(sum(y==1))},features=FEATURES,threshold=.5,evaluation='same frozen five-fold leave-one-farm-out OOF as step 1',probabilities_calibrated=False,by_year={str(year):score(y[[r['year']==year for r in rows]],prob[[r['year']==year for r in rows]]) for year in sorted({r['year'] for r in rows})})
delta=100*(metrics['accuracy']-baseline['accuracy'])
comparison=dict(step1=baseline_recomputed,step2=score(y,prob),accuracy_change_pp=delta,macro_f1_change=metrics['macro_f1']-baseline['macro_f1'],silage_recall_change_pp=100*(metrics['silage_recall']-baseline['silage_recall']),outcome='improved' if delta>0 else 'degraded' if delta<0 else 'unchanged',step1_wrong_now_correct=int(sum((old!=y)&(pred==y))),step1_correct_now_wrong=int(sum((old==y)&(pred!=y))),same_cohort=True,same_folds=True,same_parameters=True,same_seed=True,feature_selection='Predeclared single added feature: nearest dairy location distance in km; no validation-driven search',no_statistical_significance_claim='44 repeated field-year observations in five farms; changes are descriptive')
write_json('metrics.json',metrics);write_json('comparison.json',comparison);write_json('fold_metrics.json',reports)
write_json('environment.json',dict(hostname=platform.node(),python=platform.python_version(),numpy=np.__version__,sklearn=sklearn.__version__,joblib=joblib.__version__,parameters=PARAMETERS,input_commit=commit,execution='NVIDIA Brev host CPU; sklearn random forest'))
write_json('verification.json',dict(baseline_saved_models_reproduce_all_44_predictions=True,baseline_accuracy_and_confusion_reproduced=True,exactly_44_matching_sample_keys=True,all_2948_distance_pairs_checked=True,nearest_distances_recomputed=True,only_one_added_distance_feature=True,no_field_or_farm_leakage=True,fold_models_reload_equal=True,full_model_reload_equal=True,no_heldout_imputation_statistics=True,no_overseas_or_national_candidate_rows=True))
write_json('model_checksums.json',{str(p.relative_to(RUN)):hashlib.sha256(p.read_bytes()).hexdigest() for p in models.glob('*.joblib')})
(RUN/'requirements.lock.txt').write_text(subprocess.check_output([str(ROOT/'venv/bin/python'),'-m','pip','freeze'],text=True))
limits=['Small cohort: 44 field-years, 34 fields, five farms; exploratory validation','Dairy location list assembled in 2026; operating/location status during 2021-2023 not independently verified','Distances are straight-line geodesic distances to approximate address points, not driving distance or confirmed silage relationships','Some dairy locations are retail/associated or low-precision reference addresses','No hyperparameter or distance-feature search; no guarantee accuracy improves','Distance may proxy geography; result does not establish causal feed supply relationships','Stage 3 not run']
write_json('limitations.json',limits)
note=f'''# 第二步：马里兰 NDVI + 最近奶牛场距离\n\n仅在NVIDIA Brev运行；输入从GitHub提交 `{commit}` 下载。保留第一步44条官方田块年度记录（34块田）、五折按农场留出划分和随机森林参数。没有加入海外、全国候选田、牛数、面积或ID作为预测变量。\n\n在原5个NDVI衍生特征之外，仅新增 `nearest_dairy_distance_km`，为67个马里兰奶牛场地点中最近一个的WGS84椭球直线距离。这个定义在训练前确定，不根据测试结果搜索。逐田从2948条距离中重新取最小值，并核对所有年度键；同一田跨年距离相同。缺失值仍仅用训练折中位数填补。\n\n|指标|第一步 NDVI|第二步 NDVI+距离|\n|---|---:|---:|\n|准确率|{baseline['accuracy']:.2%} ({baseline_recomputed['correct']}/44)|{metrics['accuracy']:.2%} ({metrics['correct']}/44)|\n|宏平均F1|{baseline['macro_f1']:.4f}|{metrics['macro_f1']:.4f}|\n|青贮召回率|{baseline['silage_recall']:.2%}|{metrics['silage_recall']:.2%}|\n\n准确率变化为 **{delta:+.2f}个百分点**，实际结论 `{comparison['outcome']}`。原来错误现在正确{comparison['step1_wrong_now_correct']}条；原来正确现在错误{comparison['step1_correct_now_wrong']}条。对照结果来自相同44条OOF预测，不使用训练内准确率，也没有反复挑选距离定义。\n\n奶牛场位置资料于2026年整理，未逐场核实2021–2023年的历史位置和在营状态，所以只能作为当前地理代理的探索性比较，不能声称严格历史实时预测。位置近不等于实际饲料供需关系，地址点与田内代表点也不等于牛舍和农田出入口。样本小，概率未校准，不作统计显著性或全球表现承诺。\n\n逐田变化见 `paired_oof_predictions.csv`，全部指标见 `comparison.json`、`metrics.json`，折结果见 `fold_metrics.json`。模型保存在 `models/`，交付压缩包为 `trained_models.zip`。训练代码为 `train_step2.py`：放在 `/home/ubuntu/cornhub-compute/`，用该目录 `venv/bin/python train_step2.py` 执行。现有控制器命令为 `python3 outputs/brev/remote.py train-step2`。源码、输入哈希和环境版本均已记录。第三步未运行。\n'''
(RUN/'README.md').write_text(note)
with zipfile.ZipFile(RUN/'trained_models.zip','w',zipfile.ZIP_DEFLATED) as archive:
    for p in sorted(models.glob('*.joblib')):archive.write(p,p.relative_to(RUN))
    for name in ['environment.json','metrics.json','model_checksums.json']:archive.write(RUN/name,name)
(ROOT/'latest_step2.txt').write_text(str(RUN))
print(json.dumps(comparison,ensure_ascii=False,indent=2));print('Results:',RUN)
