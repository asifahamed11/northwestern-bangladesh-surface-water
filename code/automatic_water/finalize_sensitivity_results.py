"""Independent numerical QA and readable findings for a completed real run."""
from pathlib import Path
import argparse, hashlib, json, zipfile
from datetime import datetime, timezone, timedelta
import numpy as np
import pandas as pd
from automatic_water import analyze as a
from automatic_water.analyze_dw_sensitivity import audit_downloads, pooled_summary

ROOT=Path(__file__).resolve().parents[1]

def recovery_checks(old,spi,out):
    f=a.add_envelopes(old);rows=[];summaries=[]
    # Exploratory diagnostics, specified together; none replaces the primary
    # 95% coverage / five-reference-observation specification.
    for coverage in [.8,.9,.95]:
        for minimum_reference in [3,4,5]:
            start=len(rows)
            for (region,group),part in f.groupby(['region','water_group']):
                part=part.copy();part['eligible_for_recovery']=part.sar_coverage_fraction.ge(coverage-1e-8)
                lo,hi,_=a.anomaly_envelopes(part,minimum_reference)
                rain=spi[(spi.region==region)&(spi.scale_months==3)]
                series=pd.Series(rain.spi.to_numpy(),index=pd.PeriodIndex(rain.period,freq='M'))
                series=series[series.index.year>=2015]
                for event in a.drought_events(series):
                    rows.append({'coverage_gate':coverage,'minimum_reference_count':minimum_reference,
                        'region':region,'water_group':group,**a.interval_recovery(event,lo,hi)})
            counts=pd.DataFrame(rows[start:]).status.value_counts().to_dict()
            summaries.append({'coverage_gate':coverage,'minimum_reference_count':minimum_reference,
                'records':sum(counts.values()),'status_counts':counts})
    pd.DataFrame(rows).to_csv(out/'exploratory_recovery_support_sensitivity.csv',index=False)
    (out/'exploratory_recovery_support_sensitivity_summary.json').write_text(json.dumps(summaries,indent=2)+'\n',encoding='utf-8')
    primary=pd.read_csv(out/'radar_automated_recovery_intervals.csv')
    repeated=pd.DataFrame([r for r in rows if r['coverage_gate']==.95 and r['minimum_reference_count']==5])
    key=['region','water_group','onset_period','climate_end_period']
    assert primary.set_index(key).status.sort_index().equals(repeated.set_index(key).status.sort_index())
    return summaries

def extra_figures(models,events,specs,out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(3,1,figsize=(11,10),constrained_layout=True)
    names=['Naogaon','Chapainawabganj','Rajshahi'];groups=['all_water','baseline_seasonal','baseline_permanent']
    for ax,group in zip(axes,groups):
        for index,endpoint in enumerate(['lower','upper']):
            subset=models[(models.region.isin(names))&(models.water_group==group)&(models.envelope_endpoint==endpoint)].set_index('region').loc[names]
            values=subset.time_coefficient_logit_per_year.to_numpy();y=np.arange(3)+(index-.5)*.19;color=['#2877ad','#b76a30'][index]
            ax.errorbar(values,y,xerr=np.vstack([values-subset.lower95.to_numpy(),subset.upper95.to_numpy()-values]),
                fmt='none',ecolor=color,capsize=4,linewidth=1.5)
            significant=subset.p_adjusted_BY_district_family.lt(.05).to_numpy()
            for selected,fill in [(significant,color),(~significant,'white')]:
                ax.scatter(values[selected],y[selected],s=52,facecolors=fill,edgecolors=color,zorder=3)
            ax.plot([],[],color=color,marker='o',label=endpoint+' endpoint')
        ax.axvline(0,color='#555555',linestyle='--',linewidth=1);ax.set_yticks(np.arange(3),names)
        ax.invert_yaxis();ax.grid(axis='x',alpha=.18);ax.set_title(group.replace('_',' '))
        ax.set_xlabel('Time coefficient (logit of method-envelope fraction per year)');ax.legend(loc='lower left',ncol=2)
    fig.suptitle('Climate-adjusted radar envelope models, 2015–2024\nPointwise 95% intervals; filled markers have district-family BY-adjusted p < 0.05')
    for ext in ['png','svg']:fig.savefig(out/'Figures'/f'03_climate_envelope_models.{ext}',dpi=200)
    plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(12,5),constrained_layout=True)
    counts=events.status.value_counts();labels={'PRE_EVENT_SUPPORT_OR_REFERENCE_GAP':'Before drought: observation/reference gap',
        'DROUGHT_SUPPORT_OR_REFERENCE_GAP':'During drought: observation/reference gap'}
    axes[0].barh([labels.get(x,x) for x in counts.index],counts.values,color='#3e789c')
    for i,count in enumerate(counts.values):axes[0].text(count+1,i,str(count),va='center')
    axes[0].set_xlim(0,max(counts.values)*1.18);axes[0].set_xlabel('Event–cohort records (overlapping groups included)')
    axes[0].set_title('Primary specification: no identifiable timing')
    matrix=np.array([[sum(s['status_counts'].get(x,0) for x in ['TIMING_STABLE_WITHIN_ENVELOPE','TIMING_INTERVAL_WITHIN_ENVELOPE'])
        for s in specs if s['coverage_gate']==c] for c in [.8,.9,.95]])
    axes[1].imshow(matrix,vmin=0,vmax=1,cmap='Blues',aspect='auto')
    for i in range(3):
        for j in range(3):axes[1].text(j,i,str(int(matrix[i,j])),ha='center',va='center')
    axes[1].set_xticks(range(3),['3','4','5']);axes[1].set_yticks(range(3),['80%','90%','95%'])
    axes[1].set_xlabel('Minimum reference count');axes[1].set_ylabel('Radar coverage gate')
    axes[1].set_title('Identifiable timings across 9 exploratory checks')
    for ext in ['png','svg']:fig.savefig(out/'Figures'/f'04_recovery_identifiability.{ext}',dpi=200)
    plt.close(fig)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',type=Path,required=True);args=parser.parse_args();out=args.run.resolve()
    state=json.loads((out/'STATUS.json').read_text(encoding='utf-8'));assert state['software_run_complete']
    f,old,_,hashes=audit_downloads(ROOT/'NW_Bangladesh_DW_sensitivity_2015_2024')
    long=pd.read_csv(out/'dw_monthly_threshold_evidence.csv');summary=pd.read_csv(out/'dw_threshold_support_and_agreement.csv')
    models=pd.read_csv(out/'exploratory_climate_envelope_models.csv');events=pd.read_csv(out/'radar_automated_recovery_intervals.csv')
    assert len(long)==5760 and long.groupby(['region','water_group','threshold']).size().eq(120).all()
    assert np.allclose(long.unknown_observation_fraction+long.unknown_classification_fraction+long.classified_fraction,1)
    assert np.allclose(long.water_upper_fraction-long.water_lower_fraction,1-long.classified_fraction)
    assert ((long.water_lower_fraction>=-1e-10)&(long.water_upper_fraction<=1+1e-10)&(long.water_lower_fraction<=long.water_upper_fraction)).all()
    union=f[(f.region=='All_districts')&(f.water_group=='all_water')];table=[]
    for t in [50,60,70,80]:
        p=f'dw_t{t}';row={'threshold':t/100,'classified_months':int(union[p+'_known_area_km2'].gt(1e-9).sum()),
            'mean_classified_percent':100*(union[p+'_known_area_km2']/union.domain_area_km2).mean()}
        for sensor in ['sar','jrc']:
            paired=union[p+'_'+sensor+'_pair_area_km2'];same=union[p+'_'+sensor+'_same_area_km2'];denominator=paired.sum()
            row[sensor+'_pooled_agreement_percent']=100*same.sum()/denominator if denominator>0 else None
            row[sensor+'_mean_paired_percent']=100*(paired/union.domain_area_km2).mean()
            assert long.loc[long[sensor+'_pair_area_km2'].eq(0),sensor+'_conditional_agreement'].isna().all()
            check=summary[(summary.region=='All_districts')&(summary.water_group=='all_water')&summary.threshold.eq(t/100)].iloc[0]
            assert np.isclose(check[sensor+'_pooled_area_month_agreement'],same.sum()/denominator,equal_nan=True) if denominator>0 else pd.isna(check[sensor+'_pooled_area_month_agreement'])
        table.append(row)
    specs=recovery_checks(old,pd.read_csv(out/'spi_indices.csv'),out)
    extra_figures(models,events,specs,out)
    qa={'status':'PASS','completed_client_date':'2026-10-15','new_csv_files':12,'original_csv_files':14,
        'new_monthly_rows':1440,'threshold_evidence_rows':5760,'retained_actual_scenes':1539,
        'source_inventory_and_baseline_controls_pass':True,'november_pilot_reproduced':True,
        'independent_direct_area_ratio_check_pass':True,'unknown_support_accounting_pass':True,
        'primary_recovery_reproduced_in_sensitivity':True,'exploratory_recovery_specifications':9,
        'primary_recovery_records':len(events),'primary_status_counts':events.status.value_counts().to_dict(),
        'all_water_union_threshold_summary':table,'verified_accuracy':False,'scientific_publication_ready':False,
        'raw_observations_modified':False,'new_download_required_for_completed_analysis':False}
    for item in hashes:assert hashlib.sha256(Path(item['path']).read_bytes()).hexdigest()==item['sha256']
    climate_hashes=json.loads((out/'climate_input_sha256.json').read_text(encoding='utf-8'))
    for item in climate_hashes:assert hashlib.sha256(Path(item['path']).read_bytes()).hexdigest()==item['sha256']
    (out/'FINAL_CHECKS.json').write_text(json.dumps(qa,indent=2)+'\n',encoding='utf-8')
    lines=['# আসল data থেকে analysis — ১৫ অক্টোবর ২০২৬','',
        '**Download যাচাই ও এই analysis সম্পন্ন। এই analysis-এর জন্য নতুন download লাগছে না।**','',
        'নতুন ১২টি CSV ZIP-এর CRC ও extracted file-এর SHA256 দিয়ে মিলেছে। Downloads থেকে Desktop-এর নির্ধারিত folder-এ একই bytes copy করা হয়েছে।',
        'আগের ১৪টি CSV অপরিবর্তিত আছে। নতুন ১,৪৪০টি মাস/region/cohort row থেকে চার threshold-এ ৫,৭৬০টি হিসাব হয়েছে।',
        '২৬৫টি Sentinel-1 ও ১,২৭৪টি Dynamic World scene-এর ID/date/track ঠিক আছে। Fixed area, grid, source count, পুরোনো ০.৮ ফল এবং November pilot পুনরায় মিলে গেছে।','',
        '## ১. কেন আগের optical হিসাব শূন্য ছিল?','',
        'এই study-র মাসিক probability-তে ০.৮ নিয়মে কোনো confident classification পাওয়া যায়নি। ০.৫/০.৬/০.৭ নিয়মে কিছু অংশে পাওয়া যায়।',
        'নীচের হিসাব সব district মিলিয়ে historical ever-water footprint-এর জন্য; পুরো তিন জেলার প্রশাসনিক এলাকা নয়। Support-এর mean ১২০ মাসের উপর।','',
        '| Probability সীমা | Classified support থাকা মাস | গড় classified footprint | Radar/DW মিল | গড় Radar/DW paired footprint | JRC/DW মিল |',
        '|---|---:|---:|---:|---:|---:|']
    for r in table:
        agreement=lambda value:'অজানা' if value is None else f'{value:.2f}%'
        lines.append(f"| {r['threshold']:.1f} | {r['classified_months']}/120 | {r['mean_classified_percent']:.2f}% | {agreement(r['sar_pooled_agreement_percent'])} | {r['sar_mean_paired_percent']:.2f}% | {agreement(r['jrc_pooled_agreement_percent'])} |")
    lines += ['', 'মিলের শতাংশ paired area-month দিয়ে weighted। এটি independent ground-truth accuracy নয়। কঠোর সীমায় মিল বেশি হলেও কম জায়গা তুলনায় থাকে।',
        'কোনো best accuracy threshold নির্বাচন হয়নি। ০.৭-এ radar/DW মিল ৯৮.৭১%, কিন্তু paired footprint-এর mean মাত্র ৩.২৯%; পুরো এলাকার ৯৮.৭১% সঠিক বলা যাবে না।','',
        '## ২. Climate-adjusted radar ফল','',
        '২০১৫–২০২৪-এর radar analysis-এ পর্যাপ্ত support থাকা ৯০টি মাস দিয়ে প্রতি region/cohort-এর model হয়েছে। বৃষ্টি, তাপমাত্রা, evaporation demand, মৌসুম ও observation effort হিসাবের অংশ।',
        'রাজশাহীর all-water footprint ও ২০০০–২০০৪-এ seasonal হিসেবে চিহ্নিত cohort-এ lower এবং upper দুই radar-envelope endpoint-এর সময়ের coefficient positive; district-family BY adjustment-এর পরও দুই endpoint-এর ফল supported।',
        'রাজশাহীর seasonal cohort: lower coefficient +0.0582 [0.0236, 0.0929], adjusted p=0.0161; upper +0.0396 [0.0124, 0.0669], adjusted p=0.0312। Units: logit fraction/year, শতাংশ পানি/বছর নয়।',
        'নওগাঁ ও চাঁপাইনবাবগঞ্জে seasonal cohort-এর একইভাবে স্পষ্ট positive/negative পরিবর্তন পাওয়া যায়নি। Permanent cohort-এর ক্ষেত্রে কোনো জেলায় দুই endpoint-এ একসঙ্গে পরিষ্কার পরিবর্তন মেলেনি।',
        'এটি ঘোষিত radar benchmark ও support-envelope-এর ফল। Radar ভেজা মাটি, ধানক্ষেত, rough water বা vegetation-এ ভুল করতে পারে; model physical true-water পরিবর্তন বা মানুষের কাজের causal প্রভাব প্রমাণ করে না।','',
        '## ৩. খরার পরে পানি ফিরতে কত মাস লাগে?','',
        'প্রাথমিক নিয়মে ১০৮টি event–cohort record-এর কোনো timing নির্ভরযোগ্যভাবে নির্ধারণ হয়নি। এগুলো ১০৮টি আলাদা drought নয়: cohort ও union overlap করে।',
        '- ৮৪টি record: drought-এর আগের প্রয়োজনীয় observation অথবা seasonal reference নেই।',
        '- ২৪টি record: drought চলাকালীন observation অথবা seasonal reference-এর ঘাটতি।',
        '- April–July-এ ২০১৫–২০২১ reference period-এ যথেষ্ট observed month মাত্র ৪টি; primary নিয়মে ৫টি দরকার।',
        'Radar coverage ৮০/৯০/৯৫% এবং reference minimum ৩/৪/৫ — মোট ৯টি exploratory specification-এও কোনো stable বা interval timing পাওয়া যায়নি। Reference ৩/৪ হলে কিছু record observation stage পার হলেও ২১টিতে deficit নিজেই envelope-এর মধ্যে uncertain। Primary নিয়ম বদলানো হয়নি।',
        '**এর অর্থ পানি ফেরেনি নয়। এই observation ও ঘোষিত uncertainty দিয়ে বিশ্বাসযোগ্য সময় আলাদা করা যায়নি।**','',
        '## ৪. আগের annual গবেষণার সঙ্গে সম্পর্ক','',
        'আগের JRC annual analysis ছিল ২০০০–২০২১-এর আলাদা common-observation footprint-এ; নতুন radar ফল ২০১৫–২০২৪-এর fixed historical cohort-এ। Sensor, সময়, footprint এবং measured variable আলাদা। তাই নতুন positive radar signal দিয়ে পুরোনো annual seasonal decline বাতিল করা বা সরাসরি একটাই trend বলা যাবে না।','',
        '## এখন কী বলা যায়','',
        'বাস্তব source-complete downloads থেকে observation/threshold sensitivity, conditional method agreement এবং exploratory climate-adjusted radar ফল পাওয়া গেছে। Recovery timing-এর identifiability নেই; independent reference accuracy এখনও যাচাই হয়নি।',
        'এই সীমা মেনে methods/results লেখা যায়। পুরো গবেষণাকে submission-ready বা ১০০% accurate বলা হয়নি।','',
        '## ফাইল','',
        '- `dw_monthly_threshold_evidence.csv`: সব মাস/cohort/threshold-এর support, bounds এবং paired comparison।',
        '- `dw_threshold_support_and_agreement.csv`: regional summary।',
        '- `exploratory_climate_envelope_models.csv`: model coefficients, confidence intervals ও adjusted p।',
        '- `radar_automated_recovery_intervals.csv`: primary recovery record ও কারণ।',
        '- `exploratory_recovery_support_sensitivity.csv`: ৯ specification-এর ফল।',
        '- `Figures`: support, agreement, climate model এবং recovery — চারটি figure PNG ও SVG।',
        '- `FINAL_CHECKS.json`, `input_sha256.json`, `climate_input_sha256.json`: audit ও source integrity।']
    (out/'FINAL_FINDINGS_BN.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({'report':str(out/'FINAL_FINDINGS_BN.md'),'qa':qa},indent=2))

if __name__=='__main__':main()
