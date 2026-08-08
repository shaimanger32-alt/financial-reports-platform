"""Phase 0: workspace wiring only. Provider clients arrive in phase 1."""

import ingestion


def test_version_is_exposed() -> None:
    assert ingestion.__version__ == "0.1.0"
