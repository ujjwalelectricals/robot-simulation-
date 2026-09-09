"""Windows launcher for the self-contained EVOLVE 3D laboratory."""
from performance_tuning import install as install_performance
install_performance()

from ecosystem_expansion import install as install_ecosystem
install_ecosystem()

from cognitive_upgrade import install as install_cognition
install_cognition()

from hierarchical_behavior import install as install_behavior
install_behavior()

from survival_memory_upgrade import install as install_survival_memory
install_survival_memory()

from memory_enhancement import install as install_memory
install_memory()

from advanced_evolution import install as install_advanced
install_advanced()

import main_3d as main

if __name__ == "__main__":
    raise SystemExit(main.main())
