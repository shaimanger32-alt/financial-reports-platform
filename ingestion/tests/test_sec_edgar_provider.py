"""The SEC EDGAR provider.

The fixture is a real `companyfacts` response for Apple, trimmed to eight
concepts and 1,431 rows. Nothing in it was composed: the fiscal calendar tests
below pass or fail against what Apple actually filed, including the 53-week
years that are the whole reason this provider needs a calendar at all.
"""

import json
from datetime import date, timedelta
from itertools import pairwise
from pathlib import Path

import httpx
import pytest

from financial_core.periods import classify, classify_in
from ingestion.config import IngestionSettings
from ingestion.providers.base import FactQuery, ProviderError, ProviderNotSupportedError
from ingestion.providers.sec_edgar import (
    SecEdgarClient,
    learn_fiscal_calendar,
    normalise_cik,
    parse_company_facts,
)

FIXTURE = Path(__file__).parent / "fixtures" / "apple_companyfacts.json"
PAYLOAD = FIXTURE.read_bytes()
DOCUMENT = json.loads(PAYLOAD)


class TestCik:
    @pytest.mark.parametrize("value", [320193, "320193", "CIK0000320193", "0000320193"])
    def test_every_form_normalises_to_ten_digits(self, value: str | int) -> None:
        assert normalise_cik(value) == "0000320193"

    def test_a_non_numeric_cik_is_refused(self) -> None:
        with pytest.raises(ValueError, match="not a CIK"):
            normalise_cik("AAPL")


class TestFiscalCalendar:
    CALENDAR = learn_fiscal_calendar(DOCUMENT)

    def test_apples_fiscal_years_are_reconstructed(self) -> None:
        assert not self.CALENDAR.is_empty

        window = self.CALENDAR.window_for_year(2025)
        assert window is not None
        assert (window.start, window.end) == (date(2024, 9, 29), date(2025, 9, 27))

    def test_the_fifty_three_week_years_are_recognised_as_filed(self) -> None:
        """2012, 2017 and 2023 each ran 371 days. A rule that assumed 364 or 365
        would misplace every quarter that followed."""
        long_years = [window.fiscal_year for window in self.CALENDAR.windows if window.days == 371]

        assert long_years == [2012, 2017, 2023]

    def test_a_year_is_labelled_by_its_own_report_not_a_comparative(self) -> None:
        """Apple's fiscal 2023 appears tagged fy=2023, 2024 and 2025, because
        later filings carry it as a comparative. The lowest label is the year's
        own annual report."""
        window = self.CALENDAR.window_for_year(2023)

        assert window is not None
        assert (window.start, window.end) == (date(2022, 9, 25), date(2023, 9, 30))

    def test_no_two_fiscal_years_overlap(self) -> None:
        for earlier, later in pairwise(self.CALENDAR.windows):
            assert earlier.end < later.start

    def test_the_calendar_classifies_what_the_calendar_year_rule_could_not(self) -> None:
        """The measurement that justified this whole piece of work."""
        rows = [
            (row.get("start"), row["end"])
            for concept in DOCUMENT["facts"]["us-gaap"].values()
            for unit in concept["units"].values()
            for row in unit
        ]
        old = sum(
            classify(date.fromisoformat(s) if s else None, date.fromisoformat(e)) is not None
            for s, e in rows
        )
        new = sum(
            classify_in(date.fromisoformat(s) if s else None, date.fromisoformat(e), self.CALENDAR)
            is not None
            for s, e in rows
        )

        assert old / len(rows) < 0.10
        # Not 100%, and deliberately. The remainder are comparatives older than
        # any fiscal year Apple's own annual reports name in this payload, and
        # labelling them would mean guessing which year they belong to.
        assert new / len(rows) > 0.97

    def test_the_only_rows_left_unclassified_are_outside_the_declared_years(self) -> None:
        """Refusing them is the point. Boundaries we were never told about are
        not invented, and a period labelled with a year it is not produces a
        growth rate that is confidently, unrecoverably wrong."""
        earliest = self.CALENDAR.windows[0].start
        unclassified = [
            row["end"]
            for concept in DOCUMENT["facts"]["us-gaap"].values()
            for unit in concept["units"].values()
            for row in unit
            if classify_in(
                date.fromisoformat(row["start"]) if row.get("start") else None,
                date.fromisoformat(row["end"]),
                self.CALENDAR,
            )
            is None
        ]

        assert unclassified
        assert all(date.fromisoformat(end) < earliest for end in unclassified)

    def test_no_two_windows_claim_the_same_fiscal_year(self) -> None:
        """The bug this guards: Apple's fiscal 2008 and fiscal 2009 were both
        labelled 2009, because only the later filing's comparatives were held
        and a comparative carries the *filing's* year. Four different years'
        revenue landed in one period, and fiscal 2010 growth read as 171.7%
        against a real 52%."""
        years = [window.fiscal_year for window in self.CALENDAR.windows]

        assert len(years) == len(set(years))

    def test_every_window_is_labelled_close_to_the_year_it_ends_in(self) -> None:
        """A retailer closing in January calls it the previous year, so one is
        allowed. Two means the label came from a comparative."""
        for window in self.CALENDAR.windows:
            assert abs(window.fiscal_year - window.end.year) <= 1

    def test_the_year_in_progress_is_covered(self) -> None:
        """The year a company is currently reporting has no annual report yet,
        and is exactly the year a reader opens the product for. Without it the
        most recent quarters classify as nothing."""
        latest = self.CALENDAR.windows[-1]

        assert latest.is_projected
        assert latest.fiscal_year > 2025

    def test_the_projected_year_starts_where_the_company_said(self) -> None:
        """Only the end is carried over. The start is observed, from the
        year-to-date window every quarterly report opens with."""
        declared = [w for w in self.CALENDAR.windows if not w.is_projected]
        projected = self.CALENDAR.windows[-1]

        assert projected.start == declared[-1].end + timedelta(days=1)

    def test_only_the_year_in_progress_is_ever_projected(self) -> None:
        """Everything a company has closed, it has declared."""
        projected = [w for w in self.CALENDAR.windows if w.is_projected]

        assert len(projected) <= 1
        if projected:
            assert projected[0] is self.CALENDAR.windows[-1]

    def test_a_payload_with_no_annual_filings_yields_an_empty_calendar(self) -> None:
        """Empty classifies nothing, which beats assuming December."""
        quarterly_only = {
            "facts": {
                "us-gaap": {
                    "Assets": {
                        "units": {
                            "USD": [
                                {"end": "2025-06-28", "val": 1, "fy": 2025, "form": "10-Q"},
                            ]
                        }
                    }
                }
            }
        }

        assert learn_fiscal_calendar(quarterly_only).is_empty


class TestParsing:
    FACTS = parse_company_facts(PAYLOAD, "0000320193")

    def test_every_row_becomes_a_fact(self) -> None:
        assert len(self.FACTS) == 1431

    def test_instants_and_durations_are_told_apart(self) -> None:
        kinds = {fact.period.kind for fact in self.FACTS}

        assert kinds == {"instant", "duration"}

    def test_a_balance_sheet_figure_carries_no_start(self) -> None:
        assets = [fact for fact in self.FACTS if fact.concept == "us-gaap:Assets"]

        assert assets
        assert all(fact.period.kind == "instant" and fact.period.start is None for fact in assets)

    def test_the_concept_keeps_its_taxonomy(self) -> None:
        assert all(fact.concept.startswith("us-gaap:") for fact in self.FACTS)

    def test_the_filing_is_identified_by_its_accession_number(self) -> None:
        assert all(fact.provider_filing_id for fact in self.FACTS)

    def test_the_real_publication_date_is_kept(self) -> None:
        """MAGNA supplies none, which forced decision 0009 to infer recency from
        a reference number. SEC states it, so nothing is inferred here."""
        assert all(fact.labels.get("filed") for fact in self.FACTS)

    def test_a_fact_repeats_across_filings(self) -> None:
        """Comparatives, exactly as in MAGNA. Deduplication with lineage is a
        correctness requirement, not an optimisation."""
        keys = [(fact.concept, fact.period.raw) for fact in self.FACTS]

        assert len(keys) > len(set(keys))


class TestClient:
    def _client(self, handler: object) -> SecEdgarClient:
        assert callable(handler)
        settings = IngestionSettings(sec_edgar_user_agent="Test test@example.com")
        transport = httpx.MockTransport(handler)
        return SecEdgarClient(
            settings=settings,
            client=httpx.Client(transport=transport, headers={"User-Agent": "Test"}),
        )

    def test_it_refuses_to_start_without_a_user_agent(self) -> None:
        """SEC rejects such requests outright. Failing here beats being blocked
        by a regulator for anonymous traffic."""
        with pytest.raises(ProviderError, match="SEC_EDGAR_USER_AGENT"):
            SecEdgarClient(settings=IngestionSettings(sec_edgar_user_agent=""))

    def test_it_fetches_and_parses_company_facts(self) -> None:
        client = self._client(lambda request: httpx.Response(200, content=PAYLOAD))
        batch = client.fetch_facts(FactQuery(entity_ids=["320193"]))

        assert len(batch.facts) == 1431
        assert batch.content_hash
        assert batch.source_reference == "companyfacts/CIK0000320193"
        assert batch.raw_payload == PAYLOAD

    def test_the_raw_payload_travels_with_the_result(self) -> None:
        """Spec section 32 step 4: archived so it can be reprocessed without
        calling a public regulator again."""
        client = self._client(lambda request: httpx.Response(200, content=PAYLOAD))
        batch = client.fetch_facts(FactQuery(entity_ids=["320193"]))

        assert json.loads(batch.raw_payload)["entityName"] == "Apple Inc."

    def test_a_year_filter_is_applied_after_parsing(self) -> None:
        client = self._client(lambda request: httpx.Response(200, content=PAYLOAD))
        batch = client.fetch_facts(FactQuery(entity_ids=["320193"], from_year=2024, to_year=2025))

        assert batch.facts
        assert all(2024 <= fact.period.end.year <= 2025 for fact in batch.facts)

    def test_a_concept_filter_is_applied_after_parsing(self) -> None:
        client = self._client(lambda request: httpx.Response(200, content=PAYLOAD))
        batch = client.fetch_facts(FactQuery(entity_ids=["320193"], concepts=["us-gaap:Assets"]))

        assert batch.facts
        assert {fact.concept for fact in batch.facts} == {"us-gaap:Assets"}

    def test_it_asks_for_one_company_at_a_time(self) -> None:
        client = self._client(lambda request: httpx.Response(200, content=PAYLOAD))

        with pytest.raises(ProviderNotSupportedError, match="exactly one entity"):
            client.fetch_facts(FactQuery(entity_ids=["320193", "1045810"]))

    def test_documents_are_not_offered_yet(self) -> None:
        client = self._client(lambda request: httpx.Response(200, content=PAYLOAD))

        with pytest.raises(ProviderNotSupportedError):
            client.fetch_document("0000320193-26-000008")

    def test_a_taxonomy_listing_is_not_offered(self) -> None:
        client = self._client(lambda request: httpx.Response(200, content=PAYLOAD))

        with pytest.raises(ProviderNotSupportedError):
            client.list_concepts()

    def test_the_entity_index_is_parsed(self) -> None:
        index = json.dumps(
            {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}}
        ).encode()
        client = self._client(lambda request: httpx.Response(200, content=index))
        entities = client.list_entities()

        assert [entity.provider_entity_id for entity in entities] == ["0000320193"]

    def test_sector_is_null_rather_than_guessed(self) -> None:
        """SEC's ticker index carries no sector. Section 4.4: unknown is null."""
        index = json.dumps(
            {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}}
        ).encode()
        client = self._client(lambda request: httpx.Response(200, content=index))

        assert client.list_entities()[0].sector_name is None
