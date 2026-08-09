"""Raw payload archive.

Content addressing is what makes re-ingestion idempotent (spec section 33): the
same payload fetched twice must not produce a second copy or a second filing.
"""

import json
from pathlib import Path

from ingestion.archive import RawArchive, content_hash


def test_payload_is_stored_with_metadata(tmp_path: Path) -> None:
    archive = RawArchive(tmp_path)
    payload = b'[{"Tag": "ifrs-full:Revenue"}]'

    stored = archive.store(
        payload,
        provider="magna_xbrl",
        kind="search",
        source_reference="magna_xbrl:search:abc",
    )

    assert not stored.already_present
    assert stored.path.read_bytes() == payload
    assert stored.content_hash == content_hash(payload)

    metadata = json.loads(stored.metadata_path.read_text(encoding="utf-8"))
    assert metadata["provider"] == "magna_xbrl"
    assert metadata["source_reference"] == "magna_xbrl:search:abc"
    assert metadata["byte_size"] == len(payload)


def test_storing_the_same_payload_twice_is_idempotent(tmp_path: Path) -> None:
    archive = RawArchive(tmp_path)
    payload = b"identical bytes"

    first = archive.store(payload, provider="magna_xbrl", kind="init", source_reference="a")
    second = archive.store(payload, provider="magna_xbrl", kind="init", source_reference="b")

    assert not first.already_present
    assert second.already_present
    assert first.path == second.path
    assert len(list(first.path.parent.glob("*.json"))) == 2  # payload + metadata


def test_different_payloads_do_not_collide(tmp_path: Path) -> None:
    archive = RawArchive(tmp_path)

    first = archive.store(b"one", provider="magna_xbrl", kind="search", source_reference="a")
    second = archive.store(b"two", provider="magna_xbrl", kind="search", source_reference="b")

    assert first.path != second.path
    assert first.content_hash != second.content_hash
