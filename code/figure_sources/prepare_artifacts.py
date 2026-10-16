"""Prepare manuscript figures/tables from frozen results, without refitting models."""
from pathlib import Path
import json, hashlib, shutil, sys, csv
from datetime import datetime,timezone
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MPolygon, Patch
from matplotlib.lines import Line2D
from shapely.geometry import shape
from shapely.ops import unary_union
from PIL import Image

sys.stdout.reconfigure(encoding='utf-8')
P=Path(__file__).resolve().parent; ROOT=P.parent
ACTIVE=ROOT/'code_only_final_20261016/analysis_v3_user_label144'
T=ACTIVE/'Tables';F=P/'Figures';S=P/'Supplementary_Data';Q=P/'setup/qa'
for d in (F,S,Q,P/'manuscripts',P/'outputs'):d.mkdir(parents=True,exist_ok=True)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
provenance=[]
def read(name):
 p=T/name;provenance.append(dict(path=str(p),sha256=sha(p)));return pd.read_csv(p)
def save(fig,name):
 fig.savefig(F/(name+'.png'),dpi=320,facecolor='white')
 fig.savefig(F/(name+'.pdf'),facecolor='white')
 fig.savefig(F/(name+'.svg'),facecolor='white')
 with Image.open(F/(name+'.png')) as im:im.convert('RGB').save(F/(name+'.tiff'),dpi=(320,320),compression='tiff_lzw')
 plt.close(fig)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.labelsize':9,'axes.titlesize':10,
 'xtick.labelsize':8,'ytick.labelsize':8,'legend.fontsize':8,'axes.spines.top':False,'axes.spines.right':False,
 'lines.linewidth':2,'savefig.dpi':320,'svg.fonttype':'none'})
colors={'All_districts':'#222222','Naogaon':'#0072B2','Chapainawabganj':'#D55E00','Rajshahi':'#009E73'}
markers_by_region={'All_districts':'o','Naogaon':'^','Chapainawabganj':'s','Rajshahi':'D'}
regions=list(colors);short={'All_districts':'Three-district union',**{r:r for r in regions[1:]}}
annual=read('annual_common_support_water.csv');quality=read('annual_observation_quality.csv')
step=read('annual_observation_effort_climate_sensitivity.csv');end=read('primary_endpoint_changes.csv')
thr=read('dw_threshold_support_and_agreement.csv');proxy=read('proxy_agreement_and_unknown_ranges.csv')
outcomes=read('reference_outcome_accounting.csv');recovery=read('exploratory_recovery_support_sensitivity.csv')

# Figure 1: verified study boundaries plus declared estimands.
geo=ROOT/'NW_Bangladesh_2000_2024/verified_study_area.geojson';country=ROOT/'dataset-download/boundaries/Bangladesh_ADM2_original.geojson'
fc=json.loads(geo.read_text());allfc=json.loads(country.read_text())
provenance += [dict(path=str(p),sha256=sha(p)) for p in (geo,country)]
fig=plt.figure(figsize=(180/25.4,151/25.4),layout='constrained');gs=fig.add_gridspec(2,2,height_ratios=[1.1,1])
ax=fig.add_subplot(gs[0,0]);ax2=fig.add_subplot(gs[0,1]);flow=fig.add_subplot(gs[1,:]);flow.axis('off')
def polys(ax,geom,**kw):
 for poly in (geom.geoms if hasattr(geom,'geoms') else [geom]):ax.add_patch(MPolygon(np.array(poly.exterior.coords),**kw))
for ft in allfc['features']:polys(ax,shape(ft['geometry']),facecolor='#E9ECEF',edgecolor='#FFFFFF',linewidth=.2)
for ft in fc['features']:
 n=ft['properties']['district'];n='Chapainawabganj' if n=='Nawabganj' else n;g=shape(ft['geometry'])
 polys(ax,g,facecolor=colors[n],edgecolor='white',linewidth=.4);polys(ax2,g,facecolor=colors[n],edgecolor='white',linewidth=1)
 pt=g.representative_point();label='Chapai-\nnawabganj' if n=='Chapainawabganj' else n
 ax2.text(pt.x,pt.y,label,color='white',ha='center',va='center',weight='bold',fontsize=9)
ax.set(xlim=(87.7,92.8),ylim=(20.6,26.8),xlabel='Longitude (°E)',ylabel='Latitude (°N)',title='A  Location within Bangladesh')
ax2.set(xlim=(87.9,89.15),ylim=(24.08,25.3),xlabel='Longitude (°E)',ylabel='Latitude (°N)',title='B  Three study districts')
for a in [ax,ax2]:a.set_aspect(1/np.cos(np.deg2rad(24)))
flow.set_title('C  Analysis domains and interpretation',loc='left')
boxes=[(.76,'Primary: 2000–2021','JRC annual source classes; fixed footprint of 1,276.41 km²\nClimate and observation controls'),
       (.47,'Supplement: 2015–2024','Sentinel-1 / Dynamic World; separate retrospective cohorts\nThresholds, support and recovery gaps'),
       (.18,'Four selected months','720 stratified pixel-months; dated Sentinel-2 evidence\nProxy agreement and assisted review with unknowns')]
for y,title,txt in boxes:
 flow.text(.01,y,title,ha='left',va='center',fontsize=9,weight='bold')
 flow.text(.41,y,txt,ha='left',va='center',fontsize=8,linespacing=1.5)
save(fig,'Figure_1_study_area_and_design')

# Figure 2: trajectories with honest separate scales and observation density.
fig,axs=plt.subplots(2,2,figsize=(180/25.4,164/25.4),layout='constrained')
for j,cls in enumerate(['seasonal','permanent']):
 for r in regions:
  a=annual[(annual.region==r)&annual.year.le(2021)]
  axs[0,j].plot(a.year,a[cls+'_water_area_km2'],color=colors[r],marker=markers_by_region[r],ms=2.7,label=short[r])
 axs[0,j].set(title=f'{"A" if j==0 else "B"}  {cls.capitalize()} source class',ylabel='Source-class area (km²)',xlabel='Year',ylim=(0,None))
 axs[0,j].set_xticks([2000,2007,2014,2021])
for r in regions:
 a=quality[(quality.region==r)&quality.year.le(2021)]
 axs[1,0].plot(a.year,a.mean_observed_calendar_months,color=colors[r],marker=markers_by_region[r],ms=2.7)
 axs[1,1].plot(a.year,a.mean_observed_jun_sep_months,color=colors[r],marker=markers_by_region[r],ms=2.7)
axs[1,0].set(title='C  Annual observation effort',ylabel='Area-weighted observed months',xlabel='Year',ylim=(0,12))
axs[1,1].set(title='D  June–September observation effort',ylabel='Area-weighted observed months',xlabel='Year',ylim=(0,4))
for a in axs[1]:a.set_xticks([2000,2007,2014,2021])
handles=[Line2D([],[],color=colors[r],label=short[r],marker=markers_by_region[r],ms=3) for r in regions]
fig.legend(handles=handles,loc='outside lower center',ncol=2,frameon=False)
save(fig,'Figure_2_annual_classes_and_observations')

# Figure 3: coefficient sensitivity; all regions and nulls retained.
fig,axs=plt.subplots(1,2,figsize=(180/25.4,112/25.4),layout='constrained')
settings=['mean_observation_effort','mean_and_wet_observation_effort','mean_wet_effort_and_2016_asset_step']
labs=['Climate + annual observations','+ wet-season observations','+ 2016 processing boundary']
cols=['#56B4E9','#E69F00','#222222'];markers=['o','s','D']
for ax,cls,panel in zip(axs,['seasonal','permanent'],'AB'):
 for k,setting in enumerate(settings):
  for j,r in enumerate(regions):
   a=step[(step.region==r)&(step.source_class==cls)&(step.setting==setting)].iloc[0]
   y=3-j+(k-1)*.18;x=a.time_coefficient_logit_per_year
   ax.errorbar(x,y,xerr=[[x-a.lower95],[a.upper95-x]],fmt=markers[k],color=cols[k],ms=4,capsize=2,elinewidth=2,label=labs[k] if j==0 else None)
 ax.axvline(0,color='#666666',lw=1,ls='--');ax.set_yticks(range(4),[short[r] for r in reversed(regions)])
 ax.set(title=f'{panel}  {cls.capitalize()} class',xlabel='Time coefficient (logit share/year)',ylim=(-.6,3.6))
axs[1].set_yticklabels([])
fig.legend(*axs[0].get_legend_handles_labels(),loc='outside lower center',ncol=1,frameon=False)
save(fig,'Figure_3_climate_observation_sensitivity')

# Figure 4: selected threshold sensitivity; no best-threshold declaration.
a=thr[(thr.region=='All_districts')&(thr.water_group=='all_water')].sort_values('threshold')
fig,axs=plt.subplots(1,2,figsize=(180/25.4,103/25.4),layout='constrained')
x=np.arange(4);w=.32
axs[0].bar(x-w/2,a.mean_classified_fraction*100,w,color='#0072B2',label='Classified DW')
axs[0].bar(x+w/2,a.sar_mean_paired_fraction*100,w,color='#E69F00',label='Paired SAR–DW',hatch='//')
axs[0].set(title='A  Mean footprint retained',ylabel='Share of fixed cohort (%)',xticks=x,xticklabels=['0.5','0.6','0.7','0.8'],xlabel='DW confidence threshold',ylim=(0,22))
axs[0].legend(frameon=False,loc='upper right',fontsize=8)
for name,label,c,m in [('sar','SAR–DW','#0072B2','o'),('jrc','JRC–DW','#D55E00','s')]:
 v=a[name+'_pooled_area_month_agreement']*100
 axs[1].plot(x,v,color=c,marker=m,label=label)
axs[1].set(title='B  Conditional method agreement',ylabel='Agreement on paired area-time (%)',xticks=x,xticklabels=['0.5','0.6','0.7','0.8'],xlabel='DW confidence threshold',ylim=(80,100.8))
axs[1].text(3,86,'No paired\nsupport',ha='center',fontsize=8);axs[1].legend(frameon=False,fontsize=8)
save(fig,'Figure_4_agreement_and_retained_support')

# Figure 5: outcomes and design-weighted agreement frame; not independent accuracy.
records=json.loads((ACTIVE/'RESULTS.json').read_text())
oc=records['all_point_outcome_counts'];alias={'AUTO_SCREENED':'Automatic proxy','HUMAN_DATES_CONSISTENT':'Consistent human dates','HUMAN_TEMPORAL_CHANGE':'Temporal change','HUMAN_UNCERTAIN_DATES':'Uncertain dates','UNRESOLVED_QUALITY':'Insufficient dated support'}
fig,axs=plt.subplots(1,2,figsize=(180/25.4,110/25.4),layout='constrained',gridspec_kw={'width_ratios':[1.25,1]})
for i,rr in enumerate(oc):
 c=['#0072B2','#56B4E9','#E69F00','#CC79A7','#8C8C8C'][i]
 axs[0].barh(4-i,rr['weighted_fraction']*100,color=c,height=.65)
 axs[0].text(rr['weighted_fraction']*100+.6,4-i,str(rr['samples']),va='center',fontsize=8)
axs[0].set_yticks(range(5),[alias[r['assisted_origin']] for r in reversed(oc)])
axs[0].set(title='A  All 720 pixel-months',xlabel='Design-weighted area-time share (%)',xlim=(0,69))
for j,r in enumerate(records['proxy_comparison']):
 y=1-j
 axs[1].hlines(y,r['binary_completion_lower']*100,r['binary_completion_upper']*100,color='#999999',lw=8)
 axs[1].plot(r['conditional_label_agreement']*100,y,'o',color='#222222',ms=6)
 axs[1].text(52,y+.25,f"Assigned weight: {r['assigned_design_weight_fraction']*100:.2f}%",fontsize=8)
axs[1].set(title='B  Conditional comparison',yticks=[0,1],yticklabels=['Assisted','Automatic'],xlabel='Agreement (%)',xlim=(50,102),ylim=(-.55,1.6))
axs[1].text(.02,.02,'Dot: assigned-label agreement\nGrey: binary completion range\nNo independent accuracy',transform=axs[1].transAxes,fontsize=8,va='bottom')
save(fig,'Figure_5_proxy_evidence_and_unknowns')

# Figure 6: all nine recovery sensitivity specifications.
statuses=['PRE_EVENT_SUPPORT_OR_REFERENCE_GAP','DROUGHT_SUPPORT_OR_REFERENCE_GAP','DEFICIT_UNCERTAIN_WITHIN_ENVELOPE']
legend=['Pre-event / reference gap','Drought / reference gap','Deficit uncertain within envelope'];cs=['#8C8C8C','#E69F00','#0072B2']
keys=list(recovery.groupby(['coverage_gate','minimum_reference_count']).groups)
fig,ax=plt.subplots(figsize=(180/25.4,100/25.4),layout='constrained');left=np.zeros(len(keys))
for s,lab,c in zip(statuses,legend,cs):
 counts=np.array([int(((recovery.coverage_gate==g)&(recovery.minimum_reference_count==n)&(recovery.status==s)).sum()) for g,n in keys])
 ax.barh(range(len(keys)),counts,left=left,label=lab,color=c)
 for j,v in enumerate(counts):
  if v:ax.text(left[j]+v/2,j,str(v),ha='center',va='center',color='white',fontsize=8)
 left+=counts
ax.set_yticks(range(len(keys)),[f'{g*100:.0f}% / {int(n)}' for g,n in keys]);ax.invert_yaxis()
ax.set(xlim=(0,108),xlabel='Event–cohort records (overlapping)',ylabel='Coverage gate / reference count',title='No identifiable recovery duration in any specification')
fig.legend(*ax.get_legend_handles_labels(),loc='outside lower center',ncol=1,frameon=False,fontsize=8)
save(fig,'Figure_6_recovery_support_gaps')

# Every original CSV is supplied, so nulls / failed supports remain inspectable.
tables=[]
for src in sorted(T.glob('*.csv')):
 dst=S/src.name;shutil.copy2(src,dst);tables.append(dict(file=src.name,sha256=sha(src),rows=len(pd.read_csv(src))))
(S/'table_manifest.json').write_text(json.dumps(tables,indent=2),encoding='utf-8')
summary=dict(annual_common_km2=float(annual.common_support_area_km2.iloc[0]),
 annual_everwater_retained=float(annual.retained_reference_fraction.iloc[0]),
 annual_district_support=annual[annual.year.eq(2000)][['region','common_support_area_km2']].to_dict('records'),
 observation_effort_union=quality[quality.region.eq('All_districts')&quality.year.le(2021)].agg(
  {'mean_observed_calendar_months':['min','max'],'mean_observed_jun_sep_months':['min','max'],
   'all_12_months_observed_area_fraction':['min','max']}).to_dict(),
 endpoints=end.to_dict('records'),thresholds=a.to_dict('records'),proxy=records['proxy_comparison'],
 recovery_statuses=recovery.status.value_counts().to_dict())
(P/'setup'/'manuscript_numbers.json').write_text(json.dumps(summary,indent=2,allow_nan=True),encoding='utf-8')
(P/'setup'/'artifact_provenance.json').write_text(json.dumps(dict(created=datetime.now(timezone.utc).isoformat(),
 inputs=provenance,models_refit=False,source_analysis=str(ACTIVE),figures=[dict(file=p.name,sha256=sha(p)) for p in sorted(F.glob('*'))]),indent=2),encoding='utf-8')
print('Prepared 6 figures,',len(tables),'CSV tables; source models unchanged.')
