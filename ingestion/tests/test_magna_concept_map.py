"""The MAGNA concept chains.

These tests guard the mapping against the two ways it can rot: a chain naming a
metric that does not exist, and someone adding back a concept that was excluded
on purpose.
"""

from financial_core.metrics import METRICS_BY_CODE
from ingestion.providers.magna_xbrl.concept_map import (
    CONCEPT_CHAINS,
    DELIBERATELY_EXCLUDED,
    all_mapped_concepts,
)


def test_every_chain_names_a_metric_that_exists() -> None:
    unknown = set(CONCEPT_CHAINS) - set(METRICS_BY_CODE)

    assert not unknown, f"chains point at metrics that do not exist: {sorted(unknown)}"


def test_every_core_metric_has_a_chain() -> None:
    """A core metric with no chain is permanently null, which is worth noticing."""
    missing = {
        code
        for code, spec in METRICS_BY_CODE.items()
        if spec.is_core and code not in CONCEPT_CHAINS
    }

    assert not missing, f"core metrics with no concept chain: {sorted(missing)}"


def test_no_chain_is_empty() -> None:
    empty = [code for code, chain in CONCEPT_CHAINS.items() if not chain]

    assert not empty


def test_a_concept_is_never_claimed_by_two_metrics() -> None:
    """One raw concept cannot mean two different things at once."""
    owners: dict[str, list[str]] = {}
    for metric_code, chain in CONCEPT_CHAINS.items():
        for concept in chain:
            owners.setdefault(concept, []).append(metric_code)

    shared = {concept: metrics for concept, metrics in owners.items() if len(metrics) > 1}
    assert not shared, f"concepts claimed by several metrics: {shared}"


def test_a_chain_has_no_duplicates() -> None:
    for metric_code, chain in CONCEPT_CHAINS.items():
        assert len(chain) == len(set(chain)), f"{metric_code} repeats a concept"


def test_excluded_concepts_stay_out() -> None:
    """`OtherCurrentReceivables` is the most widely tagged receivables concept
    and is still not trade receivables. Folding it in would inflate DSO for
    nearly every company."""
    mapped = set(all_mapped_concepts())

    for concept in DELIBERATELY_EXCLUDED:
        assert concept not in mapped, f"{concept} was excluded on purpose"


def test_trade_receivables_uses_only_pure_trade_concepts() -> None:
    """Measured, not assumed: 6 of the 7 issuers that tag both use
    `TradeAndOtherCurrentReceivables` for the much smaller "other receivables"
    line, despite what its name says. Matrix IT tags 1,746,539,000 as trade
    receivables and 113,123,000 there. It is not a fallback, it is a different
    number, and using it would understate DSO by an order of magnitude."""
    chain = CONCEPT_CHAINS["trade_receivables"]

    assert chain[0] == "ifrs-full:CurrentTradeReceivables"
    assert "ifrs-full:TradeAndOtherCurrentReceivables" not in chain
    assert "ifrs-full:TradeAndOtherReceivables" not in chain


def test_trade_payables_prefers_supplier_balances() -> None:
    chain = CONCEPT_CHAINS["trade_payables"]

    assert chain[0] == "ifrs-full:TradeAndOtherCurrentPayablesToTradeSuppliers"


def test_owner_attributable_figures_are_separate_metrics_not_fallbacks() -> None:
    """Total profit and profit attributable to owners are different amounts.
    Treating one as a substitute would change what a margin means whenever a
    company has minority interests."""
    assert "ifrs-full:ProfitLossAttributableToOwnersOfParent" not in CONCEPT_CHAINS["net_income"]
    assert "ifrs-full:EquityAttributableToOwnersOfParent" not in CONCEPT_CHAINS["total_equity"]
    assert CONCEPT_CHAINS["net_income_attributable_to_owners"]
    assert CONCEPT_CHAINS["equity_attributable_to_owners"]


def test_all_mapped_concepts_is_deduplicated_and_complete() -> None:
    concepts = all_mapped_concepts()

    assert len(concepts) == len(set(concepts))
    assert set(concepts) == {concept for chain in CONCEPT_CHAINS.values() for concept in chain}
