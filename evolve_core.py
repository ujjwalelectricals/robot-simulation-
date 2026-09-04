"""Backward-compatible import shim.

The active implementation lives in evolve_core_v2.py. Keeping this module means
older experiments/imports continue to work without maintaining a second engine.
"""

from evolve_core_v2 import *  # noqa: F401,F403
