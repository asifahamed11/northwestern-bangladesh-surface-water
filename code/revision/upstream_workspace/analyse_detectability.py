"""Calendar-position simulation using real method-envelope widths and gaps.

Injected zero-baseline pulses are synthetic, never measured recovery times.
Missing months and calendar-reference failures are never filled.
"""
from pathlib import Path
from datetime import datetime,timezone
import sys,json
import numpy as np
import pandas as pd
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[3];sys.path.insert(0,str(ROOT))
from automatic_water.analyze import audit_downloads,add_envelopes,anomaly_envelopes,interval_recovery
from research_pipeline.common import write_json
P=json.loads((OUT/'FROZEN_REVISION_PROTOCOL.json').read_text(encoding='utf-8'))
spec=dict(frozen_utc=datetime.now(timezone.utc).isoformat(),
 simulations='All 120 monthly onset positions, 2015-2024, each region/cohort; zero-baseline synthetic anomaly with rectangular negative pulse and abrupt return at its end.',
 widths='Real anomaly-envelope half-widths from fixed 2015-2021 calendar references, minimum five observed samples; widths/dates/gaps preserved.',
 deficit_units='fraction of historical cohort area; not proportional storage loss',
 tolerance=.02,pre_event_months=3,confirmation_months=2,horizon_months=24,
 true_simulated_recovery_months=0,
 zero_control='No injected pulse. False-positive and interpretable denominators retained separately.',
 interpretation='Conditional method detectability and continuity only; not calibrated power, real water accuracy or an observed event recovery.')
(OUT/'DETECTABILITY_PROTOCOL_ADDENDUM.json').write_text(json.dumps(spec,indent=2),encoding='utf-8')
raw,settings,hashes=audit_downloads(ROOT/'NW_Bangladesh_automatic_water_2015_2024')
write_json(OUT/'detectability_source_hashes.json',hashes)
radar=add_envelopes(raw);records=[];continuity=[]
for (region,group),frame in radar.groupby(['region','water_group']):
 lo,hi,ref=anomaly_envelopes(frame)
 radius=(hi-lo)/2
 assert np.all(radius.dropna()>=-1e-10)
 for onset in radius.index:
  for duration in P['detectability']['durations_months']:
   end=onset+duration
   pre=pd.period_range(onset-3,onset-1,freq='M')
   phase=pd.period_range(onset,end,freq='M')
   required=pd.period_range(onset-3,end+1,freq='M')
   complete=bool(radius.reindex(required).notna().all())
   continuity.append(dict(region=region,water_group=group,onset_period=str(onset),duration_months=duration,
       required_months=len(required),supported_months=int(radius.reindex(required).notna().sum()),
       pre_event_complete=bool(radius.reindex(pre).notna().all()),
       drought_complete=bool(radius.reindex(phase).notna().all()),
       through_two_month_confirmation_complete=complete))
   for deficit in P['detectability']['deficit_fractions']:
    signal=pd.Series(0.,index=radius.index)
    signal.loc[(signal.index>=onset)&(signal.index<end)]=-deficit
    a=signal-radius;b=signal+radius
    event=dict(onset_period=onset,end_period=end,minimum_spi=np.nan,status='SIMULATED_RECTANGULAR_PULSE',left_censored=False)
    result=interval_recovery(event,a,b,tolerance=.02,horizon=24,baseline_months=3,confirmation=2)
    detected=result.get('deficit_lower',np.nan)>.02
    records.append(dict(region=region,water_group=group,duration_months=duration,injected_deficit_fraction=deficit,
         synthetic_truth_recovery_months=0,continuity_through_confirmation=complete,
         detectable_deficit_within_declared_envelope=bool(detected),
         recovery_interval_contains_synthetic_truth=bool(result.get('recovery_min_months',np.nan)<=0<=result.get('recovery_max_months',np.nan)),
         **result))
 print('Detectability:',region,group,flush=True)
r=pd.DataFrame(records);c=pd.DataFrame(continuity)
r['detected_with_continuity']=r.detectable_deficit_within_declared_envelope & r.continuity_through_confirmation
r.to_csv(OUT/'tables/simulated_detectability_records.csv',index=False)
c.to_csv(OUT/'tables/simulated_continuity_records.csv',index=False)
summary=r.groupby(['region','water_group','duration_months','injected_deficit_fraction']).agg(
 onset_positions=('onset_period','size'),continuity_eligible_positions=('continuity_through_confirmation','sum'),
 detected_deficits=('detectable_deficit_within_declared_envelope','sum'),
 detected_with_continuity=('detected_with_continuity','sum'),
 intervals_covering_synthetic_truth=('recovery_interval_contains_synthetic_truth','sum')).reset_index()
summary['detected_fraction_all_positions']=summary.detected_deficits/summary.onset_positions
summary['detected_fraction_continuity_eligible']=summary.detected_with_continuity/summary.continuity_eligible_positions.replace(0,np.nan)
summary.to_csv(OUT/'tables/simulated_detectability_summary.csv',index=False)
r.groupby(['region','water_group','duration_months','injected_deficit_fraction','status']).size().rename('records').reset_index().to_csv(OUT/'tables/simulated_detectability_status_counts.csv',index=False)
write_json(OUT/'DETECTABILITY_COMPLETE.json',dict(status='SIMULATION_COMPLETED',records=len(r),
 actual_observed_recovery_created=False,synthetic_gap_filling=False,
 zero_control_false_positive_deficits=int(r.loc[r.injected_deficit_fraction.eq(0),'detectable_deficit_within_declared_envelope'].sum())))
print('PASS: real dates/support preserved; simulations kept separate from observations.',flush=True)
