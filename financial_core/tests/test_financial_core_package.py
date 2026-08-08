"""Phase 0: prove the workspace wiring, not the domain logic (which does not exist yet)."""

import subprocess
import sys
import textwrap

import financial_core


def test_version_is_exposed() -> None:
    assert financial_core.__version__ == "0.1.0"


def test_core_imports_without_infrastructure() -> None:
    """The domain layer must stay importable without a database or web framework.

    This guards spec section 9: calculations must be testable without FastAPI/DB.
    Runs in a clean subprocess so that imports made by other tests do not leak in.
    """
    probe = textwrap.dedent("""
        import sys
        import financial_core  # noqa: F401

        forbidden = {"sqlalchemy", "fastapi", "psycopg", "httpx", "alembic"}
        leaked = sorted(forbidden & set(sys.modules))
        if leaked:
            raise SystemExit("financial_core pulled in infrastructure: " + ", ".join(leaked))
    """)
    result = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
