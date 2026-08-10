"""Ordering filings without a publication date.

MAGNA supplies none. Decision 0009 permits inferring order from the reference
number, which looks like `2024-01-616266`, on condition that the inference is
labelled as one.

The sequence part is not fixed width -- `2024-01-023212` and `2024-01-616266`
happen to be, but `2023-01-74131` style values appear too -- so the parts are
zero padded before being joined. Comparing the raw strings would put
`2024-01-9` after `2024-01-10`.
"""

import re
from typing import Final

_REFERENCE = re.compile(r"^(\d{4})-(\d+)-(\d+)$")

SEQUENCE_WIDTH: Final[int] = 12


def recency_key(provider_filing_id: str) -> str:
    """A lexicographically sortable key for a filing reference.

    An unrecognised reference is returned padded but otherwise untouched, so it
    still sorts deterministically instead of raising during ingestion. It will
    sort apart from the well-formed ones, which is the honest outcome: we do not
    know where it belongs.
    """
    match = _REFERENCE.match(provider_filing_id.strip())
    if not match:
        return provider_filing_id.strip().rjust(SEQUENCE_WIDTH, "0")

    year, middle, sequence = match.groups()
    return f"{year}-{middle.zfill(4)}-{sequence.zfill(SEQUENCE_WIDTH)}"


def is_recognised(provider_filing_id: str) -> bool:
    """Whether the reference has the shape the ordering assumes."""
    return _REFERENCE.match(provider_filing_id.strip()) is not None
