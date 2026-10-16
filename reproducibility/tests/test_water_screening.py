"""Synthetic software fixtures only; never scientific reference observations."""
from pathlib import Path
import sys,unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'postprocessing'))
from screen_water_colors import BANDS,spectral_masks,classify_point,normalized


def values(seq):return {k:np.full((2,2),v) for k,v in zip(BANDS[:-1],seq)}
def scenes(label=0,clear=1,dates=('2020-11-01','2020-11-15','2020-11-29')):
    return [{'date':d,'clear_fraction':clear,'scene_automated_label':label,'near_opposite_signal_edge':False,'uninterpretable_radiometry_fraction':0} for d in dates]


class ScreeningTests(unittest.TestCase):
    def test_clear_spectral_software_examples(self):
        water=spectral_masks(values([.03,.05,.02,.01,.005]))
        dry=spectral_masks(values([.04,.06,.03,.30,.16]))
        self.assertTrue(water['water'].all());self.assertFalse(water['nonwater'].any())
        self.assertTrue(dry['nonwater'].all());self.assertFalse(dry['water'].any())

    def test_darkness_alone_never_confident_water(self):
        m=spectral_masks(values([.001,.0015,.001,.001,.0005]))
        self.assertFalse(m['water'].any());self.assertFalse(m['nonwater'].any())

    def test_mixed_and_invalid_radiometry(self):
        a=values([.03,.05,.02,.01,.005]);b=values([.04,.06,.03,.30,.16])
        for k in a:a[k][1]=b[k][1]
        m=spectral_masks(a);self.assertEqual(m['water'].mean(),.5);self.assertEqual(m['nonwater'].mean(),.5)
        v=values([.03,.05,.02,.01,-.005]);self.assertFalse(spectral_masks(v)['water'].any())
        self.assertTrue(np.isnan(normalized(np.zeros(2),np.zeros(2))).all())

    def test_binary_zero_is_not_missing(self):
        d=classify_point(scenes(0));self.assertEqual(d['category'],'AUTO_NONWATER');self.assertEqual(d['automated_water'],0)
        self.assertEqual(classify_point(scenes(1))['category'],'AUTO_WATER')

    def test_no_data_and_short_dates_remain_missing(self):
        for s in ([],scenes(None,0),scenes(0,.949),scenes(0,1,('2020-11-01','2020-11-05'))):
            d=classify_point(s);self.assertEqual(d['category'],'QUALITY_LIMITED');self.assertIsNone(d['automated_water'])
            self.assertFalse(d['review_required'])

    def test_mixed_dates_and_weak_bands_request_review(self):
        s=scenes(0);s[1]['scene_automated_label']=1
        self.assertIn('DATE_DISAGREEMENT',classify_point(s)['reason_codes'])
        s=scenes(None);self.assertEqual(classify_point(s)['category'],'REVIEW')

    def test_boundary_and_radiometry_request_review(self):
        s=scenes(1);s[1]['near_opposite_signal_edge']=True
        self.assertIn('BOUNDARY_SENSITIVITY',classify_point(s)['reason_codes'])
        s=scenes(1);s[1]['uninterpretable_radiometry_fraction']=.2
        self.assertIn('RADIOMETRY_AMBIGUOUS',classify_point(s)['reason_codes'])


if __name__=='__main__':unittest.main()
