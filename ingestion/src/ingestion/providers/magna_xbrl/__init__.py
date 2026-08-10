"""MAGNA/XBRL provider — Israel Securities Authority."""

from ingestion.providers.magna_xbrl.client import PROVIDER_CODE, MagnaXbrlClient
from ingestion.providers.magna_xbrl.concept_map import (
    CONCEPT_CHAINS,
    DELIBERATELY_EXCLUDED,
    MAPPING_VERSION,
    all_mapped_concepts,
)
from ingestion.providers.magna_xbrl.parser import distinct_filings, find_conflicts, parse_rows
from ingestion.providers.magna_xbrl.periods import PeriodParseError, parse_period

__all__ = [
    "CONCEPT_CHAINS",
    "DELIBERATELY_EXCLUDED",
    "MAPPING_VERSION",
    "PROVIDER_CODE",
    "MagnaXbrlClient",
    "PeriodParseError",
    "all_mapped_concepts",
    "distinct_filings",
    "find_conflicts",
    "parse_period",
    "parse_rows",
]
