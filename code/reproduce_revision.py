"""Replay annual revision statistics from genuine derived inputs, preserving originals."""
from pathlib import Path
import argparse,importlib.util,json,shutil,sys
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1]
def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
 out=args.output.resolve();assert not out.exists(),'Choose a new output directory'
 assert out!=ROOT and not any(out.is_relative_to(ROOT/x) for x in ['data','code','figures','manuscript','provenance','.git'])
 tables=out/'tables';tables.mkdir(parents=True)
 inp=ROOT/'data/revision/tables'
 for name in ['annual_model_inputs_revision.csv','calendar_matched_monthly_water.csv']:
  shutil.copy2(inp/name,tables/name)
 spec=importlib.util.spec_from_file_location('revision_analysis',ROOT/'code/revision/analyse_revision.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 m.OUT=out;m.T=tables;m.P=json.loads((ROOT/'data/revision/FROZEN_REVISION_PROTOCOL.json').read_text())
 d=pd.read_csv(tables/'annual_model_inputs_revision.csv');m.windows(d);m.monthly_matching();m.annual_analysis(d)
 records=[]
 for fresh in sorted(tables.glob('*.csv')):
  expected=inp/fresh.name
  if not expected.exists():continue
  a=pd.read_csv(fresh);b=pd.read_csv(expected)
  pd.testing.assert_frame_equal(a,b,check_exact=False,rtol=1e-8,atol=1e-10)
  records.append({'table':fresh.name,'rows':len(a),'equal_within_tolerance':True})
 (out/'REPLAY_REPORT.json').write_text(json.dumps({'tables':records,'raw_pixels_reprocessed':False,'models_refit':True,'reference_labels_created':False},indent=2))
 print('PASS:',len(records),'tables replayed from supplied derived inputs.')
if __name__=='__main__':main()
