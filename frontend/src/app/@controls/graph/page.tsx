import type { DropdownOption } from "../../_components/IO";
import type { QueueFilter } from "@/app/_lib/queue";
import GraphControlsClient from "./GraphControlsClient";

export const filterOptions: DropdownOption[] = [
  { value: "queued", label: "Queued" },
  { value: "all", label: "All" },
];

export const visualisationOptions: DropdownOption[] = [
  { value: "umap", label: "UMAP" },
  { value: "tsne", label: "t-SNE" },
  { value: "pca", label: "PCA" },
];

export const clusteringOptions: DropdownOption[] = [
  { value: "kmeans", label: "k-means" },
  { value: "hca", label: "HCA" },
  { value: "dbscan", label: "DBSCAN" },
];

export const DEFAULT_FILTER: QueueFilter = "queued";
export const DEFAULT_VISUALISATION: "pca" | "tsne" | "umap" = "umap";
export const DEFAULT_CLUSTERING: "kmeans" | "hca" | "dbscan" = "kmeans";
export const DEFAULT_CLUSTER_COUNT = 5;
export const DEFAULT_DBSCAN_EPS = 0.3;

export default function GraphControls() {
  const defaults = {
    filter: DEFAULT_FILTER,
    visualisation: DEFAULT_VISUALISATION,
    clustering: DEFAULT_CLUSTERING,
    clusters: DEFAULT_CLUSTER_COUNT,
    eps: DEFAULT_DBSCAN_EPS,
  };

  return (
    <GraphControlsClient
      filterOptions={filterOptions}
      visualisationOptions={visualisationOptions}
      clusteringOptions={clusteringOptions}
      defaults={defaults}
    />
  );
}
