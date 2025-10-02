export const CLUSTER_EVENT_NAME = "later:graph-clusters" as const;
export const CLUSTER_STATE_EVENT_NAME = "later:graph-cluster-state" as const;

export type ClusteringState = "idle" | "clustering" | "labeling" | "complete";

export type ClusterLegendItem = {
  clusterId: number | null;
  label: string;
  color: string;
  count: number;
  isLoading?: boolean;
};

export type ClusterLegendEventDetail = {
  filter: string;
  clustering: string;
  clusterKwarg: number | null;
  items: ClusterLegendItem[];
};

export type ClusterStateEventDetail = {
  state: ClusteringState;
};
