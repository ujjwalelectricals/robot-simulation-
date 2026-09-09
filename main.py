"""Compatibility entrypoint for EVOLVE.

The active desktop UI is now the 3D laboratory in ``main_3d.py``.
"""
from main_3d import Evolve3DApp as EvolveApp, main

__all__ = ["EvolveApp", "main"]

if __name__ == "__main__":
    raise SystemExit(main())
