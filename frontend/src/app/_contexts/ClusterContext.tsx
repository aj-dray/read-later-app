"use client";

import React, {
  createContext,
  useContext,
  useState,
  useCallback,
  ReactNode,
} from "react";
import type {
  ClusterLegendItem,
  ClusteringState,
} from "@/app/graph/clusterEvents";

export type ClusterContextType = {
  clusters: ClusterLegendItem[];
  clusteringState: ClusteringState;
  updateClusters: (clusters: ClusterLegendItem[]) => void;
  clearClusters: () => void;
  setClusteringState: (state: ClusteringState) => void;
};

const ClusterContext = createContext<ClusterContextType | null>(null);

export function useClusterContext(): ClusterContextType {
  const context = useContext(ClusterContext);
  if (!context) {
    throw new Error("useClusterContext must be used within a ClusterProvider");
  }
  return context;
}

type ClusterProviderProps = {
  children: ReactNode;
};

export function ClusterProvider({ children }: ClusterProviderProps) {
  const [clusters, setClusters] = useState<ClusterLegendItem[]>([]);
  const [clusteringState, setClusteringState] =
    useState<ClusteringState>("idle");

  const updateClusters = useCallback((newClusters: ClusterLegendItem[]) => {
    setClusters(newClusters);

    // Automatically update state based on cluster content
    if (newClusters.length === 0) {
      setClusteringState("idle");
    } else if (newClusters.some((cluster) => cluster.isLoading)) {
      setClusteringState("labeling");
    } else {
      setClusteringState("complete");
    }
  }, []);

  const clearClusters = useCallback(() => {
    setClusters([]);
    setClusteringState("idle");
  }, []);

  const value: ClusterContextType = {
    clusters,
    clusteringState,
    updateClusters,
    clearClusters,
    setClusteringState,
  };

  return (
    <ClusterContext.Provider value={value}>{children}</ClusterContext.Provider>
  );
}
