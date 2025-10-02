import sklearn
import numpy as np
from pydantic import BaseModel
from aglib import Context, Agent
from collections import defaultdict
import json
import umap as umap_lib


from . import utils


# === UTILITIES ===


def _extract_embeddings(rows):
    embeddings = []
    for row in rows:
        embedding = row["mistral_embedding"]
        if isinstance(embedding, str):
            # Parse PostgreSQL vector string format: "[1.0,2.0,3.0]"
            try:
                import json
                embedding = json.loads(embedding)
            except json.JSONDecodeError:
                # Fallback: manual parsing
                embedding = embedding.strip('[]')
                embedding = [float(x.strip()) for x in embedding.split(',')]
        embeddings.append(embedding)

    EV = np.array(embeddings)
    EV = utils.l2_normalize(EV)
    return EV


# def _handle_singletons(labels):
#     """Set clusters with only one item as outliers (label -1) and renumber remaining clusters."""
#     labels = np.asarray(labels).copy()
#     unique, counts = np.unique(labels, return_counts=True)
#     singleton_clusters = set(unique[counts == 1])

#     # First pass: convert singletons to outliers
#     for idx, label in enumerate(labels):
#         if label in singleton_clusters:
#             labels[idx] = -1

#     # Second pass: renumber remaining clusters to maintain continuous sequence
#     remaining_clusters = sorted([label for label in unique if label not in singleton_clusters])
#     cluster_mapping = {old_label: new_label for new_label, old_label in enumerate(remaining_clusters)}

#     for idx, label in enumerate(labels):
#         if label != -1:  # Don't renumber outliers
#             labels[idx] = cluster_mapping[label]

#     return labels


# === DIMENSIONAL REDUCTION ===


def pca(rows: list[dict], d: int = 2, **kwargs):
    """Return shape (n, d)"""
    EV = _extract_embeddings(rows)
    pca = sklearn.decomposition.PCA(n_components=d)
    EV_red = pca.fit_transform(EV)
    return EV_red


def tsne(rows: list[dict], d: int = 2, **kwargs):
    perplexity = kwargs.get("perplexity", min(30, max(1, len(rows) // 4)))
    # Ensure perplexity is valid (must be less than n_samples and > 0)
    perplexity = max(1, min(perplexity, len(rows) - 1))
    EV = _extract_embeddings(rows)
    tsne = sklearn.manifold.TSNE(n_components=d, perplexity=perplexity, metric="cosine", random_state=42)
    embeddings_2d_tsne = tsne.fit_transform(EV)
    return embeddings_2d_tsne


def umap(rows: list[dict], d: int = 2, **kwargs):
    # UMAP requires at least n_neighbors + 1 samples
    if len(rows) < 3:
        # Fallback to t-SNE for very small datasets
        return tsne(rows, d=d, **kwargs)

    n_neighbors = kwargs.get("n_neighbors", min(15, len(rows) - 1))
    min_dist = kwargs.get("min_dist", 0.1)
    random_state = kwargs.get("random_state")
    EV = _extract_embeddings(rows)

    # Ensure n_neighbors doesn't exceed available samples and is at least 2
    n_neighbors = max(2, min(n_neighbors, len(rows) - 1))

    reducer = umap_lib.UMAP(
        n_components=d,
        n_neighbors=n_neighbors,
        min_dist=min_dist,
        metric="cosine",
        random_state=random_state,
    )
    embeddings_2d_umap = reducer.fit_transform(EV)
    return embeddings_2d_umap


# === CLUSTERING ===


def kmeans(rows, **kwargs):
    EV = _extract_embeddings(rows)
    k = kwargs.get("k", min(5, len(rows)))
    # Ensure k doesn't exceed number of samples
    k = min(k, len(rows))
    kmeans = sklearn.cluster.KMeans(n_clusters=k, random_state=42, n_init=10)
    clusters = kmeans.fit_predict(EV)
    return clusters


def hca(rows, **kwargs):
    EV = _extract_embeddings(rows)
    # Switch to explicit number of clusters (k) rather than distance threshold
    k = kwargs.get("k")
    if k is None:
        # Fallback heuristic similar to kmeans default
        k = min(5, len(rows))
    # Ensure k is valid relative to sample size
    k = max(1, min(int(k), len(rows)))
    hca = sklearn.cluster.AgglomerativeClustering(
        n_clusters=k,
        metric="cosine",
        linkage="average"
    )
    clusters = hca.fit_predict(EV)
    return clusters


def _pick_eps(EV, min_samples=2):
    nn = sklearn.neighbors.NearestNeighbors(n_neighbors=min_samples, metric="cosine").fit(EV)
    dists, _ = nn.kneighbors(EV)
    kth = np.sort(dists[:, -1])
    return float(np.percentile(kth, 80))


def dbscan(rows, **kwargs):
    dim_red = kwargs.get("dim_red", None)
    if dim_red is not None:
        # Ensure dim_red doesn't exceed available samples for PCA
        dim_red = min(dim_red, len(rows) - 1) if len(rows) > 1 else None
        if dim_red and dim_red > 0:
            EV = pca(rows, d=dim_red)
        else:
            EV = _extract_embeddings(rows)
    else:
        EV = _extract_embeddings(rows)

    eps = kwargs.get("eps", _pick_eps(EV))
    min_samples = kwargs.get("min_samples", min(3, len(rows)))
    dbscan = sklearn.cluster.DBSCAN(eps=eps, min_samples=min_samples, metric="cosine")
    clusters = dbscan.fit_predict(EV)
    return clusters


# === LABELLING ===


class ClusterLabel(BaseModel):
    cluster_idx: int
    label: str


class LabelOutput(BaseModel):
    labels: list[ClusterLabel]


label_agent = Agent(
    name="data_labeller",
    provider="mistral",
    model="mistral-medium-latest",
    tools = [],
    system_prompt="""
        You are a data labeler for clusters of items.
        You will be provided a list of summaries each cluster's contents and must provide a 1-2 word label of this cluster's content.
        Look for broader theme where possible.
        Output in the request schema, which a UNIQUE label for each cluster.
    """
)


def label(clusters, rows):
    """Generate labels for clusters based on item summaries.

    Args:
        clusters: List of cluster indices (one per item)
        rows: List of row dicts with 'id' and 'summary' fields

    Returns:
        Dict mapping cluster_id to label string
    """
    summary_groups = defaultdict(list)
    for cidx, row in zip(clusters, rows):
        if cidx == -1:
            continue  # skip outliers
        summary_text = row.get("summary", "") if isinstance(row, dict) else str(row)
        if summary_text and summary_text.strip():
            summary_groups[int(cidx)].append(summary_text)

    num_clusters = len(summary_groups.keys())

    # If no valid clusters, return empty dict
    if num_clusters == 0:
        return {}

    cluster_data = []
    for cluster_id, summaries_list in summary_groups.items():
        cluster_data.append(f"Cluster {cluster_id}:")
        for i, summary_text in enumerate(summaries_list, 1):
            cluster_data.append(f"  {i}. {summary_text}")
        cluster_data.append("")  # Empty line between clusters

    formatted_input = "\n".join(cluster_data)

    ctx = Context()
    ctx.add_user_query(formatted_input)
    output = label_agent.request(ctx, response_format=LabelOutput)

    parsed_output = LabelOutput.model_validate(json.loads(output.content))
    return {cl.cluster_idx: cl.label for cl in parsed_output.labels}
