"""Replay and audit the complete 2018/2024 joint-cell pilot without Earth Engine."""
from pathlib import Path
import argparse,importlib.util,json
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    out=a.output.resolve()
    assert not out.exists(),'Choose a new output directory'
    assert out!=ROOT and not any(out.is_relative_to(ROOT/x) for x in ['data','code','figures','manuscript','provenance','.git'])
    source=ROOT/'data/revision/batch_completion_20261021'
    spec=importlib.util.spec_from_file_location('joint_pilot',ROOT/'code/revision/analyse_joint_pilot.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    mod.run(source/'raw',ROOT/'data/inputs/earth_engine_exports/NW_Bangladesh_DW_sensitivity_2015_2024',out)
    checks=[]
    for expected in sorted((source/'analysis').glob('*.csv')):
        fresh=pd.read_csv(out/expected.name);old=pd.read_csv(expected)
        pd.testing.assert_frame_equal(fresh,old,check_exact=False,rtol=1e-10,atol=1e-10)
        checks.append({'table':expected.name,'rows':len(fresh),'equal_within_tolerance':True})
    assert len(checks)==4
    (out/'REPLAY_REPORT.json').write_text(json.dumps({'tables':checks,'requires_earth_engine':False,
        'creates_independent_labels':False,'estimates_physical_accuracy':False},indent=2),encoding='utf-8')
    print('PASS: four joint-cell tables reproduced and original export metadata/areas reconciled.')
if __name__=='__main__':main()
