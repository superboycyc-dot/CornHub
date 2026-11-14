import pytest
from satellite.pc_fallback import pre04_baseline


def test_pc_raw_ratio_requires_metadata_confirmed_pre04():
    assert pre04_baseline({'properties':{'s2:processing_baseline':'03.00'}})=='03.00'


@pytest.mark.parametrize('baseline',['04.00','05.11',''])
def test_pc_does_not_guess_additive_offsets(baseline):
    with pytest.raises(ValueError):
        pre04_baseline({'properties':{'s2:processing_baseline':baseline}})
