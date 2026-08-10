"""Resolving a metric through a fallback chain.

The behaviour that matters most is what happens when the chain does *not*
resolve: the answer has to be an explicit "nobody reported any of these", not a
zero and not a silently different concept.
"""

from financial_core.normalization import (
    ConceptCandidate,
    ResolutionOutcome,
    resolve_all,
    resolve_metric,
)

RECEIVABLES_CHAIN = (
    ConceptCandidate(0, "ifrs-full:CurrentTradeReceivables"),
    ConceptCandidate(1, "ifrs-full:TradeReceivables"),
    ConceptCandidate(2, "ifrs-full:TradeAndOtherCurrentReceivables"),
)


def test_the_most_precise_concept_wins_when_present() -> None:
    resolution = resolve_metric(
        "trade_receivables",
        RECEIVABLES_CHAIN,
        {
            "ifrs-full:CurrentTradeReceivables": 205_000_000,
            "ifrs-full:TradeAndOtherCurrentReceivables": 260_000_000,
        },
    )

    assert resolution.is_resolved
    assert resolution.raw_concept == "ifrs-full:CurrentTradeReceivables"
    assert resolution.value == 205_000_000


def test_the_chain_falls_through_to_a_later_concept() -> None:
    """This is the case that rescues DSO for companies using a different tag."""
    resolution = resolve_metric(
        "trade_receivables",
        RECEIVABLES_CHAIN,
        {"ifrs-full:TradeAndOtherCurrentReceivables": 260_000_000},
    )

    assert resolution.is_resolved
    assert resolution.raw_concept == "ifrs-full:TradeAndOtherCurrentReceivables"


def test_a_concept_present_without_a_value_is_not_a_match() -> None:
    """An empty figure is unknown. The chain keeps looking."""
    resolution = resolve_metric(
        "trade_receivables",
        RECEIVABLES_CHAIN,
        {
            "ifrs-full:CurrentTradeReceivables": None,
            "ifrs-full:TradeReceivables": 190_000_000,
        },
    )

    assert resolution.raw_concept == "ifrs-full:TradeReceivables"
    assert resolution.value == 190_000_000


def test_nothing_reported_is_stated_not_guessed() -> None:
    resolution = resolve_metric("trade_receivables", RECEIVABLES_CHAIN, {})

    assert resolution.outcome is ResolutionOutcome.NO_CANDIDATE_REPORTED
    assert resolution.value is None
    assert resolution.raw_concept is None
    assert resolution.considered == tuple(c.raw_concept for c in RECEIVABLES_CHAIN)


def test_a_metric_with_no_chain_is_distinguishable_from_one_nobody_reported() -> None:
    """Two different problems. A missing mapping is ours; a missing figure is
    the issuer's."""
    resolution = resolve_metric("something_unmapped", (), {"ifrs-full:Revenue": 1.0})

    assert resolution.outcome is ResolutionOutcome.NO_MAPPING
    assert resolution.considered == ()


def test_zero_is_a_real_value_and_resolves() -> None:
    """Zero is a figure the company reported. Only None means unknown."""
    resolution = resolve_metric(
        "trade_receivables",
        RECEIVABLES_CHAIN,
        {"ifrs-full:CurrentTradeReceivables": 0.0},
    )

    assert resolution.is_resolved
    assert resolution.value == 0.0


def test_a_company_override_beats_the_general_chain() -> None:
    """An issuer extension wins even though its priority is higher."""
    chain = (
        *RECEIVABLES_CHAIN,
        ConceptCandidate(9, "acme:CustomerBalances", company_scoped=True),
    )

    resolution = resolve_metric(
        "trade_receivables",
        chain,
        {
            "ifrs-full:CurrentTradeReceivables": 205_000_000,
            "acme:CustomerBalances": 211_000_000,
        },
    )

    assert resolution.raw_concept == "acme:CustomerBalances"
    assert resolution.company_scoped is True


def test_an_override_that_is_not_reported_falls_back_to_the_general_chain() -> None:
    chain = (
        *RECEIVABLES_CHAIN,
        ConceptCandidate(9, "acme:CustomerBalances", company_scoped=True),
    )

    resolution = resolve_metric(
        "trade_receivables",
        chain,
        {"ifrs-full:CurrentTradeReceivables": 205_000_000},
    )

    assert resolution.raw_concept == "ifrs-full:CurrentTradeReceivables"
    assert resolution.company_scoped is False


def test_resolution_is_deterministic_when_priorities_collide() -> None:
    chain = (
        ConceptCandidate(0, "ifrs-full:Bravo"),
        ConceptCandidate(0, "ifrs-full:Alpha"),
    )
    reported = {"ifrs-full:Alpha": 1.0, "ifrs-full:Bravo": 2.0}

    first = resolve_metric("m", chain, reported)
    second = resolve_metric("m", tuple(reversed(chain)), reported)

    assert first.raw_concept == second.raw_concept == "ifrs-full:Alpha"


def test_resolve_all_covers_every_chain() -> None:
    chains = {
        "trade_receivables": RECEIVABLES_CHAIN,
        "inventories": (ConceptCandidate(0, "ifrs-full:Inventories"),),
    }

    resolved = resolve_all(chains, {"ifrs-full:Inventories": 42.0})

    assert resolved["inventories"].is_resolved
    assert resolved["trade_receivables"].outcome is ResolutionOutcome.NO_CANDIDATE_REPORTED
