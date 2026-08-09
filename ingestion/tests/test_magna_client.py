"""MAGNA client behaviour, against a stubbed transport.

The asynchronous search flow is the part most likely to break in production and
the part the published specification gets wrong, so it is pinned down here:
submit, poll through 403s, then read the published file.
"""

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from ingestion.config import IngestionSettings
from ingestion.providers.base import FactQuery, ProviderError, ProviderNotSupportedError
from ingestion.providers.magna_xbrl import MagnaXbrlClient

INIT_FIXTURE = Path(__file__).parent / "fixtures" / "magna_init.json"
SEARCH_FIXTURE = Path(__file__).parent / "fixtures" / "magna_search_matrix.json"

GUID = "3cbd96dd-88bf-4fd8-8bd0-70457643876d"


@pytest.fixture
def settings() -> IngestionSettings:
    return IngestionSettings(
        magna_api_base_url="https://magna.test/api",
        magna_results_base_url="https://magna.test/public/search",
        magna_poll_initial_delay_seconds=0.0,
        magna_poll_max_delay_seconds=0.0,
        magna_poll_attempts=5,
    )


@pytest.fixture(autouse=True)
def _no_sleeping(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("ingestion.providers.magna_xbrl.client.time.sleep", lambda _: None)


def _client(settings: IngestionSettings, handler: Any) -> MagnaXbrlClient:
    transport = httpx.MockTransport(handler)
    return MagnaXbrlClient(settings=settings, client=httpx.Client(transport=transport))


def test_entities_are_mapped_with_sector_names(settings: IngestionSettings) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/init"
        return httpx.Response(200, content=INIT_FIXTURE.read_bytes())

    with _client(settings, handler) as client:
        entities = client.list_entities()

    assert entities
    matrix = next(e for e in entities if e.provider_entity_id == "520039413")
    assert matrix.name_en == "MATRIX IT LTD"
    assert matrix.sector_code == "8800"
    assert matrix.sector_name == "טכנולוגיה"


def test_init_is_fetched_once_and_cached(settings: IngestionSettings) -> None:
    """The specification states these values change rarely."""
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, content=INIT_FIXTURE.read_bytes())

    with _client(settings, handler) as client:
        client.list_entities()
        client.list_concepts()
        client.list_entities()

    assert calls == 1


def test_company_extensions_are_identified(settings: IngestionSettings) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=INIT_FIXTURE.read_bytes())

    with _client(settings, handler) as client:
        concepts = client.list_concepts()

    standard = [c for c in concepts if not c.is_extension]
    extensions = [c for c in concepts if c.is_extension]

    assert standard and extensions
    assert all(c.namespace == "ifrs-full" for c in standard)


def test_search_polls_through_pending_responses(settings: IngestionSettings) -> None:
    """A 403 means 'not generated yet', not 'failed'."""
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        if request.method == "POST":
            body = json.loads(request.content)
            assert body["fromYear"] == 2023
            assert body["entities"] == [{"_id": "520039413"}]
            return httpx.Response(200, json={"guid": GUID, "status": "pending"})

        assert request.url.path == f"/public/search/{GUID}.json"
        attempts += 1
        if attempts < 3:
            return httpx.Response(403, json={"message": "Missing Authentication Token"})
        return httpx.Response(200, content=SEARCH_FIXTURE.read_bytes())

    with _client(settings, handler) as client:
        batch = client.fetch_facts(
            FactQuery(
                entity_ids=("520039413",),
                concepts=("ifrs-full:Revenue",),
                from_year=2023,
                to_year=2024,
            )
        )

    assert attempts == 3
    assert batch.facts
    assert batch.content_hash
    assert batch.source_reference.endswith(GUID)


def test_search_gives_up_after_the_attempt_budget(settings: IngestionSettings) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(200, json={"guid": GUID, "status": "pending"})
        return httpx.Response(403, json={"message": "Missing Authentication Token"})

    with (
        _client(settings, handler) as client,
        pytest.raises(ProviderError, match="still pending"),
    ):
        client.fetch_facts(FactQuery(concepts=("ifrs-full:Revenue",), from_year=2023, to_year=2023))


def test_missing_guid_is_an_error(settings: IngestionSettings) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "pending"})

    with (
        _client(settings, handler) as client,
        pytest.raises(ProviderError, match="no guid"),
    ):
        client.fetch_facts(FactQuery(concepts=("ifrs-full:Revenue",), from_year=2023, to_year=2023))


def test_year_range_is_required(settings: IngestionSettings) -> None:
    """MAGNA rejects a query without a year range; fail before the network call."""
    with (
        _client(settings, lambda r: httpx.Response(200, json={})) as client,
        pytest.raises(ValueError, match="from_year and to_year"),
    ):
        client.fetch_facts(FactQuery(concepts=("ifrs-full:Revenue",)))


def test_documents_are_not_available(settings: IngestionSettings) -> None:
    """The query API serves facts only. Phase 6 needs a different source."""
    with (
        _client(settings, lambda r: httpx.Response(200, json={})) as client,
        pytest.raises(ProviderNotSupportedError),
    ):
        client.fetch_document("2023-01-104698")


def test_client_satisfies_the_provider_protocol(settings: IngestionSettings) -> None:
    from ingestion.providers import FinancialDataProvider

    with _client(settings, lambda r: httpx.Response(200, json={})) as client:
        assert isinstance(client, FinancialDataProvider)
