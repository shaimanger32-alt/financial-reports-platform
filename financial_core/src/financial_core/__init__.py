"""Deterministic financial domain logic.

This package is the analytical heart of the product and is deliberately free of
infrastructure: no database session, no HTTP client, no web framework. Every
calculation here must be testable in isolation (spec section 9).

Sub-packages are added as their phase is implemented:
  periods/     period model, quarter/YTD/TTM derivation   (phase 2)
  metrics/     formula registry and core metrics          (phase 3)
  signals/     numeric observations                       (phase 4)
  patterns/    multi-signal findings                      (phase 4)
  validation/  data-quality and comparability checks      (phase 2)
"""

__version__ = "0.1.0"
