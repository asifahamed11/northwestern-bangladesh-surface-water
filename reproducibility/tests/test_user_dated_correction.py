"""Synthetic invariants for one explicit dated correction, not study labels."""
from copy import deepcopy
import unittest
from postprocessing.apply_user_label144_correction import revise_answer


class UserDatedCorrectionTests(unittest.TestCase):
    def original(self):
        a={'label':'0','reviewer':'SOFTWARE_FIXTURE','updated_at':'2026-10-01T00:00:00Z'}
        return {'exported_at':'2026-10-02T00:00:00Z','records':[
            {'sample_id':'A','dates':{'day1':deepcopy(a),'day2':deepcopy(a)},'seen_scenes':['day1','day2']},
            {'sample_id':'B','dates':{'day1':deepcopy(a)},'seen_scenes':['day1']}]}

    def test_exact_id_and_date_only_and_source_immutable(self):
        source=self.original(); saved=deepcopy(source)
        revised,old,new=revise_answer(source,'A','day1','1','2026-10-16T01:00:00Z')
        self.assertEqual(source,saved)
        self.assertEqual(revised['records'][0]['dates']['day2'],saved['records'][0]['dates']['day2'])
        self.assertEqual(revised['records'][1],saved['records'][1])
        self.assertEqual(revised['records'][0]['seen_scenes'],saved['records'][0]['seen_scenes'])
        self.assertEqual(old['label'],'0');self.assertEqual(new['label'],'1')
        self.assertEqual(new['reviewer'],old['reviewer'])

    def test_wrong_identity_and_invalid_answer_rejected(self):
        for sid,scene,label in [('X','day1','1'),('A','missing','1'),('A','day1','water')]:
            with self.assertRaises(ValueError):revise_answer(self.original(),sid,scene,label,'2026-10-16T01:00:00Z')

    def test_reapplying_same_decision_does_not_create_another_revision(self):
        with self.assertRaises(ValueError):revise_answer(self.original(),'A','day1','0','2026-10-16T01:00:00Z')


if __name__=='__main__':unittest.main()
