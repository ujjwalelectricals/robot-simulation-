"""Windows launcher for the full EVOLVE cognition, ecology, evolution and visual stack."""
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

import main

from visual_upgrade import install as install_visuals
install_visuals()

if __name__ == "__main__":
    raise SystemExit(main.main())
