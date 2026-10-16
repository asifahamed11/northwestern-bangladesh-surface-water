"""Numerical and input-contract fixtures only, not research observations."""
from pathlib import Path
from tempfile import TemporaryDirectory
import copy,hashlib,json,sys,unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'postprocessing'))
from evaluate_blind_accuracy import summarize,decision,bootstrap,evaluate,SCHEMA


def row(sid='TEST_A'):
    return {'sample_id':sid,'period':'2020-11','scenes':[
        {'item_id':'test_1','date':'2020-11-01','clear_fraction':1},
        {'item_id':'test_2','date':'2020-11-15','clear_fraction':0},
        {'item_id':'test_3','date':'2020-11-29','clear_fraction':1}]}


def entry(label='0'):
    return {'label':label,'reviewer':'TEST_REVIEWER','notes':'','reason':'','updated_at':'2026-10-15T10:00:00Z',
            'attested':label in ('0','1'),'seen_scenes':['test_1','test_2','test_3']}


class EvaluationTests(unittest.TestCase):
    def test_unknown_weight_stays_in_identification_bounds(self):
        m=summarize([1,0,1],[1,1,np.nan],[2,3,5])
        self.assertAlmostEqual(m['conditional_accuracy_on_verified_support'],.4)
        self.assertAlmostEqual(m['accuracy_identification_lower'],.2)
        self.assertAlmostEqual(m['accuracy_identification_upper'],.7)
        self.assertAlmostEqual(m['unknown_reference_weight_fraction'],.5)

    def test_all_known_bounds_equal_point_value(self):
        m=summarize([0,1],[0,0],[9,1])
        self.assertEqual(m['conditional_accuracy_on_verified_support'],.9)
        self.assertEqual(m['accuracy_identification_lower'],.9)
        self.assertEqual(m['accuracy_identification_upper'],.9)

    def test_no_reference_does_not_generate_accuracy(self):
        m=summarize([0,1],[np.nan,np.nan],[4,6])
        self.assertIsNone(m['conditional_accuracy_on_verified_support'])
        self.assertEqual(m['accuracy_identification_lower'],0)
        self.assertEqual(m['accuracy_identification_upper'],1)

    def test_invalid_numeric_values_rejected(self):
        for pred,ref,weight in [([2],[0],[1]),([.2],[0],[1]),([1],[np.inf],[1]),([1],[0],[-1]),([1],[0],[0])]:
            with self.assertRaises(ValueError):summarize(pred,ref,weight)

    def test_human_gates_and_water_zero(self):
        self.assertEqual(decision(entry('0'),row()),('VERIFIED',0))
        self.assertEqual(decision(entry('UNCERTAIN'),row()),('UNCERTAIN',None))
        e=entry();e['attested']=False
        self.assertEqual(decision(e,row()),('PRELIMINARY',None))
        e=entry();e['seen_scenes']=['test_1']
        with self.assertRaises(ValueError):decision(e,row())
        e=entry('UNCERTAIN');e['seen_scenes']=[]
        self.assertEqual(decision(e,row()),('PRELIMINARY',None))

    def test_bootstrap_reproducible_and_unequal_groups_retained(self):
        p=np.array([0,1,1,0]);r=np.array([0,1,np.nan,1]);w=np.array([5,1,2,3]);s=np.array(['A','A','B','B'])
        a=bootstrap(p,r,w,s,100,17);b=bootstrap(p,r,w,s,100,17)
        self.assertEqual(a,b)
        self.assertLessEqual(a['identification_bounds_outer_sampling_interval95'][0],a['identification_bounds_outer_sampling_interval95'][1])

    def test_end_to_end_backup_lock_unknowns_and_no_input_changes(self):
        with TemporaryDirectory() as tmp:
            base=Path(tmp)/'TEST_FIXTURES';(base/'public').mkdir(parents=True);(base/'private').mkdir()
            identity={'schema':SCHEMA,'rows':[row('TEST_A'),row('TEST_B')],'scope':'SOFTWARE_FIXTURE_ONLY'}
            ds={**identity,'id':hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()}
            plan=[{'sample_id':s,'predicted_water':v,'population_pixels':100,'planned_samples':1,'pixel_area_km2':.001,'stratum':s} for s,v in [('TEST_A',0),('TEST_B',1)]]
            for path,obj in [(base/'public/review_dataset.json',ds),(base/'private/validation_sample_plan.json',plan),
                (base/'private/stratum_counts.json',[{'stratum':s,'minimum_verified':1} for s in ['TEST_A','TEST_B']])]:path.write_text(json.dumps(obj),encoding='utf-8')
            manifest={'dataset_id':ds['id'],'frozen_evaluation_inputs_sha256':{s:hashlib.sha256((base/s).read_bytes()).hexdigest() for s in ('private/validation_sample_plan.json','private/stratum_counts.json','public/review_dataset.json')}}
            (base/'review_manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
            backup={'schema':SCHEMA,'dataset_id':ds['id'],'exported_at':'2026-10-15T11:00:00Z',
              'records':[{'sample_id':'TEST_A',**entry('0')},{'sample_id':'TEST_B',**entry('UNCERTAIN')}]}
            path=Path(tmp)/'TEST_BACKUP.json';path.write_text(json.dumps(backup),encoding='utf-8');before=path.read_bytes()
            result,out=evaluate(path,base=base,out=Path(tmp)/'TEST_RESULT')
            self.assertEqual(path.read_bytes(),before)
            self.assertEqual(result['status'],'INCOMPLETE_HUMAN_REFERENCE_REVIEW')
            self.assertFalse(result['prewriting_reference_collection_gate_pass'])
            self.assertEqual(result['metrics']['n_unknown_reference'],1)
            self.assertFalse(result['global_accuracy_point_estimate_assuming_random_nonresponse_reported'])
            self.assertFalse(result['scientific_publication_ready'])
            backup['records'][1]=copy.deepcopy(backup['records'][0])
            path.write_text(json.dumps(backup),encoding='utf-8')
            with self.assertRaises(ValueError):evaluate(path,base=base,out=Path(tmp)/'SHOULD_NOT_EXIST')
            self.assertFalse((Path(tmp)/'SHOULD_NOT_EXIST').exists())
            backup['records']=[{'sample_id':'TEST_A',**entry('0')},{'sample_id':'TEST_B',**entry('UNCERTAIN')}]
            path.write_text(json.dumps(backup),encoding='utf-8')
            plan[0]['predicted_water']=1
            (base/'private/validation_sample_plan.json').write_text(json.dumps(plan),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'Frozen evaluation input changed'):
                evaluate(path,base=base,out=Path(tmp)/'CHANGED_PLAN_NOT_ACCEPTED')
            self.assertFalse((Path(tmp)/'CHANGED_PLAN_NOT_ACCEPTED').exists())

    def test_every_added_date_must_be_seen(self):
        r=row();r['scenes'].append({'item_id':'test_4','date':'2020-11-30','clear_fraction':1})
        e=entry()
        with self.assertRaises(ValueError):decision(e,r)
        e['seen_scenes'].append('test_4')
        self.assertEqual(decision(e,r),('VERIFIED',0))


if __name__=='__main__':unittest.main()
