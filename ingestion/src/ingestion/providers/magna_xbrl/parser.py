"""Translation of MAGNA result rows into provider-neutral facts.

Two things about the payload drive the defensiveness here, both observed in the
phase 1 spike rather than assumed:

1. The column set is not stable. `Balance`, `Title`, `Verbose Label` and the
   period labels are absent from a substantial share of rows, so every lookup
   goes through `.get()`.
2. `Fact` is frequently empty. In the first sample, 204 of 745 rows carried no
   figure. Those rows become a fact with `value=None`, never zero.
"""

import logging
import math
from collections.abc import Iterator, Sequence
from typing import Any

from ingestion.providers.base import ProviderFact
from ingestion.providers.magna_xbrl.periods import PeriodParseError, parse_period

logger = logging.getLogger(__name__)

# Column names as they appear in the JSON result file.
COL_ENTITY = "Company ID"
COL_FILING = "Reference Number"
COL_PERIOD = "Period"
COL_TAG = "Tag"
COL_FACT = "Fact"
COL_MEASURE = "Measure"
COL_SCALE = "Scale"
COL_DECIMALS = "Decimals"
COL_STATEMENT = "Data source in XBRL"

_DIMENSION_COLUMNS = ("Axis", "Member", "ExplicitMember", "TypedMember")
_LABEL_COLUMNS = {
    "Label (EN)": "en",
    "Verbose Label (HE)": "he",
    "Title": "title_he",
}


def _text(row: dict[str, Any], column: str) -> str | None:
    """Read a column, treating blanks and the literal 'None' as absent."""
    value = row.get(column)
    if value is None:
        return None
    text = str(value).strip()
    return text if text and text != "None" else None


def _number(row: dict[str, Any], column: str) -> float | None:
    """Read a numeric column. An unparseable figure is unknown, not zero.

    Non-finite input is rejected too: `float("INF")` parses happily, and an
    infinite financial figure is not a number anyone reported.
    """
    text = _text(row, column)
    if text is None:
        return None
    try:
        value = float(text.replace(",", ""))
    except ValueError:
        logger.warning("unparseable number in %s: %r", column, text)
        return None

    if not math.isfinite(value):
        logger.warning("non-finite number in %s: %r", column, text)
        return None
    return value


def _integer(row: dict[str, Any], column: str) -> int | None:
    """Read an integer column.

    XBRL writes `decimals="INF"` to mean "stated exactly, no rounding". That is
    a real and common value, and it is not an integer. It is read as unknown
    here because nothing consumes `decimals` numerically yet; `scale` still
    carries the display scale.
    """
    value = _number(row, column)
    return int(value) if value is not None else None


def parse_rows(rows: Sequence[dict[str, Any]]) -> list[ProviderFact]:
    """Parse every readable row, skipping and logging those that are not."""
    return list(_iter_facts(rows))


def _iter_facts(rows: Sequence[dict[str, Any]]) -> Iterator[ProviderFact]:
    for index, row in enumerate(rows):
        entity = _text(row, COL_ENTITY)
        filing = _text(row, COL_FILING)
        concept = _text(row, COL_TAG)
        raw_period = _text(row, COL_PERIOD)

        if not (entity and filing and concept and raw_period):
            logger.warning("row %d missing an identifying column; skipped", index)
            continue

        try:
            period = parse_period(raw_period)
        except PeriodParseError as exc:
            # A fact whose period cannot be read is unusable. Dropping it is
            # correct; guessing the period would corrupt every derived metric.
            logger.warning("row %d has an unreadable period (%s); skipped", index, exc)
            continue

        dimensions = {
            column: value
            for column in _DIMENSION_COLUMNS
            if (value := _text(row, column)) is not None
        }
        labels = {
            key: value
            for column, key in _LABEL_COLUMNS.items()
            if (value := _text(row, column)) is not None
        }

        yield ProviderFact(
            provider_entity_id=entity,
            provider_filing_id=filing,
            concept=concept,
            period=period,
            value=_number(row, COL_FACT),
            unit=_text(row, COL_MEASURE),
            scale=_integer(row, COL_SCALE),
            decimals=_integer(row, COL_DECIMALS),
            statement=_text(row, COL_STATEMENT),
            dimensions=dimensions,
            labels=labels,
        )


def distinct_filings(facts: Sequence[ProviderFact]) -> dict[str, set[str]]:
    """Map each filing reference to the entities that reported under it.

    MAGNA exposes no filing list, so the set of filings is discovered from the
    facts themselves.
    """
    discovered: dict[str, set[str]] = {}
    for fact in facts:
        discovered.setdefault(fact.provider_filing_id, set()).add(fact.provider_entity_id)
    return discovered


def find_conflicts(
    facts: Sequence[ProviderFact],
) -> dict[tuple[str, str, str, str], set[float | None]]:
    """Find facts that disagree across filings.

    The key is (entity, concept, period, dimension signature). More than one
    distinct value means a later filing restated an earlier one. The spike found
    exactly this in Matrix IT's total assets, so it is a real condition and not a
    theoretical one. Choosing which value wins is a policy decision recorded in
    docs/financial-methodology.md, not something this parser decides.
    """
    grouped: dict[tuple[str, str, str, str], set[float | None]] = {}
    for fact in facts:
        signature = "|".join(f"{k}={v}" for k, v in sorted(fact.dimensions.items()))
        key = (fact.provider_entity_id, fact.concept, fact.period.raw, signature)
        grouped.setdefault(key, set()).add(fact.value)
    return {key: values for key, values in grouped.items() if len(values) > 1}
