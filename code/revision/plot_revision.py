"""Truthful manuscript figures from frozen observational and revision tables."""
from pathlib import Path
import json,hashlib,textwrap
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from PIL import Image
import argparse
ROOT=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
P=args.output.resolve();assert not P.exists(),'Choose a new output directory'
assert P!=ROOT and not any(P.is_relative_to(ROOT/x) for x in ['code','data','figures','manuscript','provenance','.git'])
(P/'Figures').mkdir(parents=True);(P/'setup').mkdir()
OUT=ROOT/'data/revision';T=OUT/'tables'
manifest=json.loads((ROOT/'provenance/figure_manifest.json').read_text(encoding='utf-8'))
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.titlesize':10,'axes.labelsize':9,
 'xtick.labelsize':8.5,'ytick.labelsize':8.5,'legend.fontsize':8.5,'axes.spines.top':False,
 'axes.spines.right':False,'axes.linewidth':.8,'lines.linewidth':2,'svg.fonttype':'none','savefig.facecolor':'white'})
BLUE='#0072B2';ORANGE='#D55E00';GREEN='#009E73';GRAY='#666666'
models=['monsoon','monsoon_observation_processing','original_full_control']
model_names=['Monsoon rainfall','Monsoon + observation + step','Annual climate + observation + step']
model_colors=[BLUE,ORANGE,GREEN]
regions=['All_districts','Naogaon','Chapainawabganj','Rajshahi']
region_names=['Union','Naogaon','Chapainawabganj','Rajshahi']
cohorts=json.loads((OUT/'FROZEN_REVISION_PROTOCOL.json').read_text())['cohorts']

def panel(ax,label,title):ax.set_title(label+'  '+textwrap.fill(title,30),loc='left',fontweight='bold',pad=9)
def finish(fig,n,inputs):
 item=manifest[n-1];path=P/'Figures'/item['png']
 for suffix in ['.png','.svg','.pdf']:fig.savefig(path.with_suffix(suffix),dpi=320)
 with Image.open(path) as im:im.convert('RGB').save(path.with_suffix('.tiff'),dpi=(320,320),compression='tiff_lzw');item['pixels']=list(im.size)
 item['pre_revision_png_sha256']=json.loads((ROOT/'provenance/figure_manifest_v020.json').read_text(encoding='utf-8'))[n-1]['final_png_sha256']
 item['final_png_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
 item['final_tiff_sha256']=hashlib.sha256(path.with_suffix('.tiff').read_bytes()).hexdigest()
 item['revision_inputs']=[{'path':str(x),'sha256':hashlib.sha256(x.read_bytes()).hexdigest()} for x in inputs]
 item['rendering']='Recomputed exploratory revision; original inputs retained. 320 dpi RGB, original vector export.'
 plt.close(fig)

# Figure 3: gross majority transitions and static landscape context.
f=T/'static_context_majority_transitions.csv';q=pd.read_csv(f)
q=q[q.cohort.eq(cohorts[0])&q.region.eq('All_districts')&q.buffer_m.eq(500)]
a=q.groupby(['first_majority_class','last_majority_class']).area_km2.sum().unstack(fill_value=0)
matrix=a.loc[[1,2,3],[1,2,3]].to_numpy();ambiguous=q.loc[q.first_majority_class.eq(0)|q.last_majority_class.eq(0),'area_km2'].sum()
fig,axes=plt.subplots(1,2,figsize=(7.1,4.0),layout='constrained',gridspec_kw={'width_ratios':[1,1.15]})
ax=axes[0];panel(ax,'A','Majority source-class transitions')
ax.imshow(matrix,cmap='Blues',vmin=0,vmax=matrix.max())
for i in range(3):
 for j in range(3):ax.text(j,i,f'{matrix[i,j]:.1f}',ha='center',va='center',fontsize=10,color='white' if matrix[i,j]>matrix.max()*.6 else 'black')
ax.set_xticks(range(3),['Nonwater','Seasonal','Permanent'],rotation=30,ha='right')
ax.set_yticks(range(3),['Nonwater','Seasonal','Permanent'])
ax.set_xlabel('2017–2021 class');ax.set_ylabel('2000–2004 class')
f2=T/'static_context_window_changes.csv';c=pd.read_csv(f2)
c=c[c.cohort.eq(cohorts[0])&c.region.eq('All_districts')&c.source_class.eq('seasonal')&c.window_years.eq(5)]
ax=axes[1];panel(ax,'B','Seasonal change by static context')
names=['near_mapped_river','far_2020_cropland','far_2020_other']
for y,name in enumerate(names):
 v=c[c.context.eq(name)].set_index('buffer_m').change_km2
 ax.plot([v.min(),v.max()],[y,y],color=GRAY,lw=2)
 ax.scatter(v.loc[[200,500,1000]],[y]*3,c=[GRAY,BLUE,GRAY],marker='o',s=[24,55,24],zorder=3)
 ax.annotate(f'{v.loc[500]:+.1f}',(v.loc[500],y),xytext=(0,11),textcoords='offset points',ha='center',fontsize=9)
ax.axvline(0,color='black',lw=1);ax.set_yticks(range(3),['River corridor','Away: crop (2020)','Away: other (2020)']);ax.invert_yaxis();ax.set_ylim(2.65,-.65)
ax.set_xlabel('Seasonal change (km²)\nFinal five-year mean minus initial mean')
finish(fig,3,[f,f2])

# Figure 4: smaller climate models and two approximate uncertainty methods.
f=T/'model_status_revision.csv';s=pd.read_csv(f);b=pd.read_csv(T/'block_bootstrap_revision.csv')
s=s[s.cohort.eq(cohorts[0])&s.scope.eq('primary')&s.hac_lag.eq(2)]
b=b[b.cohort.eq(cohorts[0])&b.scope.eq('primary')&b.block_length.eq(3)]
fig,axes=plt.subplots(1,2,figsize=(7.1,4.5),layout='constrained',sharey=True)
for ax,cls,label in zip(axes,['seasonal','permanent'],['A','B']):
 panel(ax,label,cls.title()+' source class')
 for m,model in enumerate(models):
  for y,r in enumerate(regions):
   row=s[s.region.eq(r)&s.source_class.eq(cls)&s.model.eq(model)].iloc[0]
   boot=b[b.region.eq(r)&b.source_class.eq(cls)&b.model.eq(model)].iloc[0]
   pos=y+(m-1)*.22
   ax.plot([boot.lower95,boot.upper95],[pos+.05]*2,color=model_colors[m],lw=2,ls=':')
   ax.plot([row.lower95,row.upper95],[pos-.02]*2,color=model_colors[m],lw=2)
   ax.scatter(row.slope,pos-.02,color=model_colors[m],marker=['o','s','^'][m],s=28,zorder=3)
 ax.axvline(0,color='black',lw=1);ax.set_xlabel('Time coefficient (logit share / year)');ax.set_yticks(range(4),region_names);ax.set_ylim(3.55,-.65);ax.grid(axis='x',alpha=.18)
fig.legend([Line2D([],[],color=c,marker=m,lw=2) for c,m in zip(model_colors,['o','s','^'])],model_names,loc='outside lower center',ncol=1,frameon=False)
fig.suptitle('Solid: 95% calendar HAC (lag 2)   ···: residual block bootstrap (length 3)',fontsize=9)
finish(fig,4,[f,T/'block_bootstrap_revision.csv'])

# Figure 5: all declared cohort/window choices, matched months, and fair CV.
w=pd.read_csv(T/'endpoint_window_changes_revision.csv');m=pd.read_csv(T/'calendar_matched_support.csv');cv=pd.read_csv(T/'chronological_cv_matched_fold_summary.csv')
fig,axes=plt.subplots(2,2,figsize=(7.1,6.5),layout='constrained')
ax=axes[0,0];panel(ax,'A','Union seasonal window comparisons')
for k,(width,color,mark) in enumerate(zip([1,3,5],[BLUE,ORANGE,GREEN],['o','s','^'])):
 v=w[w.region.eq('All_districts')&w.source_class.eq('seasonal')&w.window_years.eq(width)].set_index('cohort').reindex(cohorts)
 ax.scatter(v.percent_change,np.arange(7)+(k-1)*.18,color=color,marker=mark,s=28,label=f'{width}-year')
ax.set_yticks(range(7),[f'C{i}' for i in range(1,8)]);ax.invert_yaxis();ax.set_xlabel('Change from first to final window (%)');ax.axvline(0,color='black',lw=1);ax.grid(axis='x',alpha=.18);ax.legend(frameon=False,ncol=3,columnspacing=.5,handletextpad=.2,loc='upper center',bbox_to_anchor=(.5,-.17))
ax=axes[0,1];panel(ax,'B','Same-calendar support across 22 years')
v=m[m.region.eq('All_districts')].sort_values('month')
ax.bar(v.month,v.retained_fraction*100,color=[GREEN if x else BLUE for x in v.eligible],width=.72)
ax.scatter(v.month[v.retained_fraction.eq(0)],np.zeros(v.retained_fraction.eq(0).sum()),marker='x',s=20,c=GRAY,zorder=3)
ax.axhline(20,color=GRAY,ls='--',lw=2);ax.set_xticks(range(1,13),list('JFMAMJJASOND'));ax.set_xlabel('Calendar month');ax.set_ylabel('Baseline footprint retained (%)');ax.set_ylim(-1,30)
ax.text(1,27,'20% minimum for fitting',fontsize=8.5,color=GRAY)
ax=axes[1,0];panel(ax,'C','Union seasonal cohort sensitivity')
v=pd.read_csv(f);v=v[v.region.eq('All_districts')&v.source_class.eq('seasonal')&v.scope.eq('primary')&v.model.eq('monsoon_observation_processing')&v.hac_lag.eq(2)].set_index('cohort').reindex(cohorts)
for y,(_,row) in enumerate(v.iterrows()):
 ax.plot([row.lower95,row.upper95],[y,y],color=BLUE,lw=2);ax.scatter(row.slope,y,c=BLUE,s=28)
ax.set_yticks(range(7),[f'C{i}' for i in range(1,8)]);ax.invert_yaxis();ax.axvline(0,color='black',lw=1);ax.set_xlabel('Time coefficient (logit share / year)');ax.grid(axis='x',alpha=.18)
ax=axes[1,1];panel(ax,'D','Chronological hindcast error')
names=['monsoon','monsoon_observation_processing','antecedent_sensitivity','original_full_control']
for j,cls in enumerate(['seasonal','permanent']):
 v=cv[cv.cohort.eq(cohorts[0])&cv.region.eq('All_districts')&cv.source_class.eq(cls)].set_index('model').loc[names]
 ax.scatter(v.rmse/v.mean_benchmark_rmse,np.arange(4)+(j-.5)*.2,c=[BLUE,ORANGE][j],marker=['o','^'][j],s=35,label=cls.title())
ax.axvline(1,color=GRAY,ls='--',lw=2);ax.set_yticks(range(4),['Monsoon (6 years)','+ effort / step (4)','+ antecedent rain (4)','Full controls (4)']);ax.invert_yaxis();ax.set_xlim(0,1.15);ax.set_xlabel('RMSE / matched-fold mean benchmark');ax.legend(frameon=False,loc='upper center',bbox_to_anchor=(.5,-.15),ncol=2)
finish(fig,5,[T/'endpoint_window_changes_revision.csv',T/'calendar_matched_support.csv',f,T/'chronological_cv_matched_fold_summary.csv'])

# Figure 8: seasonal overlap, score-stage audit and class-specific proxy evidence.
parts=[pd.read_csv(ROOT/f'data/inputs/earth_engine_exports/NW_Bangladesh_DW_sensitivity_2015_2024/dw_sensitivity_{year}.csv') for year in range(2015,2025)]
d=pd.concat(parts,ignore_index=True);d=d[d.region.eq('All_districts')&d.water_group.eq('all_water')]
season_rows=[]
for season,months in [('June–September',[6,7,8,9]),('Other months',[1,2,3,4,5,10,11,12])]:
 g=d[d.month.isin(months)]
 for threshold in [50,60,70,80]:
  paired=g[f'dw_t{threshold}_sar_pair_area_km2'].sum();same=g[f'dw_t{threshold}_sar_same_area_km2'].sum()
  season_rows.append(dict(season=season,threshold=threshold/100,paired_support_pct=100*(g[f'dw_t{threshold}_sar_pair_area_km2']/g.domain_area_km2).mean(),conditional_agreement_pct=100*same/paired if paired else np.nan))
season=pd.DataFrame(season_rows);season.to_csv(P/'setup/seasonal_dw_pair_support.csv',index=False)
fig,axes=plt.subplots(2,2,figsize=(7.1,6.3),layout='constrained')
for i,(name,color,mark) in enumerate([('June–September',BLUE,'o'),('Other months',ORANGE,'s')]):
 g=season[season.season.eq(name)]
 axes[0,0].plot(g.threshold,g.paired_support_pct,c=color,marker=mark,label=name)
 axes[0,1].plot(g.threshold,g.conditional_agreement_pct,c=color,marker=mark,label=name)
panel(axes[0,0],'A','Seasonal paired support');axes[0,0].set_ylabel('Mean historical footprint paired (%)');axes[0,0].set_ylim(0,18);axes[0,0].legend(frameon=False)
panel(axes[0,1],'B','Agreement on supported area-time');axes[0,1].set_ylabel('Conditional SAR–DW agreement (%)');axes[0,1].set_ylim(0,103)
for ax in axes[0]:ax.set_xlabel('Monthly probability threshold');ax.set_xticks([.5,.6,.7,.8]);ax.text(.8,3,'no pair',ha='right',fontsize=8.5)
audit=pd.read_csv(T/'dw_browser_stage_audit_202411.csv');ax=axes[1,0];panel(ax,'C','Small-area score-stage audit')
for i,col in enumerate(['raw_water_max','monthly_water_max','raw_land_max','monthly_land_max']):
 vals=audit[col]
 ax.scatter(np.arange(2)+(i-1.5)*.13,vals,marker=['o','s','^','D'][i],c=[BLUE,BLUE,ORANGE,ORANGE][i],s=32,label=['Water: raw max','Water: monthly max','Land: raw max','Land: monthly max'][i])
ax.axhline(.8,color=GRAY,ls='--',lw=2);ax.set_xticks([0,1],['Land context','Stable-water probes']);ax.set_ylabel('Maximum probability in probe');ax.set_ylim(0,.92);ax.legend(frameon=False,fontsize=8.5,loc='lower left',ncol=1)
joint_path=OUT/'batch_completion_20261021/analysis/joint_pilot_pooled.csv'
joint=pd.read_csv(joint_path);ax=axes[1,1];panel(ax,'D','Paired classes: 2018 and 2024')
for comparison,marker,style in [('sar','o','-'),('jrc','^','--')]:
 g=joint[joint.region.eq('All_districts')&joint.water_group.eq('all_water')&joint.comparison.eq(comparison)].sort_values('threshold')
 name='SAR–DW' if comparison=='sar' else 'DW–JRC'
 for metric,color,cls in [('positive_agreement',BLUE,'water'),('negative_agreement',ORANGE,'nonwater')]:
  ax.plot(g.threshold,g[metric]*100,c=color,marker=marker,ls=style,label=name+': '+cls)
ax.set_xlabel('Monthly probability threshold');ax.set_ylabel('Symmetric class agreement (%)')
ax.set_xticks([.5,.6,.7,.8]);ax.set_ylim(0,104);ax.set_xlim(.48,.82)
ax.text(.8,3,'no pair',ha='right',fontsize=8.5)
ax.legend(frameon=False,loc='lower left',fontsize=8.5)
finish(fig,8,[T/'seasonal_dw_pair_support.csv',T/'dw_browser_stage_audit_202411.csv',joint_path])

# Figure 12: actual event accounting and explicitly separate simulated controls.
events=pd.read_csv(ROOT/'data/tables/exploratory_recovery_support_sensitivity.csv')
e=events.groupby(['coverage_gate','minimum_reference_count','status']).size().unstack(fill_value=0)
sim=pd.read_csv(T/'simulated_detectability_summary.csv');u=sim[sim.region.eq('All_districts')&sim.water_group.eq('all_water')]
fig=plt.figure(figsize=(7.1,5.9),layout='constrained');gs=fig.add_gridspec(2,2,height_ratios=[1.25,1])
ax=fig.add_subplot(gs[0,:]);panel(ax,'A','Actual drought records across nine settings')
left=np.zeros(len(e));colors=[GRAY,ORANGE,BLUE]
for status,color in zip(['PRE_EVENT_SUPPORT_OR_REFERENCE_GAP','DROUGHT_SUPPORT_OR_REFERENCE_GAP','DEFICIT_UNCERTAIN_WITHIN_ENVELOPE'],colors):
 vals=e[status] if status in e else np.zeros(len(e));ax.barh(range(len(e)),vals,left=left,color=color,label={'PRE_EVENT_SUPPORT_OR_REFERENCE_GAP':'Pre-event / reference gap','DROUGHT_SUPPORT_OR_REFERENCE_GAP':'Drought / reference gap','DEFICIT_UNCERTAIN_WITHIN_ENVELOPE':'Uncertain deficit'}[status]);left+=vals
ax.set_yticks(range(len(e)),[f'{gate:.2f} / {n}' for gate,n in e.index]);ax.invert_yaxis();ax.set_xlabel('Overlapping event–cohort records (108 per setting)');ax.set_ylabel('Coverage / reference n')
handles,legend_labels=ax.get_legend_handles_labels();ax.legend(handles,['Pre-event gap','Drought gap','Uncertain deficit'],frameon=False,loc='upper center',bbox_to_anchor=(.5,-.28),ncol=3,fontsize=8.5)
ax=fig.add_subplot(gs[1,0]);panel(ax,'B','Simulated pulses: calendar continuity')
vals=u[u.injected_deficit_fraction.eq(0)].sort_values('duration_months');ax.bar(range(3),vals.continuity_eligible_positions,color=BLUE)
for x,v in enumerate(vals.continuity_eligible_positions):ax.text(x,v+.4,str(v),ha='center',fontsize=10)
ax.set_xticks(range(3),['1 month','3 months','6 months']);ax.set_ylabel('Complete positions / 120 starts');ax.set_ylim(0,18);ax.set_xlabel('Injected pulse duration')
ax=fig.add_subplot(gs[1,1]);panel(ax,'C','Simulated pulses: deficit detectability')
for j,duration in enumerate([1,3,6]):
 q=u[u.duration_months.eq(duration)].sort_values('injected_deficit_fraction')
 ax.plot(q.injected_deficit_fraction*100,q.detected_fraction_all_positions*100,marker=['o','s','^'][j],c=[BLUE,ORANGE,GREEN][j],label=f'{duration} month(s)',ls=['-','--',':'][j])
ax.set_xlabel('Injected deficit (percentage points of cohort)');ax.set_ylabel('Detectable deficits / all starts (%)');ax.set_ylim(-1,100);ax.set_xlim(-.5,20.5);ax.legend(frameon=False,loc='upper right');ax.text(10,40,'No tested pulse was confirmed\nGaps and real envelope widths retained',ha='center',fontsize=8.5)
finish(fig,12,[T/'simulated_detectability_summary.csv',ROOT/'data/tables/exploratory_recovery_support_sensitivity.csv'])
(P/'setup/inline_figure_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print('Five replacement scientific figures exported with complete source-table hashes.')

records=[]
for n in [3,4,5,8,12]:
 item=manifest[n-1];a=P/"Figures"/item["png"];b=ROOT/"figures"/item["png"]
 with Image.open(a) as x,Image.open(b) as y:equal=x.size==y.size and x.convert("RGB").tobytes()==y.convert("RGB").tobytes()
 records.append({"figure":n,"same_rendered_pixels":equal})
(P/"FIGURE_REPLAY_REPORT.json").write_text(json.dumps(records,indent=2))
assert all(x["same_rendered_pixels"] for x in records),"Inspect rendering differences"
