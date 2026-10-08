"""Parent-owned, metered review of the preregistered no-NN regime check."""
from __future__ import annotations
import time
START_WALL, START_CPU = time.perf_counter(), time.process_time()
import argparse
import csv
import json
from pathlib import Path
import numpy as np
from a25.budget import charged_job, write_json, budget_history

ROOT = Path(__file__).resolve().parents[1]

def read(path):
    return json.loads(path.read_text())

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--job',required=True)
    args=parser.parse_args()
    config=read(ROOT/'configs/a25/campaign.json')
    with charged_job(ROOT,args.job,config=config,metadata={'stage':'prospective_scientific_review'}) as book:
        book.started_wall=min(book.started_wall,START_WALL)
        book.started_cpu=min(book.started_cpu,START_CPU)
        directory=ROOT/'results/a25/development/prospective_regime_validation'
        summary=read(directory/'SUMMARY.json')
        provenance=read(directory/'PROVENANCE.json')
        if (summary['status']!='COMPLETE' or not summary['full_method_matrix_complete']
                or not summary['task_audit_K12_complete'] or summary['failures']):
            raise RuntimeError('INCOMPLETE_MATRIX_REQUIRES_HOLD_WITHOUT_SUCCESS_FILTER')
        primary=summary['primary']
        if primary['paired_parents']!=16 or primary['expected_parents']!=16 or not primary['coverage_complete']:
            raise RuntimeError('ALL_FROZEN_PARENT_PAIRS_REQUIRED')
        with (directory/'TASK_AUDIT.csv').open(newline='') as handle:
            tasks=list(csv.DictReader(handle))
        with (directory/'CHECKPOINT_METRICS.csv').open(newline='') as handle:
            checkpoints=list(csv.DictReader(handle))
        if len(tasks)!=32 or any(row['status']!='OK' for row in tasks):
            raise RuntimeError('FULL_TASK_AUDIT_COVERAGE_REQUIRED')
        task_metrics={
          'max_transfer_error':max(float(row['independent_transfer_error']) for row in tasks),
          'max_adjoint_error':max(float(row['independent_adjoint_error']) for row in tasks),
          'min_gradient_cosine':min(float(row['gradient_cosine']) for row in tasks),
          'max_state_data_error':max(float(row['independent_state_data_error']) for row in tasks),
        }
        last=[row for row in checkpoints if int(row['K'])==12]
        by_case={}
        for row in last:
            by_case.setdefault(row['case_id'],{})[row['method']]=row
        if len(by_case)!=32 or any(set(v)!=set(provenance['methods']) for v in by_case.values()):
            raise RuntimeError('FULL_FINAL_PAIR_MATRIX_REQUIRED')
        task_metrics['max_material_error_ratio_to_F']=max(float(v['TASK_R32']['delta_nrmse'])/float(v['F']['delta_nrmse']) for v in by_case.values())
        task_pass=(task_metrics['max_transfer_error']<=.05 and task_metrics['max_adjoint_error']<=.05
                   and task_metrics['min_gradient_cosine']>=.99 and task_metrics['max_material_error_ratio_to_F']<=1.05)
        task_metrics['status']='PASS_FIXED_K12_ENDPOINTS' if task_pass else 'FAIL_FIXED_K12_ENDPOINTS'
        task_metrics['scope']='32 weak-background amplitude1.2 K12 estimates; not intermediate or neural/OOD states'
        quality_hits={m:sum(v[m]['quality_target_hit']=='True' for v in by_case.values()) for m in provenance['methods']}
        values={r['method']:r for r in summary['parent_equal'] if r['K']==12 and r['metric']=='delta_nrmse'}
        parent_gain={key:1-values['F']['parent_values'][key]/value for key,value in values['L']['parent_values'].items()}
        families={family:float(np.mean([parent_gain[str(p)] for p in provenance['parent_ids']
                        if provenance['parent_families'][str(p)]==family]))
                  for family in sorted(set(provenance['parent_families'].values()))}
        result={
          'status':'POSITIVE_NARROW_REGIME_PARTIAL_THRESHOLD_CONFIRMATION',
          'role':provenance['role'],'source':'development/prospective_regime_validation/SUMMARY.json',
          'K':12,'tv_multiplier':.1,'background':'weak','amplitude':1.2,'paired_parents':16,
          'F_vs_L_parent_mean_relative_gain':primary['point_estimate'],'ci95':primary['ci95'],
          'point_target_status':summary['hypothesis_point_target_status'],
          'positive_improvement_supported':primary['ci95'][0]>0,
          'minimum_10_percent_improvement_confirmed':primary['ci95'][0]>=.1,
          'family_parent_mean_relative_gains':families,
          'parent_equal_delta_nrmse':{m:r['parent_equal_mean'] for m,r in values.items()},
          'ratio_of_parent_equal_mean_gain':1-values['F']['parent_equal_mean']/values['L']['parent_equal_mean'],
          'estimands_distinguished':'primary mean of paired parent-relative gains; secondary ratio of mean errors',
          'compression':task_metrics,'joint_quality_hits_out_of_32':quality_hits,
          'NN':'NOT_RUN','locked_ID_OOD':'CLOSED','validation_now_exposed':True,'new_clean_labels':0,
          'speed_advantage':'NOT_ESTABLISHED; descriptive per-image times are not matched cold/warm evidence',
        }
        write_json(directory/'PARENT_REVIEW.json',result)
        decision_path=ROOT/'results/a25/A25_GATE_DECISION.json'
        decision=read(decision_path)
        decision['scientific_scope']='24x24 2D TM; four historically exposed development parents plus sixteen prospectively checked validation parents in a narrow frozen regime'
        feedback=decision['gates']['feedback_imaging']
        feedback['independent_validation']='COMPLETE_PROSPECTIVE_NO_NN_REGIME_CHECK; validation/development, not locked NN test'
        feedback['regime_confirmation']='POSITIVE_IMPROVEMENT; mean10percent point target met; CI does not establish minimum10percent'
        feedback['prospective_regime']=result
        compression=decision['gates']['feedback_compression']
        compression['historical_development_status']='PASS_DECLARED_DEVELOPMENT_SCOPE'
        compression['status']='PARTIAL_DEVELOPMENT_PASS_VALIDATION_FAIL' if not task_pass else 'PASS_FIXED_ENDPOINT_SCOPES_ONLY'
        compression['prospective_fixed_endpoint_check']=task_metrics
        if not task_pass:
            decision['gates']['learning']['additional_numerical_constraint']='prospective TASK_R32 gradient cosine fails0.99; this candidate is not admitted in the newly checked range'
        decision['gates']['deployment']['prospective_joint_quality_hits']=quality_hits
        decision['next_stage']['recommendation']='Feedback has a reproducible positive narrow-regime imaging signal. Retain PARTIAL/HOLD for uniform ten-percent, learning and deployment claims. TASK_R32 fails the new-range gradient-cosine gate: repair and validate this before a new NN pilot, and separately reduce full differentiated host-CPU cost. Do not reopen exposed validation as untouched test.'
        decision['accounting_snapshot']={**{k:budget_history(ROOT)[k] for k in ('cpu_seconds','gpu_seconds')},
            'cutoff':'completed receipts before prospective review tail; immutable terminal receipts are authoritative'}
        write_json(decision_path,decision)
        (ROOT/'research/development/PROSPECTIVE_REGIME_RESULT.md').write_text(
            '# 冻结假设的有界无网络检查\n\n'
            '| 字段 | 记录 |\n|---|---|\n'
            '| Hypothesis | 弱背景、幅度1.2、共同TV×0.1、K12，F相对L的parent平均相对delta误差收益至少10%。 |\n'
            '| Motivating evidence | 四个历史development parents的该regime平均收益16.03%；这仅用于提出假设。 |\n'
            '| Proposed modification | 不改变求解器或物理；复用新数据集中16个validation parents，固定L/F/TASK_R32及原噪声。 |\n'
            '| Development experiment | configs/a25/regime_validation.json在运行前冻结；32观测×3臂×12，零新clean labels，50.31685CPU秒。 |\n'
            '| Observed result | 16parents完整。F/L平均相对收益10.517%，95%区间6.594%–15.316%；TASK_R32最小梯度余弦0.975687，未过0.99。 |\n'
            '| Decision | 正向窄regime收益支持；至少10%仍PARTIAL，压缩新范围FAIL，无NN/部署结论；不自动扩大。 |\n'
            '| New cost | 复用已计费标签，新估计材料full-wave审核、构基、prox、I/O与bootstrap全部在prospective-regime-validation-001收费；本审阅另计。 |\n'
            '| Validation eligibility | validation已暴露并成为开发证据。ID/OOD保持关闭；这些对象不能再次称为untouched test。 |\n\n'
            '原始文件：results/a25/development/prospective_regime_validation/SUMMARY.json、PARENT_REVIEW.json、EXPOSURE.json。'
            '主统计为逐parent相对收益的均值；均值误差比另为9.418%，两者不混用。\n',encoding='utf-8')
        write_json(ROOT/'results/a25/jobs'/args.job/'result.json',result)
        print(json.dumps(result,ensure_ascii=False,allow_nan=False))

if __name__=='__main__': main()
