import types

import pytest

from mvis_site.env import require_numpy_1


def test_numpy_1_runs_and_2_refuses():
    require_numpy_1()
    require_numpy_1(types.SimpleNamespace(__version__="1.26.4"))
    with pytest.raises(SystemExit, match=r"numpy is < 2 \(the anaconda base env\), with PYTHONNOUSERSITE=1"):
        require_numpy_1(types.SimpleNamespace(__version__="2.4.4"))
