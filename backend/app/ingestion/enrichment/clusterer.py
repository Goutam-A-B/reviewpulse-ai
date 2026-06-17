"""Theme Clusterer — seeded KMeans + silhouette model selection (PRD §3).

Deterministic given a fixed input order (the runner sorts by source_review_id):
KMeans uses random_state=42 / n_init=10, silhouette picks k, and cluster labels
come from per-cluster mean TF-IDF (EC-P2-09). Honest states when themes don't
exist (EC-P2-06 too few reviews, EC-P2-07 not separable). Per-review distance to
its centroid is returned for later low-fit exclusion (EC-P2-12).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.ingestion.enrichment.keywords import app_name_tokens

MIN_FOR_CLUSTERING = 12
MAX_K = 10


@dataclass
class Theme:
    index: int  # cluster index, stable within a run
    label: str
    size: int


@dataclass
class ClusterResult:
    labels: list[int]  # per-input cluster index; -1 if unclustered
    distances: list[float]  # per-input distance to assigned centroid (0.0 if unclustered)
    themes: list[Theme] = field(default_factory=list)
    note: str = ""


def cluster(vectors: list[list[float]], texts: list[str], app_name: str | None = None) -> ClusterResult:
    n = len(vectors)
    if n < MIN_FOR_CLUSTERING:
        return ClusterResult(
            [-1] * n, [0.0] * n, note=f"insufficient reviews for themes (need >= {MIN_FOR_CLUSTERING})"
        )

    import numpy as np
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score

    X = np.asarray(vectors, dtype="float32")
    # Never request more clusters than there are distinct points — avoids degenerate
    # empty clusters on low-variety corpora (EC-P2-07).
    n_distinct = len({tuple(row) for row in X.tolist()})
    k_max = min(MAX_K, n_distinct, n - 1)
    best: tuple[float, int, "np.ndarray", "np.ndarray"] | None = None
    for k in range(2, k_max + 1):
        km = KMeans(n_clusters=k, random_state=42, n_init=10).fit(X)
        labels = km.labels_
        if len(set(labels.tolist())) < 2:
            continue
        score = float(silhouette_score(X, labels))
        if best is None or score > best[0]:
            best = (score, k, labels, km.cluster_centers_)

    if best is None:
        return ClusterResult([-1] * n, [0.0] * n, note="themes not separable")

    _, k, labels_arr, centers = best
    labels = [int(x) for x in labels_arr.tolist()]
    distances = [float(np.linalg.norm(X[i] - centers[labels[i]])) for i in range(n)]
    themes = _label_clusters(labels, texts, k, app_name)
    return ClusterResult(labels, distances, themes)


def _label_clusters(labels: list[int], texts: list[str], k: int, app_name: str | None) -> list[Theme]:
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer

    stop = app_name_tokens(app_name)
    try:
        vec = TfidfVectorizer(stop_words="english", token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z]+\b")
        matrix = vec.fit_transform(texts)
        terms = vec.get_feature_names_out()
    except ValueError:
        return [Theme(c, f"Theme {c + 1}", labels.count(c)) for c in range(k) if labels.count(c)]

    themes: list[Theme] = []
    for c in range(k):
        idx = [i for i, lab in enumerate(labels) if lab == c]
        if not idx:
            continue
        mean = np.asarray(matrix[idx].mean(axis=0)).ravel()
        words: list[str] = []
        for j in mean.argsort(kind="stable")[::-1]:
            term = terms[j]
            if mean[j] <= 0.0:
                break
            if term in stop:
                continue
            words.append(term)
            if len(words) >= 3:
                break
        themes.append(Theme(c, ", ".join(words) if words else "Unlabelled", len(idx)))

    themes.sort(key=lambda t: (-t.size, t.index))
    return themes
