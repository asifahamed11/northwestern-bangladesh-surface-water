"""Algorithm invariants only; fixtures are not research observations."""
import unittest
import numpy as np
from postprocessing.finalize_code_only_research import comparison_metrics, bootstrap_metrics


class ProxyComparisonTests(unittest.TestCase):
    def test_unknown_weight_retained_in_entire_denominator(self):
        r = comparison_metrics([1, 0, 1], [1, 1, np.nan], [2, 3, 5])
        self.assertAlmostEqual(r['conditional_label_agreement'], .4)
        self.assertAlmostEqual(r['binary_completion_lower'], .2)
        self.assertAlmostEqual(r['binary_completion_upper'], .7)
        self.assertAlmostEqual(r['unassigned_design_weight_fraction'], .5)
        self.assertIsNone(r['independent_reference_accuracy'])

    def test_unknown_is_never_nonwater_or_accuracy_zero(self):
        r = comparison_metrics([0, 1], [np.nan, np.nan], [9, 1])
        self.assertIsNone(r['conditional_label_agreement'])
        self.assertEqual((r['binary_completion_lower'], r['binary_completion_upper']), (0, 1))
        self.assertIsNone(r['physical_accuracy_lower'])

    def test_complete_binary_proxy_range_collapses_only_to_agreement(self):
        r = comparison_metrics([0, 1], [0, 0], [9, 1])
        self.assertAlmostEqual(r['binary_completion_lower'], .9)
        self.assertAlmostEqual(r['binary_completion_upper'], .9)
        self.assertIsNone(r['independent_reference_accuracy'])

    def test_zero_proxy_is_a_genuine_assigned_label(self):
        r = comparison_metrics([0, 1], [0, np.nan], [1, 1])
        self.assertEqual(r['assigned_samples'], 1)
        self.assertEqual(r['matching_assigned_samples'], 1)

    def test_range_width_equals_unknown_weight_fraction(self):
        r = comparison_metrics([0, 1, 0, 1], [1, 1, np.nan, np.nan], [4, 2, 8, 3])
        self.assertAlmostEqual(r['binary_completion_upper'] - r['binary_completion_lower'], r['unassigned_design_weight_fraction'])

    def test_invalid_classes_weights_and_infinity_fail(self):
        for args in [([2], [0], [1]), ([1], [.1], [1]), ([1], [np.inf], [1]),
                     ([1], [0], [0]), ([1], [0], [-1]), ([1], [0], [np.nan]), ([], [], [])]:
            with self.assertRaises(ValueError): comparison_metrics(*args)

    def test_bootstrap_reproducible_and_all_unknown_retained(self):
        args = (np.array([0, 1, 0, 1]), np.array([0., np.nan, 1., np.nan]), np.array([9., 1., 2., 3.]), np.array(['A', 'A', 'B', 'B']))
        a = bootstrap_metrics(*args, replicates=100, seed=77)
        self.assertEqual(a, bootstrap_metrics(*args, replicates=100, seed=77))
        b = bootstrap_metrics(args[0], np.full(4, np.nan), args[2], args[3], replicates=100, seed=77)
        self.assertIsNone(b['conditional_agreement_bootstrap_lower95'])
        self.assertEqual((b['completion_range_outer_bootstrap_lower95'], b['completion_range_outer_bootstrap_upper95']), (0, 1))

    def test_perfect_sample_agreement_is_not_a_certain_population_interval(self):
        b = bootstrap_metrics(np.array([0, 1]), np.array([0., 1.]), np.array([1., 1.]), np.array(['A', 'A']), replicates=100, seed=1)
        self.assertTrue(b['conditional_percentile_bootstrap_degenerate'])
        self.assertIsNone(b['conditional_agreement_bootstrap_lower95'])


if __name__ == '__main__': unittest.main()
