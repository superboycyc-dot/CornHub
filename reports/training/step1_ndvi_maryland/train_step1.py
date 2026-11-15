"""Run step 1 on Brev: official Maryland labels, NDVI-only grouped validation."""
import csv
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tarfile
import tempfile

import joblib
import numpy as np
import sklearn
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, balanced_accuracy_score, brier_score_loss, classification_report, confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.pipeline import make_pipeline

ROOT=Path(__file__).resolve().parent
RUN=ROOT/'runs'/('step1-ndvi-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
RUN.mkdir(parents=True)
INPUT=RUN/'inputs'
INPUT.mkdir()
FEATURES=['ndvi_peak','peak_doy','max_drop_per_day','drop_doy','ndvi_late_mean']
PARAMETERS=dict(n_estimators=100,max_depth=4,min_samples_leaf=2,class_weight='balanced',random_state=42,n_jobs=1)
BRANCHES={
    'work/a-data':['data/processed/core/labels.csv','data/processed/core/validation_folds.csv','data/processed/core/fields.geojson','data/processed/core/README.md'],
    'work/b-satellite':['data/processed/satellite/features.csv','data/processed/satellite/timeseries.csv'],
    'work/c-model':['src/model/pipeline.py'],
}

def write_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def write_csv(path,rows,columns=None):
    with path.open('w',encoding='utf-8-sig',newline='') as h:
        writer=csv.DictWriter(h,fieldnames=columns or list(rows[0]))
        writer.writeheader();writer.writerows(rows)

env=dict(os.environ)
env['GIT_SSH_COMMAND']=f'ssh -i {ROOT}/keys/github_readonly -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile={ROOT}/keys/known_hosts'
cache=ROOT/'repository.git'
def git(*args,capture=False):
    result=subprocess.run(['git','--git-dir',str(cache),*args],env=env,check=True,stdout=subprocess.PIPE if capture else None)
    return result.stdout

# Only the three Maryland training branches are fetched. No overseas files or distances.
git('fetch','--depth=1','origin',*[f'+refs/heads/{b}:refs/remotes/origin/{b}' for b in BRANCHES])
commits={b:git('rev-parse',f'refs/remotes/origin/{b}',capture=True).decode().strip() for b in BRANCHES}
manifest=[]
for branch,paths in BRANCHES.items():
    with tempfile.TemporaryFile() as h:
        subprocess.run(['git','--git-dir',str(cache),'archive',commits[branch],'--',*paths],env=env,stdout=h,check=True)
        h.seek(0)
        with tarfile.open(fileobj=h) as archive:archive.extractall(INPUT,filter='data')
    for path in paths:
        f=INPUT/path
        manifest.append(dict(path=path,branch=branch,commit=commits[branch],sha256=hashlib.sha256(f.read_bytes()).hexdigest()))
write_json(RUN/'input_manifest.json',manifest)
shutil.copyfile(__file__,RUN/'train_step1.py')

spec=importlib.util.spec_from_file_location('upstream_model',INPUT/'src/model/pipeline.py')
upstream=importlib.util.module_from_spec(spec);spec.loader.exec_module(upstream)
audit=dict(input_rows={},missing_files=[],errors=[],duplicate_keys=[])
base=INPUT/'data/processed'
labels=upstream.load(base/'core/labels.csv','labels',audit)
folds=upstream.load(base/'core/validation_folds.csv','folds',audit)
features=upstream.load(base/'satellite/features.csv','features',audit)
groups=upstream.inspect_core(base,labels,folds,features,audit)
if audit['errors'] or audit['missing_files']:raise RuntimeError(json.dumps(audit))
if len(labels)!=44 or len({k[0] for k in labels})!=34:
    raise RuntimeError('This step is explicitly scoped to 44 official Maryland labeled field-years / 34 fields')
if not set(labels)<=set(features) or not set(labels)<=set(folds):raise RuntimeError('Missing labeled keys')
rows=[]
for key,label in sorted(labels.items()):
    f=features[key]
    if f['quality_flag'] not in {'usable','limited'}:raise RuntimeError(f'Non-eligible official row {key}')
    rows.append({**label,**{n:f[n] for n in FEATURES},'fold_id':folds[key]['fold_id'],'farm_group':groups[key[0]],'quality_flag':f['quality_flag']})
X=np.array([[np.nan if r[n] is None else r[n] for n in FEATURES] for r in rows],dtype=np.float64)
y=np.array([int(r['label']=='silage') for r in rows])
fold_ids=np.array([r['fold_id'] for r in rows])
field_ids=np.array([r['field_id'] for r in rows])
farm_ids=np.array([r['farm_group'] for r in rows])
if len(set(fold_ids))!=5:raise RuntimeError('Expected frozen five-fold scheme')
for ids in [field_ids,farm_ids]:
    for identity in set(ids):
        if len(set(fold_ids[ids==identity]))!=1:raise RuntimeError('Field/farm crosses folds')
write_csv(RUN/'frozen_training_rows.csv',rows)

def score(truth,probs):
    pred=(np.array(probs)>=.5).astype(int)
    return dict(n=len(truth),accuracy=float(accuracy_score(truth,pred)),balanced_accuracy=float(balanced_accuracy_score(truth,pred)) if len(set(truth))==2 else None,macro_f1=float(f1_score(truth,pred,labels=[0,1],average='macro',zero_division=0)) if len(set(truth))==2 else None,silage_precision=float(precision_score(truth,pred,zero_division=0)),silage_recall=float(recall_score(truth,pred,zero_division=0)) if 1 in truth else None,brier_score=float(brier_score_loss(truth,probs)),roc_auc=float(roc_auc_score(truth,probs)) if len(set(truth))==2 else None,confusion_matrix=confusion_matrix(truth,pred,labels=[0,1]).tolist(),confusion_order=['grain','silage'])

prob=np.full(len(rows),np.nan)
dummy_pred=np.full(len(rows),-1)
fold_reports=[]
models=RUN/'models';models.mkdir()
for fold in sorted(set(fold_ids)):
    train=np.flatnonzero(fold_ids!=fold);test=np.flatnonzero(fold_ids==fold)
    assert not set(field_ids[train])&set(field_ids[test])
    assert not set(farm_ids[train])&set(farm_ids[test])
    if len(set(y[train]))!=2:raise RuntimeError('Training fold lacks a class; no fabricated predictions')
    model=make_pipeline(SimpleImputer(strategy='median',keep_empty_features=True),RandomForestClassifier(**PARAMETERS))
    model.fit(X[train],y[train])
    prob[test]=model.predict_proba(X[test])[:,list(model.classes_).index(1)]
    dummy=DummyClassifier(strategy='most_frequent').fit(X[train],y[train])
    dummy_pred[test]=dummy.predict(X[test])
    path=models/f'fold_{fold}.joblib';joblib.dump(model,path)
    np.testing.assert_allclose(joblib.load(path).predict_proba(X[test]),model.predict_proba(X[test]),rtol=0,atol=0)
    counts=np.bincount(y[train],minlength=2)
    fold_reports.append(dict(fold_id=fold,n_train=len(train),n_test=len(test),train_class_counts=counts.tolist(),test_class_counts=np.bincount(y[test],minlength=2).tolist(),test_field_ids=sorted(set(field_ids[test])),test_farm_groups=sorted(set(farm_ids[test])),metrics=score(y[test],prob[test]),warnings=['Fewer than two training samples in one class'] if min(counts)<2 else [],imputer_statistics=model.named_steps['simpleimputer'].statistics_.tolist()))
    print(f'Fold {fold}: held out {len(test)} rows, correct {sum((prob[test]>=.5)==y[test])}',flush=True)
if not np.isfinite(prob).all():raise RuntimeError('Incomplete OOF coverage')

pred=(prob>=.5).astype(int)
oof=[]
for i,r in enumerate(rows):
    oof.append(dict(field_id=r['field_id'],year=r['year'],fold_id=r['fold_id'],farm_group=r['farm_group'],true_label=r['label'],predicted_label='silage' if pred[i] else 'grain',p_silage=float(prob[i]),correct=bool(pred[i]==y[i]),quality_flag=r['quality_flag'],prediction_role='oof'))
write_csv(RUN/'oof_predictions.csv',oof)
full=make_pipeline(SimpleImputer(strategy='median',keep_empty_features=True),RandomForestClassifier(**PARAMETERS))
full.fit(X,y)
joblib.dump(dict(model=full,features=FEATURES,threshold=.5,class_mapping={0:'grain',1:'silage'},parameters=PARAMETERS),models/'ndvi_full_model.joblib')
reloaded=joblib.load(models/'ndvi_full_model.joblib')['model']
np.testing.assert_allclose(reloaded.predict_proba(X),full.predict_proba(X),rtol=0,atol=0)
importance=[dict(feature=n,importance=float(v)) for n,v in zip(FEATURES,full.named_steps['randomforestclassifier'].feature_importances_)]
write_csv(RUN/'feature_importance.csv',importance)

result=score(y,prob)
result.update(status='trained_and_evaluated',stage=1,region='Maryland BARC only',sample_count=len(rows),unique_fields=len(set(field_ids)),class_counts={'grain':int(sum(y==0)),'silage':int(sum(y==1))},correct=int(sum(pred==y)),incorrect=int(sum(pred!=y)),features=FEATURES,excluded_predictors=['dairy_distance','area','field_id','year','farm_group','fold_id','label','valid_obs_count','max_gap_days','quality_flag'],evaluation='frozen five-fold leave-one-farm-out OOF',threshold=.5,probabilities_calibrated=False,majority_oof_accuracy=float(accuracy_score(y,dummy_pred)),accuracy_gain_over_majority_pp=100*float(accuracy_score(y,pred)-accuracy_score(y,dummy_pred)),quality_counts={q:sum(r['quality_flag']==q for r in rows) for q in ['usable','limited']},by_year={str(yr):score(y[[r['year']==yr for r in rows]],prob[[r['year']==yr for r in rows]]) for yr in sorted({r['year'] for r in rows})},limitations=['44 field-years on 34 fields and five farms; exploratory small-sample estimate','One fold has fewer than two training examples in a class','No independent external-region or future-year test','Training success does not guarantee improved accuracy; stage 2/3 not run'])
write_json(RUN/'metrics.json',result)
write_json(RUN/'fold_metrics.json',fold_reports)
write_json(RUN/'input_validation.json',audit)
write_json(RUN/'comparison_protocol.json',dict(completed_stage=1,stage2='Same 44 rows, labels, folds, model parameters and seed; append dairy-distance features. Report actual improvement, no improvement or degradation.',stage3='Not run. Requires labeled external data, source/field deduplication, domain-aware held-out evaluation and fold-local missing-data handling. Unlabeled rows cannot produce accuracy.',missing_data='NaN internally; training-fold median imputation; entirely missing training columns use zero; no test-fold statistics',primary_metrics=['accuracy','macro_f1','silage_recall','balanced_accuracy']))
write_json(RUN/'environment.json',dict(hostname=platform.node(),python=platform.python_version(),numpy=np.__version__,sklearn=sklearn.__version__,joblib=joblib.__version__,execution='NVIDIA Brev host CPU; random forest is not a CUDA model',commits=commits,parameters=PARAMETERS))
(RUN/'requirements.lock.txt').write_text(subprocess.check_output([str(ROOT/'venv/bin/python'),'-m','pip','freeze'],text=True))
with (RUN/'oof_predictions.csv').open(encoding='utf-8-sig') as h:saved=list(csv.DictReader(h))
assert len(saved)==44 and len({(r['field_id'],r['year']) for r in saved})==44
saved_correct=sum(r['true_label']==r['predicted_label'] for r in saved)
assert saved_correct==result['correct'] and saved_correct/44==result['accuracy']
write_json(RUN/'verification.json',dict(saved_predictions_reread=True,metrics_recomputed_from_saved_predictions=True,fold_models_reload_equal=True,full_model_reload_equal=True,no_field_or_farm_fold_leakage=True,only_five_ndvi_predictors=True,all_44_rows_evaluated=True))
text=f'''# 第一步：马里兰官方数据，NDVI基线训练\n\n在 NVIDIA Brev 机器 {platform.node()} 完成训练和验证。仅使用44条官方带标签田块年度记录（34块田，2021–2023）；32条籽粒、12条青贮。未读取奶牛场距离、海外或全国候选田。\n\n模型为随机森林：100棵树，深度4，叶节点最少2个样本，平衡类别权重，随机种子42。预测变量为NDVI峰值、峰值日期、最大日下降速度、下降日期和晚季NDVI均值。观测次数和最长缺测间隔只用于质量校验，不进入模型。\n\n按既有农场分组五折划分，逐折训练并预测未见农场；同一田不同年份不会跨训练/测试折。缺失值仅用训练折中位数补齐，训练列全缺失时填零。无超参数搜索、无验证集调参。\n\n实际OOF准确率：{result['accuracy']:.2%}（{result['correct']}/44），宏平均F1：{result['macro_f1']:.4f}，青贮召回率：{result['silage_recall']:.2%}。同样划分的多数类基准准确率：{result['majority_oof_accuracy']:.2%}；差值：{result['accuracy_gain_over_majority_pp']:+.2f}个百分点。\n\n这里报告的是留出农场的预测结果，不是用训练数据评估自己。样本小，单折仅一个青贮训练样本等问题仍存在，概率未校准，未证明对其他地区或未来年份有效。第二、第三步没有运行。第二步须保持样本、标签、折分和模型配置不变，再报告加距离后效果实际提高、持平还是下降。\n\n逐田结果见 oof_predictions.csv，实际指标见 metrics.json，折结果见 fold_metrics.json；模型保存在 models/，输入快照与来源哈希在 inputs/ 和 input_manifest.json，训练代码副本为 train_step1.py。计算在该NVIDIA机器的CPU执行；现有随机森林不需要GPU。\n'''
(RUN/'README.md').write_text(text)
(ROOT/'latest_step1.txt').write_text(str(RUN))
print(json.dumps(result,ensure_ascii=False,indent=2))
print('Results:',RUN)
