"""Phase 2 — Ingestion II: Enrichment (Embed, Classify, Cluster, Keywords).

Everything here is deterministic: embeddings (fastembed/ONNX), sentiment (VADER),
clustering (seeded KMeans + fixed input order), keywords/labels (TF-IDF). Model
versions are stamped so reproducibility is auditable (EC-X-06, EC-X-08).
"""
from __future__ import annotations

import uuid

# Fixed namespace -> deterministic ids (idempotent vector upserts, stable theme ids
# for identical data; EC-X-23, EC-X-07).
_NS = uuid.UUID("6f1c2e00-0000-4000-8000-000000000000")

SENTIMENT_VERSION = "vader-v1"
THEME_VERSION = "kmeans-tfidf-v1"
EMBED_VERSION = "bge-small-en-v1.5"


def review_point_id(app_id: str, platform: str, source_review_id: str) -> str:
    return str(uuid.uuid5(_NS, f"{app_id}|{platform}|{source_review_id}"))


def theme_id(app_id: str, label: str) -> str:
    return str(uuid.uuid5(_NS, f"{app_id}|theme|{label}"))
