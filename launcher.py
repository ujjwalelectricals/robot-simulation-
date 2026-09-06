"""Windows launcher: optimized runtime + expanded ecosystem + EVOLVE UI."""
from performance_tuning import install as install_performance

install_performance()

from ecosystem_expansion import install as install_ecosystem

install_ecosystem()

import main

if __name__ == "__main__":
    raise SystemExit(main.main())
