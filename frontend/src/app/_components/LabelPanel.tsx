"use client";

import { motion, AnimatePresence } from "framer-motion";
import { useClusterContext } from "@/app/_contexts/ClusterContext";
import { useRef, useEffect } from "react";

// Generate random widths for placeholder pills (simulating 1-3 word lengths)
const generatePlaceholderWidth = () => {
  const minWidth = 40; // ~1 word
  const maxWidth = 90; // ~2-3 words
  return Math.floor(Math.random() * (maxWidth - minWidth + 1)) + minWidth;
};

// Blend a color toward white to create a pastel shade
function pastelizeColor(input: string, blend: number = 0.75): string {
  // Clamp blend between 0 and 1
  const t = Math.max(0, Math.min(1, blend));

  const toRgb = (color: string): [number, number, number] | null => {
    const hex = color.trim();
    // #RGB or #RRGGBB
    if (/^#([0-9a-fA-F]{3})$/.test(hex)) {
      const m = hex.slice(1);
      const r = parseInt(m[0] + m[0], 16);
      const g = parseInt(m[1] + m[1], 16);
      const b = parseInt(m[2] + m[2], 16);
      return [r, g, b];
    }
    if (/^#([0-9a-fA-F]{6})$/.test(hex)) {
      const r = parseInt(hex.slice(1, 3), 16);
      const g = parseInt(hex.slice(3, 5), 16);
      const b = parseInt(hex.slice(5, 7), 16);
      return [r, g, b];
    }
    // rgb/rgba
    const rgbMatch = hex.match(
      /^rgba?\((\s*\d+\s*),(\s*\d+\s*),(\s*\d+\s*)(?:,\s*([0-9]*\.?[0-9]+)\s*)?\)$/i,
    );
    if (rgbMatch) {
      const r = parseInt(rgbMatch[1], 10);
      const g = parseInt(rgbMatch[2], 10);
      const b = parseInt(rgbMatch[3], 10);
      return [r, g, b];
    }
    return null;
  };

  const rgb = toRgb(input);
  if (!rgb) {
    // Fallback: return input as-is
    return input;
  }

  const [r, g, b] = rgb;
  const pr = Math.round(255 - (255 - r) * (1 - t));
  const pg = Math.round(255 - (255 - g) * (1 - t));
  const pb = Math.round(255 - (255 - b) * (1 - t));
  return `rgb(${pr}, ${pg}, ${pb})`;
}

export default function LabelPanel() {
  const { clusters, clusteringState } = useClusterContext();
  const placeholderWidthsRef = useRef<Map<number | null, number>>(new Map());

  console.log("[LabelPanel] Render:", {
    clusteringState,
    clustersCount: clusters.length,
    clusters,
  });

  // Generate stable placeholder widths for each cluster
  useEffect(() => {
    clusters.forEach((cluster) => {
      if (!placeholderWidthsRef.current.has(cluster.clusterId)) {
        placeholderWidthsRef.current.set(
          cluster.clusterId,
          generatePlaceholderWidth(),
        );
      }
    });
  }, [clusters]);

  // Show clustering state
  if (clusteringState === "clustering") {
    return (
      <motion.div
        className="panel-light label-panel flex items-center justify-center"
        animate={{
          backgroundColor: ["#E7E7E7BB", "#D0D0D0BB", "#E7E7E7BB"],
        }}
        transition={{
          backgroundColor: { duration: 2, repeat: Infinity },
        }}
      >
        <div className="text-xs text-gray-600 font-medium">Clustering...</div>
      </motion.div>
    );
  }

  // Show nothing when idle (only truly idle, not when labeling/complete)
  if (clusteringState === "idle") {
    return null;
  }

  // If we're in labeling/complete state but have no clusters, don't show anything
  // (This shouldn't normally happen but handles edge cases)
  if (clusters.length === 0) {
    return null;
  }

  // Show labels (either loading or complete)
  return (
    <div className="panel-light label-panel flex flex-wrap gap-[10px] items-center justify-center">
      {clusters.map((cluster, index) => {
        const isLoading = cluster.isLoading;
        const placeholderWidth =
          placeholderWidthsRef.current.get(cluster.clusterId) ??
          generatePlaceholderWidth();

        return (
          <motion.div
            key={`cluster-${cluster.clusterId}`}
            className="pill-pastel flex items-center justify-center h-[20px] px-[10px] rounded-[10px] text-xs font-medium leading-none overflow-hidden"
            style={{
              backgroundColor: pastelizeColor(cluster.color, 0.5),
            }}
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{
              opacity: isLoading ? [0.5, 1, 0.5] : 1,
              scale: 1,
            }}
            transition={{
              duration: 0.2,
              delay: 0.05 * index,
              opacity: isLoading
                ? { duration: 1.5, repeat: Infinity }
                : { duration: 0.3, ease: [0.4, 0, 0.2, 1] },
            }}
            layout
          >
            <AnimatePresence mode="wait">
              {isLoading ? (
                <motion.div
                  key="placeholder"
                  className="h-2 bg-black/20 rounded"
                  style={{ width: `${placeholderWidth - 20}px` }}
                  initial={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.2 }}
                />
              ) : (
                <motion.span
                  key="label"
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ duration: 0.3, ease: [0.4, 0, 0.2, 1] }}
                >
                  {cluster.label}
                </motion.span>
              )}
            </AnimatePresence>
          </motion.div>
        );
      })}
    </div>
  );
}
