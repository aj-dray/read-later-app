"use client";

import { useCallback, useMemo } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { ControlStrip } from "../default";
import {
  DropdownComponent,
  NumberInputControl,
  type DropdownOption,
} from "../../_components/IO";
import type { QueueFilter } from "@/app/_lib/queue";
import { useSettings, useSetting } from "@/app/_contexts/SettingsContext";

interface GraphControlsClientProps {
  filterOptions: DropdownOption[];
  visualisationOptions: DropdownOption[];
  clusteringOptions: DropdownOption[];
  defaults: {
    filter: QueueFilter;
    visualisation: "pca" | "tsne" | "umap";
    clustering: "kmeans" | "hca" | "dbscan";
    clusters: number;
    eps: number;
  };
}

export default function GraphControlsClient({
  filterOptions,
  visualisationOptions,
  clusteringOptions,
  defaults,
}: GraphControlsClientProps) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { loading } = useSettings();

  // Use global settings with URL sync
  const [filter, setFilter] = useSetting("filter");
  const [visualisation, setVisualisation] = useSetting("visualisation");
  const [clustering, setClustering] = useSetting("clustering");
  const [clusters, setClusters] = useSetting("clusters");
  const [eps, setEps] = useSetting("eps");

  const updateParam = useCallback(
    (
      key: "filter" | "visualisation" | "clustering" | "clusters" | "eps",
      value: string,
      defaultValue: string | number,
    ) => {
      const currentQuery = searchParams.toString();
      const next = new URLSearchParams(currentQuery);
      if (value === String(defaultValue)) {
        next.delete(key);
      } else {
        next.set(key, value);
      }

      const nextQuery = next.toString();
      const target = nextQuery ? `${pathname}?${nextQuery}` : pathname;
      const current = currentQuery ? `${pathname}?${currentQuery}` : pathname;

      if (target !== current) {
        router.replace(target);
      } else {
        // Force refresh even if URL didn't change (e.g., reverting to default)
        router.refresh();
      }
    },
    [pathname, router, searchParams],
  );

  const handleFilterSelect = useCallback(
    (option: DropdownOption) => {
      const newFilter = option.value as QueueFilter;
      if (newFilter === filter) {
        return;
      }

      // Update global settings and URL
      setFilter(newFilter);
      updateParam("filter", newFilter, defaults.filter);
    },
    [filter, updateParam, setFilter, defaults.filter],
  );

  const handleVisualisationSelect = useCallback(
    (option: DropdownOption) => {
      const newVis = option.value as "pca" | "tsne" | "umap";
      if (newVis === visualisation) {
        return;
      }

      // Update global settings and URL
      setVisualisation(newVis);
      updateParam("visualisation", newVis, defaults.visualisation);
    },
    [visualisation, updateParam, setVisualisation, defaults.visualisation],
  );

  const handleClusteringSelect = useCallback(
    (option: DropdownOption) => {
      const newClustering = option.value as "kmeans" | "hca" | "dbscan";
      if (newClustering === clustering) {
        return;
      }

      const currentQuery = searchParams.toString();
      const next = new URLSearchParams(currentQuery);

      if (newClustering === defaults.clustering) {
        next.delete("clustering");
      } else {
        next.set("clustering", newClustering);
      }

      // Handle DBSCAN-specific params
      if (newClustering === "dbscan") {
        next.delete("clusters");
        // Ensure eps has a sensible default in URL for DBSCAN
        if (!next.get("eps")) {
          next.set("eps", `${defaults.eps}`);
          setEps(defaults.eps);
        }
      }

      const nextQuery = next.toString();
      const target = nextQuery ? `${pathname}?${nextQuery}` : pathname;
      const current = currentQuery ? `${pathname}?${currentQuery}` : pathname;

      // Update global settings
      setClustering(newClustering);

      if (target !== current) {
        router.replace(target);
      } else {
        // Force refresh even if URL didn't change (e.g., switching to default)
        router.refresh();
      }
    },
    [
      clustering,
      searchParams,
      pathname,
      router,
      setClustering,
      setEps,
      defaults.clustering,
      defaults.eps,
    ],
  );

  const handleClusterCountChange = useCallback(
    (value: number) => {
      setClusters(value);
      updateParam("clusters", `${value}`, defaults.clusters);
    },
    [updateParam, setClusters, defaults.clusters],
  );

  const handleDbscanEpsChange = useCallback(
    (value: number) => {
      // Clamp for safety
      const clamped = Math.max(0.01, Math.min(value, 1.0));
      setEps(clamped);
      updateParam("eps", `${clamped}`, defaults.eps);
    },
    [updateParam, setEps, defaults.eps],
  );

  const showClusterInput = clustering !== "dbscan";
  const showDbscanInput = clustering === "dbscan";

  const clusterLabel = useMemo(() => {
    if (!showClusterInput) {
      return null;
    }
    return "No. Clusters";
  }, [showClusterInput]);

  return (
    <>
      <ControlStrip
        label="Filter"
        io={DropdownComponent}
        ioProps={{
          options: filterOptions,
          selectedValue: filter,
          onSelect: handleFilterSelect,
          placeholder: "Select filter",
        }}
      />
      <ControlStrip
        label="Visualisation"
        io={DropdownComponent}
        ioProps={{
          options: visualisationOptions,
          selectedValue: visualisation,
          onSelect: handleVisualisationSelect,
          placeholder: "Select mode",
        }}
      />
      <ControlStrip
        label="Clustering"
        io={DropdownComponent}
        ioProps={{
          options: clusteringOptions,
          selectedValue: clustering,
          onSelect: handleClusteringSelect,
          placeholder: "Select clustering",
        }}
      />
      {showClusterInput && clusterLabel && (
        <ControlStrip
          label={clusterLabel}
          io={NumberInputControl}
          ioProps={{
            value: clusters ?? defaults.clusters,
            min: 2,
            max: 24,
            onChange: handleClusterCountChange,
          }}
        />
      )}
      {showDbscanInput && (
        <ControlStrip
          label="DBSCAN eps"
          io={NumberInputControl}
          ioProps={{
            value: eps ?? defaults.eps,
            min: 0.01,
            max: 1.0,
            step: 0.01,
            onChange: handleDbscanEpsChange,
          }}
        />
      )}
    </>
  );
}
