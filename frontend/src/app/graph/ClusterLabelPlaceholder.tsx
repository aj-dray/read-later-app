"use client";

/**
 * ClusterLabelPlaceholder component for displaying cluster labels with loading state
 *
 * This component provides a pulsing animation while cluster labels are being generated.
 *
 * @example
 * ```tsx
 * <ClusterLabelPlaceholder label="Loading..." isLoading={true} />
 * <ClusterLabelPlaceholder label="Technology" isLoading={false} />
 * ```
 */

type ClusterLabelPlaceholderProps = {
  label: string;
  isLoading?: boolean;
  className?: string;
};

export function ClusterLabelPlaceholder({
  label,
  isLoading = false,
  className = "",
}: ClusterLabelPlaceholderProps) {
  return (
    <span className={`inline-block ${isLoading ? "animate-pulse-soft" : ""} ${className}`}>
      {label}
    </span>
  );
}