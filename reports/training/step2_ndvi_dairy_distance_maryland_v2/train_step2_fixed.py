"""Fixed follow-up: all split features instead of sqrt feature subsampling."""
import csv
from datetime import datetime,timezone
import hashlib,json,platform,shutil,zipfile
from pathlib import Path
import joblib,numpy as np,sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.metrics import accuracy_score,balanced_accuracy_score,confusion_matrix,f1_score,recall_score,precision_score,brier_score_loss

ROOT=Path(__file__).resolve().parent
SOURCE=Path((ROOT/'latest_step2.txt').read_text().strip())
NESTED=Path((ROOT/'latest_step2_nested.txt').read_text().strip())
RUN=ROOT/'runs'/('step2-fixed-all-features-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
RUN.mkdir(parents=True);(RUN/'models').mkdir()
def read(p):
 with p.open(encoding='utf-8-sig',newline='') as h:return list(csv.DictReader(h))
def write(name,data):(RUN/name).write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def csvout(name,data):
 with (RUN/name).open('w',encoding='utf-8-sig',newline='') as h:
  w=csv.DictWriter(h,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
rows=read(SOURCE/'frozen_training_rows.csv');original=read(SOURCE/'paired_oof_predictions.csv')
base=['ndvi_peak','peak_doy','max_drop_per_day','drop_doy','ndvi_late_mean']
sets={'ndvi_control':base,'ndvi_distance':base+['nearest_dairy_distance_km']}
params=dict(n_estimators=100,max_depth=4,min_samples_leaf=2,class_weight='balanced',random_state=42,n_jobs=1,max_features=1.0)
write('protocol.json',dict(parameters=params,threshold=.5,only_change_from_original_RF='max_features: sqrt -> 1.0',feature_sets=sets,outer_folds='same frozen five farm folds',experiment_type='fixed development follow-up after failed nested selection; not new blind validation',no_seed_search=True,no_threshold_search=True,no_row_filtering=True))
csvout('frozen_training_rows.csv',rows);shutil.copyfile(__file__,RUN/'train_step2_fixed.py')
y=np.array([int(r['label']=='silage') for r in rows]);folds=np.array([r['fold_id'] for r in rows]);farms=np.array([r['farm_group'] for r in rows]);fields=np.array([r['field_id'] for r in rows])
assert len(rows)==44 and len({(r['field_id'],r['year']) for r in rows})==44
for ids in [farms,fields]:
 for value in set(ids):assert len(set(folds[ids==value]))==1
probabilities={};foldreports=[]
def metrics(p):
 pred=(np.asarray(p)>=.5).astype(int)
 return dict(correct=int(sum(pred==y)),n=44,accuracy=float(accuracy_score(y,pred)),macro_f1=float(f1_score(y,pred,average='macro',labels=[0,1],zero_division=0)),balanced_accuracy=float(balanced_accuracy_score(y,pred)),silage_recall=float(recall_score(y,pred)),silage_precision=float(precision_score(y,pred,zero_division=0)),brier_score=float(brier_score_loss(y,p)),confusion_matrix=confusion_matrix(y,pred,labels=[0,1]).tolist(),confusion_order=['grain','silage'])
for arm,names in sets.items():
 X=np.array([[float(r[n]) if r[n] not in ('',None) else np.nan for n in names] for r in rows]);p=np.full(44,np.nan)
 for fold in sorted(set(folds)):
  train=np.flatnonzero(folds!=fold);test=np.flatnonzero(folds==fold)
  assert not set(farms[train])&set(farms[test]) and not set(fields[train])&set(fields[test])
  model=make_pipeline(SimpleImputer(strategy='median',keep_empty_features=True),RandomForestClassifier(**params));model.fit(X[train],y[train]);p[test]=model.predict_proba(X[test])[:,list(model.classes_).index(1)]
  path=RUN/'models'/f'{arm}_fold_{fold}.joblib';joblib.dump(dict(model=model,features=names,threshold=.5),path)
  np.testing.assert_allclose(joblib.load(path)['model'].predict_proba(X[test])[:,list(model.classes_).index(1)],p[test],rtol=0,atol=0)
  foldreports.append(dict(arm=arm,fold_id=fold,n_test=len(test),correct=int(sum((p[test]>=.5)==y[test]))))
 assert np.isfinite(p).all();probabilities[arm]=p
 full=make_pipeline(SimpleImputer(strategy='median',keep_empty_features=True),RandomForestClassifier(**params));full.fit(X,y);joblib.dump(dict(model=full,features=names,threshold=.5,parameters=params),RUN/'models'/f'{arm}_full_model.joblib')
bykey={(r['field_id'],r['year']):r for r in original}
original1=np.array([float(bykey[(r['field_id'],r['year'])]['step1_p_silage']) for r in rows]);original2=np.array([float(bykey[(r['field_id'],r['year'])]['step2_p_silage']) for r in rows])
results=dict(original_step1=metrics(original1),original_step2=metrics(original2),**{a:metrics(p) for a,p in probabilities.items()})
nested=json.loads((NESTED/'metrics.json').read_text())
summary=dict(status='completed',metrics=results,change_pp_vs_original_step1=100*(results['ndvi_distance']['accuracy']-results['original_step1']['accuracy']),change_pp_vs_original_step2=100*(results['ndvi_distance']['accuracy']-results['original_step2']['accuracy']),distance_gain_pp_vs_matched_control=100*(results['ndvi_distance']['accuracy']-results['ndvi_control']['accuracy']),nested_experiment_also_reported=nested['metrics'],development_rerun_not_independent_blind_test=True)
write('metrics.json',summary);write('fold_results.json',foldreports)
paired=[]
for i,r in enumerate(rows):
 out=dict(field_id=r['field_id'],year=r['year'],fold_id=r['fold_id'],farm_group=r['farm_group'],true_label=r['label'],original_step1_label=bykey[(r['field_id'],r['year'])]['step1_label'],original_step2_label=bykey[(r['field_id'],r['year'])]['step2_label'])
 for arm,p in probabilities.items():out[arm+'_p_silage']=float(p[i]);out[arm+'_prediction']='silage' if p[i]>=.5 else 'grain';out[arm+'_correct']=bool((p[i]>=.5)==y[i])
 paired.append(out)
csvout('paired_oof_predictions.csv',paired)
write('input_manifest.json',[dict(path=str(SOURCE/n),sha256=hashlib.sha256((SOURCE/n).read_bytes()).hexdigest()) for n in ['frozen_training_rows.csv','paired_oof_predictions.csv','metrics.json']]+[dict(path=str(NESTED/'metrics.json'),sha256=hashlib.sha256((NESTED/'metrics.json').read_bytes()).hexdigest())])
write('verification.json',dict(same_44_rows=True,same_outer_folds=True,no_field_or_farm_leakage=True,fixed_threshold_and_seed=True,only_max_features_changed=True,saved_fold_models_reproduce_probabilities=True))
write('environment.json',dict(hostname=platform.node(),python=platform.python_version(),numpy=np.__version__,sklearn=sklearn.__version__,joblib=joblib.__version__,execution='NVIDIA Brev CPU'))
write('model_checksums.json',{str(p.relative_to(RUN)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (RUN/'models').glob('*.joblib')})
lines=['# 第二步再次实验：固定全特征分裂','', '本次在NVIDIA上计算，仍为44条马里兰记录、相同五折农场留出。原随机森林只将max_features从sqrt改为1.0，其余100棵树、深度4、叶节点2、类别平衡、种子42和阈值0.5不变。对照NDVI-only和NDVI+最近奶牛场距离同时执行。','', '|方案|正确数|准确率|宏平均F1|青贮召回率|','|---|---:|---:|---:|---:|']
for name,m in results.items():lines.append(f'|{name}|{m["correct"]}/44|{m["accuracy"]:.2%}|{m["macro_f1"]:.4f}|{m["silage_recall"]:.2%}|')
lines+=['',f'与原第二步相比准确率变化{summary["change_pp_vs_original_step2"]:+.2f}个百分点，与原第一步相比{summary["change_pp_vs_original_step1"]:+.2f}个百分点；与本轮匹配NDVI对照相比{summary["distance_gain_pp_vs_matched_control"]:+.2f}个百分点。','',f'同时保留失败的嵌套选型实验：NDVI对照{nested["metrics"]["ndvi_control"]["accuracy"]:.2%}，NDVI+距离{nested["metrics"]["ndvi_distance"]["accuracy"]:.2%}。没有隐藏失败实验。','', '**本轮是已多次查看的开发数据上的再实验，不是独立盲测，也没有统计显著性保证。不能把模型设置改变带来的收益全部归因于距离；历史奶牛场位置仍未独立核验。** 原79.55%结果不覆盖，第三步未运行。','', '逐田预测、源码、协议、输入哈希和模型均已保存。脚本放在 /home/ubuntu/cornhub-compute/，运行 venv/bin/python train_step2_fixed.py。']
(RUN/'README.md').write_text('\n'.join(lines)+'\n')
with zipfile.ZipFile(RUN/'trained_models.zip','w',zipfile.ZIP_DEFLATED) as z:
 for p in (RUN/'models').glob('*.joblib'):z.write(p,p.relative_to(RUN))
 for n in ['metrics.json','environment.json','model_checksums.json']:z.write(RUN/n,n)
(ROOT/'latest_step2_fixed.txt').write_text(str(RUN));print(json.dumps(summary,ensure_ascii=False,indent=2));print('Results:',RUN)
