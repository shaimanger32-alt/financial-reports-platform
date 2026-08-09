"""Raw payload archive.

Spec section 32, step 4: keep the source payload with its hash so the pipeline
can be reprocessed after a code change without asking the provider again. The
archive is append-only and content-addressed, which also makes ingestion
idempotent -- the same payload fetched twice occupies one file (section 33).
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


def content_hash(payload: bytes) -> str:
    """Stable identity of a payload."""
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class ArchivedPayload:
    """Where a payload landed and what it is."""

    path: Path
    metadata_path: Path
    content_hash: str
    already_present: bool


class RawArchive:
    """Content-addressed store for provider payloads."""

    def __init__(self, root: Path | str) -> None:
        self._root = Path(root)

    def store(
        self,
        payload: bytes,
        *,
        provider: str,
        kind: str,
        source_reference: str,
        extension: str = "json",
    ) -> ArchivedPayload:
        """Archive a payload, skipping the write when it is already held.

        `source_reference` records what was asked for, so an archived file can be
        traced back to the request that produced it.
        """
        digest = content_hash(payload)
        directory = self._root / provider / kind
        directory.mkdir(parents=True, exist_ok=True)

        path = directory / f"{digest[:16]}.{extension}"
        metadata_path = directory / f"{digest[:16]}.meta.json"

        if path.exists():
            return ArchivedPayload(path, metadata_path, digest, already_present=True)

        path.write_bytes(payload)
        metadata_path.write_text(
            json.dumps(
                {
                    "provider": provider,
                    "kind": kind,
                    "source_reference": source_reference,
                    "content_hash": digest,
                    "byte_size": len(payload),
                    "archived_at": datetime.now(UTC).isoformat(),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return ArchivedPayload(path, metadata_path, digest, already_present=False)
