"""Windows launcher: optimized runtime + expanded ecosystem + visual upgrade."""
from performance_tuning import install as install_performance

install_performance()

from ecosystem_expansion import install as install_ecosystem

install_ecosystem()

import main

from visual_upgrade import install as install_visuals

install_visuals()

if __name__ == "__main__":
    raise SystemExit(main.main())
