"""Run-time checks shared by the site scripts."""
from __future__ import annotations

import importlib


def require_numpy_1(module=None) -> None:
    """numpy 2 prints numbers differently (np.float64(1.0)), so the generated files would change. ~/.local holds
    numpy 2; run with PYTHONNOUSERSITE=1."""
    np = module or importlib.import_module("numpy")
    if int(np.__version__.split(".")[0]) >= 2:
        raise SystemExit(f"numpy {np.__version__} changes the output; run a python whose numpy is < 2 (the anaconda base env), "
                         "with PYTHONNOUSERSITE=1 so ~/.local's numpy 2 stays out")
