"""Data providers. MAGNA is provider one, not the domain model."""

from ingestion.providers.base import (
    FactBatch,
    FactQuery,
    FinancialDataProvider,
    ProviderConcept,
    ProviderEntity,
    ProviderError,
    ProviderFact,
    ProviderNotSupportedError,
    ProviderPeriod,
    ProviderUnavailableError,
)

__all__ = [
    "FactBatch",
    "FactQuery",
    "FinancialDataProvider",
    "ProviderConcept",
    "ProviderEntity",
    "ProviderError",
    "ProviderFact",
    "ProviderNotSupportedError",
    "ProviderPeriod",
    "ProviderUnavailableError",
]
