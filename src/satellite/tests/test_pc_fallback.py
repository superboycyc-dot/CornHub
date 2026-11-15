import numpy as np
import pytest
from satellite.pc_fallback import calibration_parameters
from satellite.imagery import ndvi_statistics


@pytest.mark.parametrize('baseline,offset',[('02.12',0),('03.00',0),('04.00',-1000),('05.00',-1000),('05.13',-1000)])
def test_pc_uses_product_baseline_not_observation_date(baseline,offset):
    assert calibration_parameters({'properties':{'s2:processing_baseline':baseline}})==(baseline,offset)


@pytest.mark.parametrize('baseline',['','unknown','06.00','NaN'])
def test_pc_unknown_baseline_fails_instead_of_guessing(baseline):
    with pytest.raises(ValueError):
        calibration_parameters({'properties':{'s2:processing_baseline':baseline}})


def test_corrected_dn_ratio_avoids_uint_wrap_and_double_scaling():
    _,offset=calibration_parameters({'properties':{'s2:processing_baseline':'04.00'}})
    red=np.array([[1500]],dtype='uint16').astype('float64')+offset
    nir=np.array([[3000]],dtype='uint16').astype('float64')+offset
    result=ndvi_statistics(red,nir,np.array([[4]]),np.array([[True]]))
    assert result['ndvi']==pytest.approx(.6)
