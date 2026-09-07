# Research boundary

This directory is the target home for offline research components.

Allowed responsibilities:

- Backtesting and historical execution-cost simulation.
- Walk-forward and time-ordered validation.
- Feature generation and ML training/validation.
- Experiment tracking and model evaluation.

Research code must not import live execution, broker adapters, recovery, or
system-gate modules. Research outputs should be versioned model artifacts or
explicit, validated model contracts consumed by the live boundary.

The existing `strategy/` modules are not moved in this change because doing so
would create a large, hard-to-audit import migration while the test suite is
already being repaired. Migration should happen module-by-module with tests
remaining green after every move.
