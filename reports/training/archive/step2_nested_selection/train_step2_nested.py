"""One predeclared nested model-selection rerun, entirely on NVIDIA Brev."""
import concurrent.futures
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess
import zipfile

import joblib
import numpy as np
import sklearn
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, brier_score_loss, confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT=Path(__file__).resolve().parent
SOURCE=Path((ROOT/'latest_step2.txt').read_text().strip()).resolve()
RUN=ROOT/'runs'/('step2-nested-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
RUN.mkdir(parents=True);(RUN/'models').mkdir()
NDVI=['ndvi_peak','peak_doy','max_drop_per_day','drop_doy','ndvi_late_mean']
THRESHOLDS=[.25,.35,.45,.5,.55,.65,.75]
CONFIGS=[]
for depth in [2,4,None]:
    for leaf in [1,2]:CONFIGS.append(dict(family='random_forest',max_depth=depth,min_samples_leaf=leaf))
for depth in [4,None]:
    for leaf in [1,2]:CONFIGS.append(dict(family='extra_trees',max_depth=depth,min_samples_leaf=leaf))
for C in [.1,1.,10.]:CONFIGS.append(dict(family='logistic',C=C))
SETS={
    'ndvi_only':NDVI,
    'nearest':[ *NDVI,'nearest_dairy_distance_km'],
    'distance_summary':[*NDVI,'nearest_dairy_distance_km','nearest3_mean_km','nearest5_mean_km','inverse_distance_exposure'],
}

def read(path):
    with path.open(encoding='utf-8-sig',newline='') as h:return list(csv.DictReader(h))
def write_json(name,value):
    (RUN/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def write_csv(name,rows):
    with (RUN/name).open('w',encoding='utf-8-sig',newline='') as h:
        w=csv.DictWriter(h,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def key(r):return(r['field_id'],r['year'])

rows=read(SOURCE/'frozen_training_rows.csv')
previous=read(SOURCE/'paired_oof_predictions.csv')
distances=read(SOURCE/'inputs/data/processed/maryland_field_dairy_distances/field_year_farm_distances.csv')
if len(rows)!=44 or len({key(r) for r in rows})!=44:raise RuntimeError('Unexpected Maryland cohort')
bykey={key(r):r for r in previous}
groups={key(r):[] for r in rows}
for r in distances:
    if key(r) not in groups:raise RuntimeError('Unknown distance key')
    d=float(r['distance_km'])
    if not np.isfinite(d) or d<0:raise RuntimeError('Invalid distance')
    groups[key(r)].append(d)
for r in rows:
    old=bykey[key(r)]
    if old['true_label']!=r['label'] or old['fold_id']!=r['fold_id'] or old['farm_group']!=r['farm_group']:raise RuntimeError('Changed frozen label or split')
    d=np.sort(groups[key(r)])
    if len(d)!=67:raise RuntimeError('Missing dairy distances')
    if abs(float(r['nearest_dairy_distance_km'])-d[0])>1e-6:raise RuntimeError('Nearest distance changed')
    r['nearest3_mean_km']=float(np.mean(d[:3]));r['nearest5_mean_km']=float(np.mean(d[:5]));r['inverse_distance_exposure']=float(np.sum(1/(1+d)))
features=SETS['distance_summary']
X=np.array([[float(r[n]) if r[n] not in ('',None) else np.nan for n in features] for r in rows])
y=np.array([int(r['label']=='silage') for r in rows]);folds=np.array([r['fold_id'] for r in rows]);farms=np.array([r['farm_group'] for r in rows]);fields=np.array([r['field_id'] for r in rows])
for ids in [farms,fields]:
    for group in set(ids):
        if len(set(folds[ids==group]))!=1:raise RuntimeError('Farm/field crosses outer folds')
write_csv('frozen_training_rows.csv',rows)
manifest=[]
for name in ['frozen_training_rows.csv','paired_oof_predictions.csv','input_manifest.json','metrics.json','comparison.json','inputs/data/processed/maryland_field_dairy_distances/field_year_farm_distances.csv']:
    p=SOURCE/name;manifest.append(dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
write_json('input_manifest.json',manifest)
shutil.copyfile(__file__,RUN/'train_step2_nested.py')
protocol=dict(seed=42,outer_validation='unchanged five-fold leave-one-farm-out',inner_validation='leave-one-farm-out within outer training only',candidate_configs=CONFIGS,feature_sets=SETS,thresholds=THRESHOLDS,selection='maximize pooled inner OOF accuracy, then macro F1, then threshold proximity to 0.5, then smaller feature set, then configuration order',single_class_inner_training='explicit constant-class dummy fallback, recorded; never train on outer test labels',arms={'ndvi_control':['ndvi_only'],'ndvi_distance':['nearest','distance_summary']},distance_definition={'nearest':'minimum over 67 dairy locations','nearest3_mean_km':'mean of three smallest distances','nearest5_mean_km':'mean of five smallest distances','inverse_distance_exposure':'sum over 67 of 1/(1+distance_km)'},distance_variants_predeclared_before_training=True,no_outer_score_selection=True,development_caveat='Outer results were viewed during prior experiments; this is a development-set rerun, not a new independent blind test.',no_overseas=True)
write_json('protocol.json',protocol)

def build(config):
    if config['family']=='logistic':
        return make_pipeline(SimpleImputer(strategy='median',keep_empty_features=True),StandardScaler(),LogisticRegression(C=config['C'],class_weight='balanced',max_iter=2000,random_state=42))
    cls=RandomForestClassifier if config['family']=='random_forest' else ExtraTreesClassifier
    return make_pipeline(SimpleImputer(strategy='median',keep_empty_features=True),cls(n_estimators=100,max_depth=config['max_depth'],min_samples_leaf=config['min_samples_leaf'],class_weight='balanced',random_state=42,n_jobs=1))
def probability(model,values):
    p=model.predict_proba(values)
    return p[:,list(model.classes_).index(1)] if 1 in model.classes_ else np.zeros(len(values))
def score(truth,p,threshold=.5):
    pred=(np.asarray(p)>=np.asarray(threshold)).astype(int)
    return dict(n=len(truth),correct=int(sum(pred==truth)),accuracy=float(accuracy_score(truth,pred)),balanced_accuracy=float(balanced_accuracy_score(truth,pred)) if len(set(truth))==2 else None,macro_f1=float(f1_score(truth,pred,labels=[0,1],average='macro',zero_division=0)),silage_precision=float(precision_score(truth,pred,zero_division=0)),silage_recall=float(recall_score(truth,pred,zero_division=0)) if 1 in truth else None,brier_score=float(brier_score_loss(truth,p)),roc_auc=float(roc_auc_score(truth,p)) if len(set(truth))==2 else None,confusion_matrix=confusion_matrix(truth,pred,labels=[0,1]).tolist(),confusion_order=['grain','silage'])
def columns(feature_set):return [features.index(n) for n in SETS[feature_set]]

history=[]
def evaluate_candidate(task):
    train,inner_splits,feature_set,config_id=task
    config=CONFIGS[config_id];cols=columns(feature_set);p=np.full(len(train),np.nan);fallbacks=0
    for inner_train,inner_test in inner_splits:
        ti=train[inner_train];vi=train[inner_test]
        assert not set(farms[ti])&set(farms[vi]);assert not set(fields[ti])&set(fields[vi])
        if len(set(y[ti]))<2:
            model=make_pipeline(SimpleImputer(strategy='median',keep_empty_features=True),DummyClassifier(strategy='most_frequent'));fallbacks+=1
        else:model=build(config)
        model.fit(X[np.ix_(ti,cols)],y[ti]);p[inner_test]=probability(model,X[np.ix_(vi,cols)])
    if not np.isfinite(p).all():raise RuntimeError('Incomplete inner predictions')
    choices=[]
    for threshold in THRESHOLDS:
        pred=(p>=threshold).astype(int);correct=int(sum(pred==y[train]));f1=float(f1_score(y[train],pred,labels=[0,1],average='macro',zero_division=0))
        choices.append(((correct,f1,-abs(threshold-.5)),threshold))
    best,threshold=max(choices,key=lambda x:x[0])
    return dict(feature_set=feature_set,config_id=config_id,threshold=threshold,inner_correct=best[0],inner_n=len(train),inner_accuracy=best[0]/len(train),inner_macro_f1=best[1],single_class_inner_fallbacks=fallbacks)

def select(train,allowed_sets,outer_fold,arm):
    inner=[]
    for farm in sorted(set(farms[train])):
        ti=np.flatnonzero(farms[train]!=farm);vi=np.flatnonzero(farms[train]==farm)
        if not len(ti) or not len(vi):raise RuntimeError('Insufficient inner farm groups')
        inner.append((ti,vi))
    tasks=[(train,inner,s,i) for s in allowed_sets for i in range(len(CONFIGS))]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(evaluate_candidate,tasks))
    for result in results:history.append(dict(outer_fold=outer_fold,arm=arm,**result))
    chosen=max(results,key=lambda r:(r['inner_correct'],r['inner_macro_f1'],-abs(r['threshold']-.5),-len(SETS[r['feature_set']]),-r['config_id']))
    return chosen

arms={'ndvi_control':['ndvi_only'],'ndvi_distance':['nearest','distance_summary']}
probs={arm:np.full(44,np.nan) for arm in arms};thresholds={arm:np.full(44,np.nan) for arm in arms};fold_reports=[]
for fold in sorted(set(folds)):
    train=np.flatnonzero(folds!=fold);test=np.flatnonzero(folds==fold)
    assert not set(farms[train])&set(farms[test]);assert not set(fields[train])&set(fields[test])
    for arm,allowed in arms.items():
        chosen=select(train,allowed,fold,arm)
        model=build(CONFIGS[chosen['config_id']]);cols=columns(chosen['feature_set'])
        model.fit(X[np.ix_(train,cols)],y[train]);p=probability(model,X[np.ix_(test,cols)])
        probs[arm][test]=p;thresholds[arm][test]=chosen['threshold']
        saved=dict(model=model,features=SETS[chosen['feature_set']],threshold=chosen['threshold'],selection=chosen)
        path=RUN/'models'/f'{arm}_fold_{fold}.joblib';joblib.dump(saved,path)
        np.testing.assert_allclose(probability(joblib.load(path)['model'],X[np.ix_(test,cols)]),p,rtol=0,atol=0)
        entry=dict(outer_fold=fold,arm=arm,n_train=len(train),n_test=len(test),train_farm_groups=sorted(set(farms[train])),test_farm_groups=sorted(set(farms[test])),chosen=chosen,config=CONFIGS[chosen['config_id']],outer_metrics=score(y[test],p,chosen['threshold']))
        fold_reports.append(entry)
        print(f'Outer fold {fold} {arm}: {entry["outer_metrics"]["correct"]}/{len(test)}, selected {chosen}',flush=True)
    write_json('fold_results.json',fold_reports)
    write_csv('inner_search_results.csv',history)

for arm in arms:
    if not np.isfinite(probs[arm]).all() or not np.isfinite(thresholds[arm]).all():raise RuntimeError('Incomplete outer evaluation')
baseline_p=np.array([float(bykey[key(r)]['step1_p_silage']) for r in rows]);old_p=np.array([float(bykey[key(r)]['step2_p_silage']) for r in rows])
metrics={'original_step1_ndvi':score(y,baseline_p),'original_step2_nearest':score(y,old_p),**{arm:score(y,probs[arm],thresholds[arm]) for arm in arms}}
improved=metrics['ndvi_distance']['accuracy']>metrics['original_step1_ndvi']['accuracy']
summary=dict(status='completed',region='Maryland only',samples=44,unique_fields=len(set(fields)),metrics=metrics,accuracy_change_pp_vs_original_step1=100*(metrics['ndvi_distance']['accuracy']-metrics['original_step1_ndvi']['accuracy']),accuracy_change_pp_vs_original_step2=100*(metrics['ndvi_distance']['accuracy']-metrics['original_step2_nearest']['accuracy']),accuracy_change_pp_vs_tuned_ndvi_control=100*(metrics['ndvi_distance']['accuracy']-metrics['ndvi_control']['accuracy']),exceeds_original_step1=improved,selection_used_outer_labels=False,development_set_not_new_blind_test=True,source_step2_run=str(SOURCE),no_guarantee_of_improvement=True)
write_json('metrics.json',summary)
paired=[]
for i,r in enumerate(rows):
    out=dict(field_id=r['field_id'],year=r['year'],fold_id=r['fold_id'],farm_group=r['farm_group'],true_label=r['label'],original_step1_prediction=bykey[key(r)]['step1_label'],original_step2_prediction=bykey[key(r)]['step2_label'])
    for arm in arms:
        out[arm+'_p_silage']=float(probs[arm][i]);out[arm+'_threshold']=float(thresholds[arm][i]);out[arm+'_prediction']='silage' if probs[arm][i]>=thresholds[arm][i] else 'grain';out[arm+'_correct']=bool((probs[arm][i]>=thresholds[arm][i])==y[i])
    paired.append(out)
write_csv('paired_oof_predictions.csv',paired)

# Select final deployable models using farm-grouped CV on all 44 rows. They do
# not supply the validation score above; scores remain outer held-out results.
deployment=[]
all_rows=np.arange(44)
for arm,allowed in arms.items():
    chosen=select(all_rows,allowed,'full_model_selection',arm);cols=columns(chosen['feature_set']);model=build(CONFIGS[chosen['config_id']]);model.fit(X[:,cols],y)
    package=dict(model=model,features=SETS[chosen['feature_set']],threshold=chosen['threshold'],selection=chosen,config=CONFIGS[chosen['config_id']])
    joblib.dump(package,RUN/'models'/f'{arm}_full_model.joblib');deployment.append(dict(arm=arm,selection=chosen,config=CONFIGS[chosen['config_id']]))
write_json('deployment_selection.json',deployment);write_csv('inner_search_results.csv',history)
write_json('environment.json',dict(hostname=platform.node(),python=platform.python_version(),numpy=np.__version__,sklearn=sklearn.__version__,joblib=joblib.__version__,execution='NVIDIA Brev CPU; four concurrent candidate evaluations, one thread per tree model'))
write_json('verification.json',dict(outer_folds_unchanged=True,all_44_rows_evaluated=True,no_field_or_farm_crosses_outer_folds=True,inner_farms_disjoint=True,inner_preprocessing_fit_only_on_inner_train=True,outer_preprocessing_fit_only_on_outer_train=True,thresholds_selected_only_from_inner_oof=True,saved_fold_models_reload_equal=True,all_candidate_results_preserved=True,prior_79_55_result_retained=True))
write_json('model_checksums.json',{str(p.relative_to(RUN)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (RUN/'models').glob('*.joblib')})
(RUN/'requirements.lock.txt').write_text(subprocess.check_output([str(ROOT/'venv/bin/python'),'-m','pip','freeze'],text=True))
m=metrics
note=f'''# 第二步改进实验：嵌套分组选择\n\n全部训练在NVIDIA Brev执行，仅使用原44条马里兰官方田块年度记录和奶牛场距离。保留原五个留出农场，每个外层折只在训练农场内部用留一农场验证选择模型、距离表达和阈值。种子固定42，不搜索随机种子。所有候选定义在protocol.json，并保存每个候选的内部得分。内部训练集缺少一类时使用显式常量分类器，不能从外层测试标签补充信息。\n\n|方案|外层预测准确率|正确条数|宏平均F1|青贮召回率|\n|---|---:|---:|---:|---:|\n|原第一步NDVI|{m['original_step1_ndvi']['accuracy']:.2%}|{m['original_step1_ndvi']['correct']}/44|{m['original_step1_ndvi']['macro_f1']:.4f}|{m['original_step1_ndvi']['silage_recall']:.2%}|\n|原第二步最近距离|{m['original_step2_nearest']['accuracy']:.2%}|{m['original_step2_nearest']['correct']}/44|{m['original_step2_nearest']['macro_f1']:.4f}|{m['original_step2_nearest']['silage_recall']:.2%}|\n|本轮嵌套选择NDVI对照|{m['ndvi_control']['accuracy']:.2%}|{m['ndvi_control']['correct']}/44|{m['ndvi_control']['macro_f1']:.4f}|{m['ndvi_control']['silage_recall']:.2%}|\n|本轮嵌套选择NDVI+距离|{m['ndvi_distance']['accuracy']:.2%}|{m['ndvi_distance']['correct']}/44|{m['ndvi_distance']['macro_f1']:.4f}|{m['ndvi_distance']['silage_recall']:.2%}|\n\n本轮距离方案比原第一步变化{summary['accuracy_change_pp_vs_original_step1']:+.2f}个百分点，比原第二步变化{summary['accuracy_change_pp_vs_original_step2']:+.2f}个百分点，比本轮同样调优的NDVI对照变化{summary['accuracy_change_pp_vs_tuned_ndvi_control']:+.2f}个百分点。不能把不同模型调优带来的变化全部归因于奶牛场距离。\n\n候选包含固定随机种子的随机森林、极端随机树、标准化逻辑回归；距离表达为最近距离或最近1/3/5场距离和逆距离暴露度的汇总。每折阈值仅用内层OOF预测选择，不使用外层测试标签。用于部署的全量模型另行在44条上通过分组CV选择，不把训练内分数当验证分数。\n\n**限制**：之前已反复查看这44条数据的验证结果，因此本轮属于开发集再实验，不是全新的独立盲测。只有5个农场，少数折类别极少；没有显著性或真实部署性能保证。奶牛场资料为2026年整理，历史在营状态未逐场核实，直线距离也不等于实际供需或道路距离。原来79.55%的负结果保留不变，不覆盖旧报告，不删除不利候选。第三步未运行。\n\n输入哈希、固定协议、内部搜索记录、外层逐田结果和模型均已保存。脚本放到 /home/ubuntu/cornhub-compute/，运行 venv/bin/python train_step2_nested.py；其输入为latest_step2.txt指向的冻结第二步数据。\n'''
(RUN/'README.md').write_text(note)
with zipfile.ZipFile(RUN/'trained_models.zip','w',zipfile.ZIP_DEFLATED) as archive:
    for p in sorted((RUN/'models').glob('*.joblib')):archive.write(p,p.relative_to(RUN))
    for name in ['environment.json','metrics.json','model_checksums.json','deployment_selection.json']:archive.write(RUN/name,name)
(ROOT/'latest_step2_nested.txt').write_text(str(RUN))
print(json.dumps(summary,ensure_ascii=False,indent=2));print('Results:',RUN)
