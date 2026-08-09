"""MAGNA XBRL provider client. Read-only.

The published specification (magna-xbrl-api.pdf, dated 2023-08-07) describes a
synchronous `/search` that answers with `{"status", "file", "count"}`. The live
API does not behave that way. It answers with `{"guid", "status": "pending"}` and
publishes the result under `/public/search/{guid}.json`, which returns 403 until
the file is ready. There is no status endpoint. This client implements the
observed behaviour; the discrepancy is recorded in docs/decisions/0007.
"""

import json
import logging
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

import httpx

from ingestion.archive import content_hash
from ingestion.config import IngestionSettings, get_ingestion_settings
from ingestion.providers.base import (
    FactBatch,
    FactQuery,
    ProviderConcept,
    ProviderEntity,
    ProviderError,
    ProviderNotSupportedError,
    ProviderUnavailableError,
)
from ingestion.providers.magna_xbrl.parser import parse_rows

logger = logging.getLogger(__name__)

PROVIDER_CODE = "magna_xbrl"

# Returned while the result file is still being generated. Not an error.
_RESULT_PENDING_STATUS = 403


class MagnaXbrlClient:
    """Client for the Israel Securities Authority MAGNA XBRL query API."""

    provider_code = PROVIDER_CODE

    def __init__(
        self,
        settings: IngestionSettings | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self._settings = settings or get_ingestion_settings()
        self._client = client or httpx.Client(
            timeout=self._settings.magna_request_timeout_seconds,
            headers={"Accept": "application/json"},
            follow_redirects=True,
        )
        self._init_payload: dict[str, Any] | None = None

    # -- init -------------------------------------------------------------

    def fetch_init(self, *, refresh: bool = False) -> dict[str, Any]:
        """Fetch and cache the initialisation payload.

        The specification states these values change rarely, so it is cached for
        the lifetime of the client rather than re-fetched per query.
        """
        if self._init_payload is not None and not refresh:
            return self._init_payload

        url = f"{self._settings.magna_api_base_url}/init"
        try:
            response = self._client.get(url)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(f"GET {url} failed: {exc}") from exc

        try:
            payload: dict[str, Any] = json.loads(response.content)
        except json.JSONDecodeError as exc:
            raise ProviderError(f"GET {url} returned invalid JSON: {exc}") from exc

        self._init_payload = payload
        return payload

    @property
    def raw_init_bytes(self) -> bytes:
        """The cached init payload re-encoded, for archiving."""
        return json.dumps(self.fetch_init(), ensure_ascii=False).encode("utf-8")

    def list_entities(self) -> Sequence[ProviderEntity]:
        """Every entity that has filed iXBRL data."""
        payload = self.fetch_init()
        branches = {branch.get("_id"): branch.get("name") for branch in payload.get("branches", [])}
        return [
            ProviderEntity(
                provider_entity_id=str(entity["_id"]),
                name=entity.get("name") or "",
                name_en=entity.get("name_en"),
                sector_code=str(entity["branch_id"]) if entity.get("branch_id") else None,
                sector_name=branches.get(entity.get("branch_id")),
            )
            for entity in payload.get("entities", [])
            if entity.get("_id")
        ]

    def list_concepts(self) -> Sequence[ProviderConcept]:
        """Every XBRL tag present in the corpus, standard and company extensions."""
        payload = self.fetch_init()
        seen: set[tuple[str, str | None]] = set()
        concepts: list[ProviderConcept] = []
        for tag in payload.get("tags", []):
            name = tag.get("name")
            if not name:
                continue
            key = (name, tag.get("label"))
            if key in seen:
                continue
            seen.add(key)
            concepts.append(ProviderConcept(name=name, label=tag.get("label")))
        return concepts

    # -- search -----------------------------------------------------------

    def fetch_facts(self, query: FactQuery) -> FactBatch:
        """Run a query and return the parsed facts with their raw payload."""
        guid = self._submit_search(query)
        raw = self._await_result(guid)

        try:
            rows: list[dict[str, Any]] = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ProviderError(f"result file {guid} is not valid JSON: {exc}") from exc

        if not isinstance(rows, list):
            raise ProviderError(f"result file {guid} is not a list of rows")

        return FactBatch(
            facts=parse_rows(rows),
            raw_payload=raw,
            content_hash=content_hash(raw),
            retrieved_at=datetime.now(UTC).isoformat(),
            source_reference=f"{PROVIDER_CODE}:search:{guid}",
        )

    def _submit_search(self, query: FactQuery) -> str:
        """Submit a query and return the job identifier."""
        if not query.from_year or not query.to_year:
            raise ValueError("from_year and to_year are required by the MAGNA API")

        body = {
            "branches": [],
            "entities": [{"_id": entity_id} for entity_id in query.entity_ids],
            "xbrlFields": [{"name": concept} for concept in query.concepts],
            "fromYear": query.from_year,
            "toYear": query.to_year,
            "quarters": list(query.quarters),
        }

        url = f"{self._settings.magna_api_base_url}/search"
        try:
            response = self._client.post(url, json=body)
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(f"POST {url} failed: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise ProviderError(f"POST {url} returned invalid JSON: {exc}") from exc

        guid = payload.get("guid")
        if not guid:
            raise ProviderError(f"POST {url} returned no guid: {payload!r}")

        logger.info("magna search submitted: guid=%s status=%s", guid, payload.get("status"))
        return str(guid)

    def _await_result(self, guid: str) -> bytes:
        """Poll the published result file until it exists.

        A 403 means the file has not been generated yet, so it is retried with a
        widening delay rather than treated as a failure.
        """
        url = f"{self._settings.magna_results_base_url}/{guid}.json"
        delay = self._settings.magna_poll_initial_delay_seconds

        for attempt in range(1, self._settings.magna_poll_attempts + 1):
            try:
                response = self._client.get(url)
            except httpx.HTTPError as exc:
                raise ProviderUnavailableError(f"GET {url} failed: {exc}") from exc

            if response.status_code == httpx.codes.OK:
                logger.info("magna result ready after %d attempt(s): %s", attempt, guid)
                return response.content

            if response.status_code != _RESULT_PENDING_STATUS:
                raise ProviderError(f"GET {url} returned HTTP {response.status_code}")

            logger.debug(
                "magna result pending (attempt %d/%d)", attempt, self._settings.magna_poll_attempts
            )
            time.sleep(delay)
            delay = min(delay * 1.5, self._settings.magna_poll_max_delay_seconds)

        raise ProviderUnavailableError(
            f"result {guid} was still pending after {self._settings.magna_poll_attempts} attempts"
        )

    # -- documents --------------------------------------------------------

    def fetch_document(self, provider_filing_id: str) -> bytes:
        """Not available through this API.

        The query interface returns facts only. Full filing documents, needed for
        the evidence engine in phase 6, must come from a separate MAGNA/MAYA
        source whose licensing is reviewed first (spec section 7.4).
        """
        raise ProviderNotSupportedError(
            "the MAGNA XBRL query API does not serve filing documents; "
            f"cannot fetch {provider_filing_id}"
        )

    def close(self) -> None:
        """Release the underlying HTTP connection pool."""
        self._client.close()

    def __enter__(self) -> "MagnaXbrlClient":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
