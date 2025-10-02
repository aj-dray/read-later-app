export const dynamic = "force-dynamic";

import { redirect } from "next/navigation";

import { getSession } from "@/app/_lib/auth";
import { fetchItems, type ItemSummary } from "@/app/_lib/items";
import type { QueueFilter } from "@/app/_lib/queue";
import { getUserControlsServer } from "@/app/_lib/user-controls-server";

import GraphClient from "./GraphClient";
import {
  DEFAULT_FILTER,
  DEFAULT_VISUALISATION,
  DEFAULT_CLUSTERING,
  DEFAULT_CLUSTER_COUNT,
  DEFAULT_DBSCAN_EPS,
} from "../@controls/graph/page";

const VISUALISATION_OPTIONS = new Set<"pca" | "tsne" | "umap">([
  "pca",
  "tsne",
  "umap",
]);

const CLUSTERING_OPTIONS = new Set<"kmeans" | "hca" | "dbscan">([
  "kmeans",
  "hca",
  "dbscan",
]);

type GraphPageProps = {
  searchParams: Promise<{
    filter?: string;
    visualisation?: string;
    clustering?: string;
    clusters?: string;
    eps?: string;
  }>;
};

function parseClusterCount(value: string | undefined): number {
  if (!value) {
    return DEFAULT_CLUSTER_COUNT;
  }
  const numeric = Number.parseInt(value, 10);
  if (!Number.isFinite(numeric)) {
    return DEFAULT_CLUSTER_COUNT;
  }
  return Math.min(Math.max(numeric, 2), 24);
}

export default async function Page({ searchParams }: GraphPageProps) {
  const session = await getSession();
  if (!session) {
    redirect("/login");
  }

  // Load user's saved settings from database
  const userSettings = await getUserControlsServer("/graph");

  const resolvedParams = await searchParams;

  // URL params take precedence, then DB settings, then defaults
  const filterParam = resolvedParams?.filter;
  const filter: QueueFilter =
    filterParam === "all" || filterParam === "queued"
      ? (filterParam as QueueFilter)
      : (userSettings.filter as QueueFilter) || DEFAULT_FILTER;

  const visualisationParam = resolvedParams?.visualisation?.toLowerCase();
  const visualisation = VISUALISATION_OPTIONS.has(visualisationParam as never)
    ? (visualisationParam as "pca" | "tsne" | "umap")
    : VISUALISATION_OPTIONS.has(userSettings.visualisation as never)
      ? (userSettings.visualisation as "pca" | "tsne" | "umap")
      : DEFAULT_VISUALISATION;

  const clusteringParam = resolvedParams?.clustering?.toLowerCase();
  const clustering = CLUSTERING_OPTIONS.has(clusteringParam as never)
    ? (clusteringParam as "kmeans" | "hca" | "dbscan")
    : CLUSTERING_OPTIONS.has(userSettings.clustering as never)
      ? (userSettings.clustering as "kmeans" | "hca" | "dbscan")
      : DEFAULT_CLUSTERING;

  let clusterKwarg: number | null = null;
  if (clustering === "dbscan") {
    const epsRaw = resolvedParams?.eps;
    const epsFromDb = typeof userSettings.eps === "number" ? userSettings.eps : null;
    const eps =
      epsRaw != null
        ? Number.parseFloat(epsRaw)
        : epsFromDb ?? DEFAULT_DBSCAN_EPS;
    clusterKwarg = Number.isFinite(eps) ? eps : DEFAULT_DBSCAN_EPS;
  } else {
    const clustersFromDb = typeof userSettings.clusters === "number" ? userSettings.clusters : null;
    clusterKwarg = resolvedParams?.clusters
      ? parseClusterCount(resolvedParams.clusters)
      : clustersFromDb ?? DEFAULT_CLUSTER_COUNT;
  }

  let items: ItemSummary[] = [];
  try {
    items = await fetchItems({
      limit: 200,
      orderBy: "created_at",
      order: "desc",
    });
  } catch (error) {
    if (error instanceof Error && error.message.includes("401")) {
      redirect("/login");
    }
    throw error;
  }

  return (
    <div className="flex h-full w-full flex-col overflow-hidden bg-[#F0F0F0]">
      <GraphClient
        items={items}
        filter={filter}
        visualisation={visualisation}
        clustering={clustering}
        clusterKwarg={clusterKwarg}
      />
    </div>
  );
}
