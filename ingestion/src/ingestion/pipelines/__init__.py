"""Pipelines that move provider data into the canonical store."""

from ingestion.pipelines.magna import IngestionReport, ingest_batch
from ingestion.pipelines.recency import recency_key

__all__ = ["IngestionReport", "ingest_batch", "recency_key"]
