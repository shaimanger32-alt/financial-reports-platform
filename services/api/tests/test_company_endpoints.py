"""The public API contract.

What these pin down is mostly what the responses must never do: drop a metric
that could not be computed, lose the versions that produced a figure, or ship a
sentence the engine had no right to write.
"""

import json
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api.main import create_app
from database.repository import find_company
from ingestion.pipelines.magna import ingest_batch
from ingestion.pipelines.snapshots import generate_snapshots
from ingestion.providers.base import FactBatch, ProviderEntity
from ingestion.providers.magna_xbrl import parse_rows
from ingestion.seeding import seed_reference_data

pytestmark = pytest.mark.integration

FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "ingestion"
    / "tests"
    / "fixtures"
    / "magna_golden_matrix_hilan.json"
)

MATRIX = ProviderEntity(
    provider_entity_id="520039413",
    name='מטריקס אי.טי. בע"מ',
    name_en="MATRIX IT LTD",
    sector_code="8800",
    sector_name="טכנולוגיה",
)


@pytest.fixture
def loaded_client(session: Session, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """An API bound to a database holding one real company."""
    payload = FIXTURE.read_bytes()
    batch = FactBatch(
        facts=parse_rows(json.loads(payload)),
        raw_payload=payload,
        content_hash="api-test",
        retrieved_at="2026-08-11T00:00:00Z",
        source_reference="test",
    )
    seed_reference_data(session)
    ingest_batch(session, MATRIX, batch)
    company = find_company(session, "520039413")
    assert company is not None
    # Ingesting and publishing are separate acts, and `is_published` defaults to
    # false. These tests are about what a reader is served, so the company has to
    # be published for them to have a subject at all; the unpublished case is
    # covered by `test_an_unpublished_company_is_absent`.
    company.is_published = True
    generate_snapshots(session, company)
    session.flush()

    from contextlib import contextmanager

    @contextmanager
    def bound_session() -> Iterator[Session]:
        yield session

    monkeypatch.setattr("api.routers.companies.session_scope", bound_session)

    with TestClient(create_app(), raise_server_exceptions=False) as client:
        yield client


def test_companies_are_listed(loaded_client: TestClient) -> None:
    response = loaded_client.get("/v1/companies")

    assert response.status_code == 200
    body = response.json()
    assert [company["id"] for company in body] == ["520039413"]
    assert body[0]["reporting_currency"] == "ILS"


def test_a_company_reports_the_periods_it_can_answer_for(loaded_client: TestClient) -> None:
    response = loaded_client.get("/v1/companies/520039413")

    assert response.status_code == 200
    body = response.json()
    assert body["periods"]
    assert body["latest_period"] == body["periods"][-1]
    assert body["sector"] == "טכנולוגיה"


def test_an_unknown_company_is_a_404(loaded_client: TestClient) -> None:
    assert loaded_client.get("/v1/companies/999999999").status_code == 404


def test_an_unpublished_company_is_absent(loaded_client: TestClient, session: Session) -> None:
    """Unpublishing removes a company from the reader's view entirely.

    It reads as absent rather than as forbidden: "exists but you may not see it"
    would disclose more than it withholds. This is the whole reason a company can
    be loaded and hand-checked before anyone is shown it.
    """
    company = find_company(session, "520039413")
    assert company is not None
    company.is_published = False
    session.flush()

    assert loaded_client.get("/v1/companies").json() == []
    assert loaded_client.get("/v1/companies/520039413").status_code == 404
    assert loaded_client.get("/v1/companies/520039413/reports/latest").status_code == 404


def test_the_latest_report_carries_every_version(loaded_client: TestClient) -> None:
    """Spec section 33: a figure that cannot say which rules produced it cannot
    be audited later."""
    response = loaded_client.get("/v1/companies/520039413/reports/latest")

    assert response.status_code == 200
    versions = response.json()["versions"]
    assert set(versions) == {
        "analysis",
        "metrics",
        "rules",
        "thresholds",
        "mappings",
        "patterns",
        # Decision 0011: a metric's tier is resolved per market, so the figure
        # cannot be audited without knowing which tiering produced it.
        "tiering",
        "pulse",
    }
    assert all(versions.values())


def test_a_report_carries_its_patterns(loaded_client: TestClient) -> None:
    """A pattern names the signals it is made of, and claims nothing beyond
    them (spec section 16)."""
    response = loaded_client.get("/v1/companies/520039413/reports/latest")

    assert response.status_code == 200
    body = response.json()
    assert "patterns" in body

    raised = {signal["code"] for signal in body["signals"]}
    for pattern in body["patterns"]:
        members = [*pattern["signal_codes"], *pattern["optional_signal_codes"]]
        assert members, "a pattern with no signals behind it is not a pattern"
        assert set(members) <= raised, "a pattern may only cite signals this period raised"
        # Section 20 reserves high confidence for an explanation from the
        # filing, which no engine before phase 6 can supply.
        assert pattern["confidence"] != "high"
        assert pattern["explanation_status"] == "not_searched"
        assert pattern["message_key"].startswith("pattern.")


def test_unavailable_metrics_are_kept_with_their_missing_inputs(
    loaded_client: TestClient,
) -> None:
    """Dropping the row would read as though the metric did not exist. The truth
    is that the issuer did not report an input, or that the ratio would have been
    meaningless, and either way the reader is entitled to know which
    (spec section 4.4).
    """
    body = loaded_client.get("/v1/companies/520039413/reports/latest").json()

    unavailable = [metric for metric in body["metrics"] if metric["value"] is None]
    assert unavailable, "the fixture should leave some metrics uncomputable"

    for metric in unavailable:
        assert metric["missing_inputs"] or metric["warnings"], (
            f"{metric['code']} is null with no explanation"
        )


def test_metrics_declare_their_tier(loaded_client: TestClient) -> None:
    body = loaded_client.get("/v1/companies/520039413/reports/latest").json()

    tiers = {metric["tier"] for metric in body["metrics"]}
    assert tiers == {"core", "extended"}


def test_signals_carry_a_message_key_and_no_prose(loaded_client: TestClient) -> None:
    """Section 42: the wording lives in the client, so no engine can assert a
    cause on its way out."""
    body = loaded_client.get("/v1/companies/520039413/reports/latest").json()

    for signal in body["signals"]:
        assert signal["message_key"].startswith("signal.")
        assert signal["confidence"] in {"low", "medium", "high"}


def test_a_named_period_can_be_requested(loaded_client: TestClient) -> None:
    periods = loaded_client.get("/v1/companies/520039413").json()["periods"]

    response = loaded_client.get(f"/v1/companies/520039413/reports/{periods[0]}")

    assert response.status_code == 200
    assert response.json()["period_code"] == periods[0]


def test_a_period_with_no_analysis_is_a_404(loaded_client: TestClient) -> None:
    assert loaded_client.get("/v1/companies/520039413/reports/1999-Q1").status_code == 404


def test_a_series_keeps_gaps_visible(loaded_client: TestClient) -> None:
    """A period where the metric could not be computed appears as a null point
    rather than being skipped, so a gap in a chart looks like a gap."""
    response = loaded_client.get("/v1/companies/520039413/series/gross_margin")

    assert response.status_code == 200
    body = response.json()
    assert body["name_he"]
    assert body["points"]
    assert all("period" in point and "value" in point for point in body["points"])


def test_series_values_match_the_report_they_came_from(loaded_client: TestClient) -> None:
    """Charts and report pages read the same snapshots, so they cannot disagree."""
    report = loaded_client.get("/v1/companies/520039413/reports/latest").json()
    series = loaded_client.get("/v1/companies/520039413/series/current_ratio").json()

    from_report = next(m["value"] for m in report["metrics"] if m["code"] == "current_ratio")
    from_series = next(
        point["value"] for point in series["points"] if point["period"] == report["period_code"]
    )

    assert from_report == pytest.approx(from_series) if from_report else from_series is None


def test_an_unknown_metric_is_a_404(loaded_client: TestClient) -> None:
    assert loaded_client.get("/v1/companies/520039413/series/not_a_metric").status_code == 404


def test_money_survives_as_a_number_not_a_string(loaded_client: TestClient) -> None:
    body = loaded_client.get("/v1/companies/520039413/reports/latest").json()

    working_capital = next(m for m in body["metrics"] if m["code"] == "working_capital")
    assert isinstance(working_capital["value"], float | int | type(None))
    assert not isinstance(working_capital["value"], Decimal)
