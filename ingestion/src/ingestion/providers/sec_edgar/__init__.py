"""SEC EDGAR provider. Read-only.

No API key and no registration: SEC asks only for a `User-Agent` naming the
caller with a contact address, and fewer than ten requests a second.
"""

from ingestion.providers.sec_edgar.client import PROVIDER_CODE, SecEdgarClient, normalise_cik
from ingestion.providers.sec_edgar.parser import (
    concept_coverage,
    learn_fiscal_calendar,
    parse_company_facts,
)

__all__ = [
    "PROVIDER_CODE",
    "SecEdgarClient",
    "concept_coverage",
    "learn_fiscal_calendar",
    "normalise_cik",
    "parse_company_facts",
]
