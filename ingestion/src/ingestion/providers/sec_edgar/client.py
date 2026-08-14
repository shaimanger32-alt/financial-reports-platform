"""SEC EDGAR provider client. Read-only.

EDGAR needs no API key and no registration. Its whole access requirement is a
`User-Agent` naming the caller with a contact address, and a request rate under
ten a second. Both are stated in SEC's fair-access policy; requests without a
User-Agent are refused outright, which is why this client will not start without
one configured rather than silently sending a default.

The endpoint used is `companyfacts`, which returns every XBRL fact a company has
ever filed in one document. That is fact-oriented rather than filing-oriented,
which is exactly the shape decision 0008's protocol was built around, so nothing
above this layer changes.
"""

import json
import logging
import time
from collections.abc import Sequence
from datetime import UTC, datetime

import httpx

from ingestion.archive import content_hash
from ingestion.config import IngestionSettings, get_ingestion_settings
from ingestion.providers.base import (
    FactBatch,
    FactQuery,
    FilingReference,
    ProviderConcept,
    ProviderEntity,
    ProviderError,
    ProviderNotSupportedError,
    ProviderUnavailableError,
)
from ingestion.providers.sec_edgar.parser import parse_company_facts

logger = logging.getLogger(__name__)

PROVIDER_CODE = "sec_edgar"

CIK_DIGITS = 10


def normalise_cik(value: str | int) -> str:
    """EDGAR keys companies by a ten-digit zero-padded CIK."""
    digits = str(value).strip().upper().removeprefix("CIK")
    if not digits.isdigit():
        raise ValueError(f"not a CIK: {value!r}")
    return digits.zfill(CIK_DIGITS)


class SecEdgarClient:
    """Client for the SEC EDGAR structured company facts API."""

    provider_code = PROVIDER_CODE

    def __init__(
        self,
        settings: IngestionSettings | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self._settings = settings or get_ingestion_settings()
        user_agent = self._settings.sec_edgar_user_agent.strip()
        if not user_agent and client is None:
            raise ProviderError(
                "SEC_EDGAR_USER_AGENT is not set. SEC requires a User-Agent naming "
                "the caller and a contact address, for example "
                "'Report Intelligence someone@example.com'. It refuses requests without one."
            )
        self._client = client or httpx.Client(
            timeout=self._settings.sec_edgar_request_timeout_seconds,
            headers={"User-Agent": user_agent, "Accept": "application/json"},
            follow_redirects=True,
        )
        self._last_request_at: float = 0.0

    # -- rate limiting ----------------------------------------------------

    def _pace(self) -> None:
        """Keep under SEC's ten-requests-a-second ceiling.

        Deliberately a sleep rather than a retry on rejection: being asked to
        slow down after the fact means we already sent traffic that a public
        regulator did not want.
        """
        interval = self._settings.sec_edgar_min_request_interval_seconds
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < interval:
            time.sleep(interval - elapsed)
        self._last_request_at = time.monotonic()

    def _get(self, url: str) -> bytes:
        self._pace()
        try:
            response = self._client.get(url)
        except httpx.HTTPError as error:
            raise ProviderUnavailableError(f"SEC EDGAR request failed: {error}") from error

        if response.status_code == httpx.codes.NOT_FOUND:
            raise ProviderError(f"SEC EDGAR has no document at {url}")
        if response.status_code >= httpx.codes.BAD_REQUEST:
            raise ProviderUnavailableError(f"SEC EDGAR answered {response.status_code} for {url}")
        return response.content

    # -- protocol ---------------------------------------------------------

    def list_entities(self) -> Sequence[ProviderEntity]:
        """Every company with a ticker in SEC's published index.

        SEC does not classify companies by sector in this file, so sector is
        left as None rather than filled with a guess. Sector-dependent analysis
        (spec section 18) needs a source that actually carries one.
        """
        payload = self._get(f"{self._settings.sec_edgar_files_base_url}/company_tickers.json")
        document = json.loads(payload)

        entities: list[ProviderEntity] = []
        for row in document.values():
            cik = row.get("cik_str")
            if cik is None:
                continue
            entities.append(
                ProviderEntity(
                    provider_entity_id=normalise_cik(cik),
                    name=str(row.get("title") or ""),
                    name_en=str(row.get("title") or ""),
                    sector_code=None,
                    sector_name=None,
                )
            )
        return entities

    def list_concepts(self) -> Sequence[ProviderConcept]:
        """Not offered as a standalone endpoint.

        EDGAR publishes no taxonomy index for `companyfacts`. The concepts a
        company uses are discovered from its own payload, which `fetch_facts`
        returns in full.
        """
        raise ProviderNotSupportedError(
            "SEC EDGAR does not expose a taxonomy listing; concepts come from companyfacts."
        )

    def fetch_facts(self, query: FactQuery) -> FactBatch:
        """Every fact a company has filed.

        `companyfacts` is not filterable server side, so the year and concept
        filters in `FactQuery` are not sent upstream. Filtering happens after
        parsing, which costs one large request per company and keeps the raw
        payload complete for the archive.
        """
        if len(query.entity_ids) != 1:
            raise ProviderNotSupportedError(
                "SEC EDGAR serves one company per request; ask for exactly one entity."
            )

        cik = normalise_cik(query.entity_ids[0])
        url = f"{self._settings.sec_edgar_api_base_url}/companyfacts/CIK{cik}.json"
        payload = self._get(url)

        facts = parse_company_facts(payload, cik)
        if query.concepts:
            wanted = set(query.concepts)
            facts = [fact for fact in facts if fact.concept in wanted]
        if query.from_year and query.to_year:
            facts = [
                fact for fact in facts if query.from_year <= fact.period.end.year <= query.to_year
            ]

        return FactBatch(
            facts=facts,
            raw_payload=payload,
            content_hash=content_hash(payload),
            retrieved_at=datetime.now(UTC).isoformat(),
            source_reference=f"companyfacts/CIK{cik}",
        )

    def list_filings(self, entity_id: str, forms: Sequence[str] = ()) -> list[FilingReference]:
        """Recent filings for one company, newest first.

        EDGAR's `submissions` endpoint carries the primary document name for
        each filing, which is what turns an accession number into a URL. Without
        it the archive path is a directory listing to be guessed at.
        """
        cik = normalise_cik(entity_id)
        payload = self._get(f"{self._settings.sec_edgar_data_base_url}/submissions/CIK{cik}.json")
        recent = json.loads(payload).get("filings", {}).get("recent", {})

        wanted = {form.upper() for form in forms}
        references: list[FilingReference] = []
        for index, form in enumerate(recent.get("form", [])):
            if wanted and form.upper() not in wanted:
                continue
            accession = recent["accessionNumber"][index]
            document = recent.get("primaryDocument", [""] * (index + 1))[index]
            if not document:
                continue
            references.append(
                FilingReference(
                    provider_filing_id=accession,
                    form=form,
                    filed=recent.get("filingDate", [""] * (index + 1))[index],
                    period_end=recent.get("reportDate", [""] * (index + 1))[index],
                    document_url=(
                        f"{self._settings.sec_edgar_archives_base_url}/data/"
                        f"{int(cik)}/{accession.replace('-', '')}/{document}"
                    ),
                )
            )
        return references

    def fetch_document(self, provider_filing_id: str) -> bytes:
        """A filing's primary document.

        Needs the company to resolve the archive path, which an accession number
        alone does not give. Callers holding a `FilingReference` should use
        `fetch_document_at`; this exists to satisfy the provider protocol and
        says plainly what it is missing rather than guessing a URL.
        """
        raise ProviderNotSupportedError(
            "a filing's archive path needs its company and primary document name; "
            "use list_filings to get a FilingReference, then fetch_document_at"
        )

    def fetch_document_at(self, url: str) -> bytes:
        """The document at a URL from `list_filings`.

        Paced like every other request. A 10-Q runs to a few megabytes, and
        these are a public regulator's servers.
        """
        return self._get(url)
