import numpy as np
from research_pipeline.spatial import majority_class

def test_strict_majority_and_ambiguous_class():
    values=np.array([[1,2,3,1],[1,2,3,1],[1,2,3,2],[2,3,1,2],[3,1,2,3]])[:,None,:]
    np.testing.assert_array_equal(majority_class(values),[[1,2,3,0]])

def test_missing_values_are_not_water_class():
    values=np.array([[0,0],[0,0],[0,1],[2,2],[2,3]])[:,None,:]
    np.testing.assert_array_equal(majority_class(values),[[0,0]])
