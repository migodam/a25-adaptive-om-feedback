"""Paid final scientific decision from existing development evidence only."""
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
    p = argparse.ArgumentParser(); p.add_argument('--job', required=True)
    args = p.parse_args(); cfg = read(ROOT/'configs/a25/campaign.json')
    with charged_job(ROOT,args.job,config=cfg,metadata={'stage':'final_scientific_decision'}) as book:
        learning = ROOT/'results/a25/learning'
        if any((learning/name).exists() for name in ('TRAINED_MODELS.json','MODEL_FREEZE.json','LOCKED_OPEN.json')):
            raise RuntimeError('UNEXPECTED_LEARNING_ARTIFACT_REQUIRES_FRESH_SCIENTIFIC_REVIEW')
        # Explicitly adopt the latest completed cost-only attempt; divergent
        # remote traces remain preserved rather than silently overwritten.
        expected = 'a25-gpu-health-blocking-003'
        choices = []
        for path in (ROOT/'results/a25').rglob('COST_SELECTED_UPDATES.json'):
            value = read(path)
            if value.get('health_job') == expected:
                choices.append((path,value))
        if not choices or any(v != choices[0][1] for _,v in choices):
            raise RuntimeError('LATEST_COMPLETED_COST_EVIDENCE_NOT_UNIQUE')
        source, choice = choices[0]
        raw_health = []
        from a25.training import select_update_budget
        runtime_config=read(ROOT/'configs/a25/nn_blocking_wait.json')
        for path in (ROOT/'results/a25').rglob('GPU_HEALTH.json'):
            value=read(path)
            predicted=select_update_budget(value,config=runtime_config,cpu_available=choice['available_cpu_seconds'],
                                            gpu_available=choice['available_gpu_seconds'])
            if predicted['candidates']==choice['candidates']:
                raw_health.append((path,value))
        if not raw_health or any(v != raw_health[0][1] for _,v in raw_health):
            raise RuntimeError('LATEST_HEALTH_INDEX_NOT_UNIQUE')
        previous=read(learning/'COST_SELECTED_UPDATES.json')
        archive=learning/'health_attempts'/previous['health_job'];archive.mkdir(parents=True,exist_ok=True)
        for name in ('COST_SELECTED_UPDATES.json','GPU_HEALTH.json'):
            if not (archive/name).exists(): (archive/name).write_bytes((learning/name).read_bytes())
        write_json(learning/'COST_SELECTED_UPDATES.json',choice)
        write_json(learning/'GPU_HEALTH.json',raw_health[0][1])
        write_json(learning/'HEALTH_INDEX_PROVENANCE.json',{'adopted_job':expected,
            'cost_source':source.relative_to(ROOT).as_posix(),
            'health_source':raw_health[0][0].relative_to(ROOT).as_posix(),
            'old_attempts_retained':True,'reason':'explicit adoption of completed runtime-only attempt'})
        with book.span('four_parent_paired_development_bootstrap',bootstrap_replicates=2000):
            summaries=[]
            rng=np.random.default_rng(251008+925)
            for experiment in ('frozen_optimizer_repair','tv_multiplier_0p1','amplitude_1p8'):
                with (ROOT/'results/a25/development'/experiment/'METRICS.csv').open(newline='') as f:
                    rows=list(csv.DictReader(f))
                last=[r for r in rows if int(r['K'])==12]
                parents=sorted({int(r['parent_id']) for r in last})
                per=[]
                for parent in parents:
                    group={m:[r for r in last if int(r['parent_id'])==parent and r['method']==m]
                           for m in ('L','F','TASK_R32')}
                    expected_count=4 if experiment=='amplitude_1p8' else 8
                    if any(len(v)!=expected_count or any(r['status']!='OK' for r in v) for v in group.values()):
                        raise RuntimeError('INCOMPLETE_PARENT_PAIR_CANNOT_BE_FILTERED')
                    means={m:float(np.mean([float(r['delta_nrmse']) for r in v])) for m,v in group.items()}
                    per.append({'parent_id':parent,**means,'relative_F_gain':1-means['F']/means['L']})
                gains=np.array([r['relative_F_gain'] for r in per])
                draws=rng.integers(0,len(per),size=(2000,len(per)))
                interval=np.quantile(gains[draws].mean(axis=1),[.025,.975])
                summaries.append({'experiment':experiment,'K':12,'parent_count':len(per),
                    'parent_mean_relative_F_gain':float(gains.mean()),
                    'paired_parent_bootstrap_95_percent':interval.tolist(),'parents':per,
                    'scope':'descriptive four exposed development parents; no formal holdout claim'})
            write_json(ROOT/'results/a25/development/PAIRED_PARENT_BOOTSTRAP.json',summaries)
        health=read(ROOT/'results/a25/development/phase0/DECISION.json')
        admission=read(ROOT/'results/a25/development/frozen_optimizer_repair/NN_CLOSURE_ADMISSION.json')
        history=budget_history(ROOT)
        decision={
          'status':'HOLD','protocol_id':cfg['protocol_id'],'source_commit':cfg['source_commit'],
          'scientific_scope':'2D scalar TM, 24x24, four historically exposed development parents',
          'gates':{
            'solver_health':{'status':'PASS','selected':health['solver'],'required_problems':14,
                'certified_problems':14,'independent_references':6,'tolerances_unchanged':True,
                'cause':'old iteration ceiling / slow dual fixed-point convergence; accelerated candidate not fastest'},
            'feedback_imaging':{'status':'PARTIAL','original_K12_equal_parent_L_delta_nrmse':.8037251184170493,
                'original_K12_equal_parent_F_delta_nrmse':.7579170985655044,
                'aggregate_relative_gain':1-.7579170985655044/.8037251184170493,
                'threshold':.10,'weak_background_amplitude1p2_parent_mean_gain':.1588612407424314,
                'regime_confirmation':'DEVELOPMENT_HYPOTHESIS_ONLY','independent_validation':'NOT_RUN'},
            'feedback_compression':{'status':'PASS_DECLARED_DEVELOPMENT_SCOPE','selected':admission['selected'],
                'source':'development/frozen_optimizer_repair/NN_CLOSURE_ADMISSION.json',
                'scope_correction':'task audits cover 32 historically exposed K12 endpoints only, not all intermediate trajectory states',
                'learned_state_or_OOD_accuracy':'NOT_ESTABLISHED','deployment_acceleration':'NOT_ESTABLISHED'},
            'learning':{'status':'NOT_RUN','reason':'complete matched 11-model minimum-500-update CPU projection exceeds frozen allowance and total remaining CPU',
                'minimum_updates':500,'projected_cpu_seconds':choice['candidates'][0]['projected_cpu_seconds'],
                'projected_gpu_seconds':choice['candidates'][0]['projected_gpu_seconds'],
                'host_cpu_allowance_seconds':choice['available_cpu_seconds'],
                'GPU_healthy':True,'checkpoint_count':0,'scientific_training_updates':0},
            'sample_efficiency':{'status':'NOT_RUN'},'OOD':{'status':'NOT_RUN'},
            'depth_reduction':{'status':'NOT_RUN'},
            'locked_validation':{'status':'CLOSED_NOT_RUN','truth_opened':False},
            'deployment':{'status':'NOT_ESTABLISHED','original_quality_hits':0,'original_conditions':32,
                'tv0p1_F_quality_hits':1,'tv0p1_conditions':32,
                'reason':'no complete paired common-quality regime; no trained-network endpoint latency'},
          },
          'NN_N0_status':'migration implementation, not official author code; accuracy NOT_RUN',
          'no_3d_no_128_no_large_training':True,'new_clean_labels':history['reservations'].get('new_full_forward_labels'),
          'physical_2d_data':{'new_train_validation_ID_OOD_parents':112,'new_shared_clean_states':448,
              'extra_development_states':8,'training_labels_not_used_for_learning':True,
              'new_labels_have_fixed_passive_complex_phase':True},
          'runtime_profile':{'source':'jobs/a25-gpu-profile-retry-005/PROFILE_UPDATE.json',
              'known_background_only':True,'profiled_N2b3_wall_seconds':1.1963355999905616,
              'profiled_N2b3_cpu_seconds':1.125,'budget_check_cumulative_profile_wall_seconds':.2552305,
              'cProfile_times_non_additive_and_not_CPU_component':True,
              'telemetry_removal_alone_has_no_evidence_for_complete_matrix_fit':True},
          'next_stage':{'decision':'HOLD_LEARNING_AND_DEPLOYMENT_CLAIMS',
              'recommendation':'validate the narrow weak-background feedback regime on independent parents; improve complete differentiated runtime before authorizing a fair NN pilot',
              'automatic_expansion':False},
          'publication_status':'LOCAL_REVIEW_THEN_PUBLICATION',
          'accounting_snapshot':{'cpu_seconds':history['cpu_seconds'],'gpu_seconds':history['gpu_seconds'],
              'cutoff':'completed jobs before final decision job; final immutable receipts remain authoritative'},
        }
        write_json(ROOT/'results/a25/A25_GATE_DECISION.json',decision)
        write_json(learning/'NOT_RUN_DECISION.json',decision['gates']['learning'])
        write_json(ROOT/'results/a25/jobs'/args.job/'result.json',{'status':'DECISIONS_SAVED','NN':'NOT_RUN','locked':'CLOSED'})
        print(json.dumps({'status':'DECISIONS_SAVED','NN':'NOT_RUN','locked':'CLOSED',
                          'minimum_matrix_cpu_seconds':choice['candidates'][0]['projected_cpu_seconds']}))

if __name__=='__main__':main()
