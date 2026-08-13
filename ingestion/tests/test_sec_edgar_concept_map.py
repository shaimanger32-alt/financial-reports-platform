"""The `us-gaap` concept chains.

These tests hold the mapping to the survey it came from. A chain is a claim
about what the market actually tags, and a claim that nothing checks rots the
moment somebody adds a concept because it looked plausible.

The fixtures are the forty-seven real `companyfacts` payloads the survey used,
when they are present. They are large and are not committed, so the coverage
tests skip rather than fail when the cache is absent — the structural tests
below always run.
"""

import json
import pathlib

import pytest

from financial_core.metrics import REPORTED_METRICS
from ingestion.providers.sec_edgar.concept_map import (
    CONCEPT_CHAINS,
    DELIBERATELY_EXCLUDED,
    MAPPING_VERSION,
    PROVIDER_CODE_DEFAULT,
)

SURVEY = pathlib.Path(
    "/private/tmp/claude-501/-Users-user-Downloads/"
    "f4e670fa-1ae0-4dfd-b30c-958e336c0756/scratchpad/edgar"
)

METRIC_CODES = {spec.code for spec in REPORTED_METRICS}


class TestTheChainsAreWellFormed:
    def test_every_chain_names_a_real_metric(self) -> None:
        """A chain pointing at a metric that does not exist would surface much
        later as a permanently null figure."""
        unknown = set(CONCEPT_CHAINS) - METRIC_CODES

        assert not unknown, f"chains for metrics that do not exist: {sorted(unknown)}"

    def test_every_concept_is_namespaced(self) -> None:
        for metric, chain in CONCEPT_CHAINS.items():
            for concept in chain:
                assert concept.startswith("us-gaap:"), f"{metric}: {concept}"

    def test_no_chain_is_empty(self) -> None:
        for metric, chain in CONCEPT_CHAINS.items():
            assert chain, metric

    def test_no_concept_repeats_within_a_chain(self) -> None:
        for metric, chain in CONCEPT_CHAINS.items():
            assert len(chain) == len(set(chain)), metric

    def test_an_excluded_concept_is_not_quietly_in_a_chain(self) -> None:
        """`RevenueFromContractWithCustomerIncludingAssessedTax` is the one
        entry that is both documented and used, deliberately and behind the
        excluding-tax concept. Everything else stays out."""
        allowed_in_chains = {"us-gaap:RevenueFromContractWithCustomerIncludingAssessedTax"}
        used = {concept for chain in CONCEPT_CHAINS.values() for concept in chain}

        for concept in DELIBERATELY_EXCLUDED:
            if concept in allowed_in_chains:
                continue
            assert concept not in used, f"{concept} is excluded and still in a chain"

    def test_the_mapping_is_versioned(self) -> None:
        assert MAPPING_VERSION
        assert PROVIDER_CODE_DEFAULT == "sec_edgar"


@pytest.mark.skipif(not SURVEY.exists(), reason="survey payload cache is not present")
class TestCoverageAgainstTheSurvey:
    """The measurements the module docstring asserts, re-run."""

    @staticmethod
    def _tagged_by_company() -> list[set[str]]:
        tagged = []
        for path in sorted(SURVEY.glob("*.json")):
            document = json.loads(path.read_text())
            concepts = document.get("facts", {}).get("us-gaap", {})
            tagged.append(
                {
                    f"us-gaap:{code}"
                    for code, body in concepts.items()
                    if any(
                        row.get("end", "") >= "2020-01-01"
                        for unit in body.get("units", {}).values()
                        for row in unit
                    )
                }
            )
        return tagged

    def _coverage(self, metric: str) -> float:
        companies = self._tagged_by_company()
        chain = set(CONCEPT_CHAINS[metric])
        return sum(1 for tags in companies if chain & tags) / len(companies)

    @pytest.mark.parametrize(
        "metric",
        [
            "revenue",
            "net_income",
            "profit_before_tax",
            "income_tax_expense",
            "total_assets",
            "total_equity",
            "equity_and_liabilities",
            "cash_and_equivalents",
            "operating_cash_flow",
            "investing_cash_flow",
            "financing_cash_flow",
        ],
    )
    def test_the_universal_chains_really_are_universal(self, metric: str) -> None:
        assert self._coverage(metric) == 1.0

    def test_the_current_asset_split_is_not_universal(self) -> None:
        """The finding that costs working capital, current ratio and quick ratio
        their CORE tier in the United States. A bank orders its balance sheet by
        liquidity and tags neither concept."""
        assert 0.85 <= self._coverage("current_assets") < 1.0
        assert 0.85 <= self._coverage("current_liabilities") < 1.0

    def test_gross_profit_is_rarer_here_than_under_ifrs(self) -> None:
        """69% of Israeli issuers, 38% of these. It can never be a headline."""
        assert self._coverage("gross_profit") < 0.50

    def test_share_counts_are_well_covered_unlike_israel(self) -> None:
        """Three and four Israeli entities tagged these. Dilution becomes a
        usable metric in the American market."""
        assert self._coverage("weighted_average_shares_basic") > 0.90
        assert self._coverage("weighted_average_shares_diluted") > 0.90
