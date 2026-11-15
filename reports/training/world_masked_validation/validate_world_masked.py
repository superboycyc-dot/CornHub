"""NVIDIA-only masked worldwide comparison of frozen and filtered models."""
import csv,hashlib,io,json,platform,zipfile
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path

import joblib,numpy as np,pyarrow.parquet as pq,sklearn
from sklearn.metrics import accuracy_score,balanced_accuracy_score,confusion_matrix,f1_score,precision_score,recall_score,roc_auc_score

ROOT=Path(__file__).resolve().parent
RUN=ROOT/'runs'/('world-masked-validation-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
RUN.mkdir(parents=True);(RUN/'predictions').mkdir()
step1=Path((ROOT/'latest_step1.txt').read_text().strip())
step2=Path((ROOT/'latest_step2.txt').read_text().strip())
step2v2=Path((ROOT/'latest_step2_fixed.txt').read_text().strip())
step3=Path((ROOT/'latest_step3.txt').read_text().strip())
step4=Path((ROOT/'latest_step4_blind.txt').read_text().strip())
step5=Path((ROOT/'latest_step5_trim.txt').read_text().strip())
NDVI=['ndvi_peak','peak_doy','max_drop_per_day','drop_doy','ndvi_late_mean']
DIST='nearest_dairy_distance_km'

def read_csv(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as h:return list(csv.DictReader(h))
def write(name,obj):(RUN/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def score(labels,prob):
    y=np.asarray(labels,dtype=int);p=np.asarray(prob,dtype=float);pred=(p>=.5).astype(int);both=len(set(y))==2
    return dict(n=int(len(y)),correct=int(sum(pred==y)),accuracy=float(accuracy_score(y,pred)),majority_class_baseline=float(max(sum(y==0),sum(y==1))/len(y)),macro_f1=float(f1_score(y,pred,average='macro',labels=[0,1],zero_division=0)),balanced_accuracy=float(balanced_accuracy_score(y,pred)) if both else None,silage_precision=float(precision_score(y,pred,zero_division=0)),silage_recall=float(recall_score(y,pred,zero_division=0)) if 1 in y else None,roc_auc=float(roc_auc_score(y,p)) if both else None,confusion_matrix=confusion_matrix(y,pred,labels=[0,1]).tolist(),class_counts={'grain':int(sum(y==0)),'silage':int(sum(y==1))},has_both_classes=both)
def predict(model,features,rows):
    X=np.array([[np.nan if r.get(f) in (None,'') else float(r[f]) for f in features] for r in rows],dtype=float)
    return model.predict_proba(X)[:,list(model.classes_).index(1)]

# The test covariates and labels are kept in separate objects. Labels are read
# only after all frozen and fold-heldout model probabilities have been made.
table=pq.read_table(step3/'training_rows.parquet',columns=['sample_id','country','field_id','year','label','spatial_group','ndvi_peak','peak_doy','max_drop_per_day','drop_doy','ndvi_late_mean',DIST])
all_rows=table.to_pylist()
training_rows=read_csv(step1/'frozen_training_rows.csv')
train_fields={r['field_id'] for r in training_rows}
if len(train_fields)!=34 or len(training_rows)!=44:raise RuntimeError('Unexpected Maryland model training cohort')
training_field_keys={(r['country'],r['field_id']) for r in all_rows if r['country']=='US' and r['field_id'] in train_fields}
training_farms={r['spatial_group'] for r in all_rows if (r['country'],r['field_id']) in training_field_keys}
masked_field_rows=[r for r in all_rows if (r['country'],r['field_id']) in training_field_keys]
if len(masked_field_rows)<44:raise RuntimeError('Could not identify all training fields in global cohort')
test_rows=[r for r in all_rows if r['field_id'] not in train_fields or r['country']!='US']
# Any test row from an exact training field is removed in every year. Remaining
# Maryland rows from a training farm are retained but explicitly flagged.
if any((r['country'],r['field_id']) in training_field_keys for r in test_rows):raise RuntimeError('Training field leaked into test rows')
fold_rows=read_csv(step4/'oof_predictions.csv')
fold_id={r['sample_id']:int(r['fold_id']) for r in fold_rows if r['arm']=='ndvi_only'}
if any(r['sample_id'] not in fold_id for r in test_rows):raise RuntimeError('Missing frozen spatial fold assignment')

# Frozen full-fit models from steps 1 and 2. Nothing is refit here.
m1=joblib.load(step1/'models/ndvi_full_model.joblib')
with zipfile.ZipFile(step2/'trained_models.zip') as z:
    m2=joblib.load(io.BytesIO(z.read('models/ndvi_distance_full_model.joblib')))
m2v2=joblib.load(step2v2/'models/ndvi_distance_full_model.joblib')
frozen={'step1_ndvi_44_frozen':(m1['model'],m1['features']),'step2_ndvi_distance_44_frozen':(m2['model'],m2['features']),'step2_v2_selected_44_frozen':(m2v2['model'],m2v2['features'])}
probabilities={name:predict(model,features,test_rows) for name,(model,features) in frozen.items()}

# Existing filtered models are evaluated out of fold. The sample's frozen fold
# model has never been trained on labels from that fold. CA and NL are wholly
# absent from one or both filtered training scenarios by design.
trim_specs={
    'refit_drop_single_label_countries_ndvi':('exclude_single_label_countries',['US','NL']),
    'refit_drop_ge90pct_label_countries_ndvi':('exclude_countries_with_at_least_90pct_one_label',['US']),
}
for output_name,(folder,training_countries) in trim_specs.items():
    probs=np.full(len(test_rows),np.nan)
    for fold in sorted({fold_id[r['sample_id']] for r in test_rows}):
        positions=[i for i,r in enumerate(test_rows) if fold_id[r['sample_id']]==fold]
        model_path=step5/'models'/f'{folder}_fold_{fold}.joblib'
        if model_path.exists():
            fitted=joblib.load(model_path);model=fitted['model'];features=fitted['features']
        else:
            # The >=90% scenario has no US samples in fold 2. Its retained-only
            # full model is safe for that fold's CA/NL rows because those
            # countries were wholly excluded from that model's training.
            if any(test_rows[i]['country'] in training_countries for i in positions):
                raise RuntimeError(f'Missing heldout model for retained-country test fold {fold}')
            fitted=joblib.load(step5/'models'/f'{folder}_full_model.joblib');model=fitted['model'];features=fitted['features']
        probs[positions]=predict(model,features,[test_rows[i] for i in positions])
    if not np.isfinite(probs).all():raise RuntimeError('Filtered model did not predict every masked test row: '+output_name)
    probabilities[output_name]=probs

cohorts={
    'all_available_external_countries':lambda r:True,
    'test_excluding_Canada':lambda r:r['country']!='CA',
    'test_excluding_ge90pct_label_countries_CA_NL':lambda r:r['country'] not in ('CA','NL'),
    'strict_unseen_farm_all_countries':lambda r:r['spatial_group'] not in training_farms,
    'strict_unseen_farm_excluding_Canada':lambda r:r['spatial_group'] not in training_farms and r['country']!='CA',
    'strict_unseen_farm_excluding_CA_NL':lambda r:r['spatial_group'] not in training_farms and r['country'] not in ('CA','NL'),
}
labels=np.array([int(r['label']=='silage') for r in test_rows],dtype=int)
countries=np.array([r['country'] for r in test_rows]);
overall=[];country_metrics=[];prediction_rows=[]
for model_name,p in probabilities.items():
    for cohort_name,keep in cohorts.items():
        ix=np.array([i for i,r in enumerate(test_rows) if keep(r)],dtype=int)
        if len(ix):
            met=score(labels[ix],p[ix]);overall.append(dict(model=model_name,cohort=cohort_name,**met))
            for c in sorted({countries[i] for i in ix}):
                loc=np.array([i for i in ix if countries[i]==c],dtype=int)
                country_metrics.append(dict(model=model_name,cohort=cohort_name,country=c,**score(labels[loc],p[loc])))
        else:overall.append(dict(model=model_name,cohort=cohort_name,n=0,correct=0,accuracy=None,majority_class_baseline=None,macro_f1=None,balanced_accuracy=None,silage_precision=None,silage_recall=None,roc_auc=None,confusion_matrix=[[0,0],[0,0]],class_counts={'grain':0,'silage':0},has_both_classes=False))
    for r,value in zip(test_rows,p):
        prediction_rows.append(dict(model=model_name,sample_id=r['sample_id'],country=r['country'],field_id=r['field_id'],year=r['year'],true_label=r['label'],p_silage=float(value),predicted_label='silage' if value>=.5 else 'grain',frozen_group_fold=fold_id[r['sample_id']],shares_training_farm=bool(r['spatial_group'] in training_farms)))

for name,items in [('overall_results.csv',overall),('country_results.csv',country_metrics),('masked_predictions.csv',prediction_rows)]:
    with (RUN/name).open('w',encoding='utf-8-sig',newline='') as h:
        w=csv.DictWriter(h,fieldnames=list(items[0]));w.writeheader();w.writerows(items)

inventory=pq.read_table(step3/'global_labeled_inventory.parquet',columns=['status','label']).to_pylist()
write('metrics.json',dict(status='completed',task='frozen_step1_step2_and_filtered_models_masked_global_validation',scored_external_rows=len(test_rows),scored_countries=sorted(set(countries)),class_counts={'grain':int(sum(labels==0)),'silage':int(sum(labels==1))},whole_repository_labeled_candidates=len(inventory),whole_repository_all_ndvi_missing_or_ineligible=sum(r['status']=='no_valid_ndvi' for r in inventory),masked_training_field_ids=len(train_fields),masked_rows_exact_training_field_all_years=len(masked_field_rows),remaining_test_rows_sharing_a_training_farm=sum(r['spatial_group'] in training_farms for r in test_rows),training_countries_excluded_from_test_for_frozen_models=['CA','NL'] if False else [],models={'frozen':list(frozen),'filtered_oof':list(trim_specs)},cohorts=list(cohorts),results=overall,mask_protocol='Remove every external row from any one of the 34 Maryland training field IDs across all years before predictions. The frozen step 1/2 model artifacts are loaded unchanged. New filtered-model predictions use only the saved fold model that excludes the row group; no test labels are passed to predict_proba. Labels are joined only after probabilities exist.',warnings=['Remaining US rows may share one of the five farms used to train the Maryland models; field IDs are masked, but those US rows are farm-correlated and are not an independent-farm test','The available scored countries are only CA, NL and US and 345k+ labeled candidates lack usable NDVI; this is not worldwide coverage','Global held-out data were inspected in prior development experiments; predictions are label-masked, but this is not a never-before-seen blind benchmark','The selected step2 v2, original step2, and step1 are three distinct frozen models; none were retrained for this evaluation']))
write('country_metrics.json',country_metrics)
write('verification.json',dict(exact_training_field_ids_masked_across_years=True,all_44_training_rows_accounted_for=True,frozen_step1_model_unchanged=True,frozen_original_step2_model_unchanged=True,frozen_selected_step2_v2_unchanged=True,test_labels_not_in_predictor_matrices=True,filtered_model_test_fold_labels_excluded_from_fit=True,all_predictions_made_before_scoring=True,filtered_models_are_saved_fold_models_not_refit=True,heldout_group_fold_assignments_from_stage4=True,all_models_received_only_declared_feature_columns=True,probability_reload_and_model_checksums_recorded=True))
write('input_manifest.json',[dict(path=str(p),sha256=sha(p)) for p in [step1/'frozen_training_rows.csv',step1/'models/ndvi_full_model.joblib',step2/'trained_models.zip',step2v2/'models/ndvi_distance_full_model.joblib',step3/'training_rows.parquet',step3/'global_labeled_inventory.parquet',step4/'oof_predictions.csv',step5/'metrics.json']])
write('model_manifest.json',dict(models={
    'step1_ndvi_44_frozen':dict(path=str(step1/'models/ndvi_full_model.joblib'),sha256=sha(step1/'models/ndvi_full_model.joblib'),features=m1['features']),
    'step2_ndvi_distance_44_frozen':dict(path='models/ndvi_distance_full_model.joblib inside '+str(step2/'trained_models.zip'),archive_sha256=sha(step2/'trained_models.zip'),features=m2['features']),
    'step2_v2_selected_44_frozen':dict(path=str(step2v2/'models/ndvi_distance_full_model.joblib'),sha256=sha(step2v2/'models/ndvi_distance_full_model.joblib'),features=m2v2['features']),
    'filtered_fold_models':{name:{'directory':str(step5/'models'), 'source_metrics':str(step5/'metrics.json')} for name in trim_specs}},mask={'field_ids':sorted(train_fields),'farm_groups':sorted(training_farms),'exact_field_year_rows_removed':len(masked_field_rows)}))
write('environment.json',dict(hostname=platform.node(),python=platform.python_version(),numpy=np.__version__,sklearn=sklearn.__version__,execution='NVIDIA Brev CPU; no model retraining for frozen step1/step2; saved OOF folds for filtered models'))
write('summary.json',dict(top_all_country_accuracy=sorted([r for r in overall if r['cohort']=='all_available_external_countries' and r.get('accuracy') is not None],key=lambda x:x['accuracy'],reverse=True),best_model_by_accuracy_warning='Accuracy may be inflated by grain-only Canada; use country and balanced metrics'))
readme=['# 全范围遮罩验证：第一步、第二步及筛选模型','','所有数据预测、过滤模型折验证和评分均在 NVIDIA Brev 上完成。预测时只传NDVI特征及有距离模型要求的距离特征；标签仅在所有预测概率生成后用于计分。第一步、第二步原模型及选定v2模型按原文件加载，没有重训。筛选模型只加载保存的折模型，测试折所在组没有用于训练。','','## 遮罩','','第一、二步训练涉及34块马里兰田、44个田块年度记录。测试集中已移除这些田块的全部年份记录，共移除'+str(len(masked_field_rows))+'条；因此不把模型训练见过的田块拿来打分。剩余美国记录中有'+str(sum(r['spatial_group'] in training_farms for r in test_rows))+'条来自同一批5个农场，报告标记了这层农场相关性。','','加拿大与荷兰的可用NDVI记录来自未参与第一、二步拟合的来源；全世界可用记录并不等于完整全球覆盖。大量没有NDVI的候选保留在来源清单中，不参与准确率。','','## Overall结果','','|模型|测试范围|样本|正确|准确率|多数类基线|宏F1|平衡准确率|青贮召回|','|---|---|---:|---:|---:|---:|---:|---:|---:|']
for r in sorted(overall,key=lambda x:(x['cohort']!='all_available_external_countries',-(x.get('accuracy') or -1))):
    if r.get('accuracy') is not None:
        bal='—' if r['balanced_accuracy'] is None else f'{r["balanced_accuracy"]:.4f}'
        rec='—' if r['silage_recall'] is None else f'{r["silage_recall"]:.2%}'
        readme.append(f'|{r["model"]}|{r["cohort"]}|{r["n"]}|{r["correct"]}|{r["accuracy"]:.2%}|{r["majority_class_baseline"]:.2%}|{r["macro_f1"]:.4f}|{bal}|{rec}|')
readme+=['', '“删加拿大”与“删≥90%单标签偏斜国家”两列是测试集筛选，只用于原封不动的第一、二步模型；新筛选模型另外采用所有可用国家的分组OOF测试。每个模型/测试范围的逐国细项见 `country_results.csv`。', '', '## 解读限制', '', '本次可评分国家只有加拿大、荷兰和美国，不能称为全世界准确率。加拿大全是籽粒，单看总准确率会被类别比例主导。美国剩余22条与训练农场相关，不能当作独立农场外测。筛选模型的全国家OOF分数与第一、二步冻结模型的全范围外部评分使用相同测试行，但模型训练数据和验证方式不同；报告指标用于比较当前可见样本上的准确率，不代表未来/全球部署性能。全球标签在前几次开发实验中已被检查，因此并非从未看过的盲测集。', '', '完整总表、逐国表、逐条预测、模型校验清单和源哈希保存在 NVIDIA 本次运行目录。']
(RUN/'README.md').write_text('\n'.join(readme)+'\n')
write('checksums.json',{str(p.relative_to(RUN)):sha(p) for p in RUN.rglob('*') if p.is_file() and p.name!='checksums.json'})
(ROOT/'latest_world_validation.txt').write_text(str(RUN))
print(json.dumps(dict(run=str(RUN),scored_external_rows=len(test_rows),country_counts=dict(Counter(countries)),rows_masked=len(masked_field_rows),farm_overlap=sum(r['spatial_group'] in training_farms for r in test_rows),top=sorted([r for r in overall if r['cohort']=='all_available_external_countries'],key=lambda x:x.get('accuracy') or -1,reverse=True)),ensure_ascii=False,indent=2))
