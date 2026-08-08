"""Data acquisition layer.

Everything provider-specific lives here and nowhere else. The financial core must
never learn a MAGNA or SEC URL (spec section 40).

Sub-packages are added in phase 1:
  providers/   FinancialDataProvider implementations (magna_xbrl first)
  parsers/     raw payload to structured records
  pipelines/   discover, fetch, archive, normalize
"""

__version__ = "0.1.0"
