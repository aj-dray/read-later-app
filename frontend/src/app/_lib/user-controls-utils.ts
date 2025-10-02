"use client";

import type { UserControlStates } from "./user-controls";
import { normalizePagePath } from "./path-utils";

// Re-export for backward compatibility
export { normalizePagePath } from "./path-utils";

/**
 * Helper to get control value with fallback
 */
export function getControlValue<T>(
  controlStates: UserControlStates,
  key: string,
  defaultValue: T,
): T {
  return controlStates[key] !== undefined
    ? (controlStates[key] as T)
    : defaultValue;
}

/**
 * Helper to merge control states with defaults
 */
export function mergeControlStates<T extends Record<string, unknown>>(
  controlStates: UserControlStates,
  defaults: T,
): T {
  const merged = { ...defaults };

  for (const [key, value] of Object.entries(controlStates)) {
    if (key in defaults) {
      merged[key as keyof T] = value as T[keyof T];
    }
  }

  return merged;
}

/**
 * Helper to validate control values against allowed options
 */
export function validateControlValue<T>(
  value: unknown,
  allowedValues: readonly T[],
  defaultValue: T,
): T {
  return allowedValues.includes(value as T) ? (value as T) : defaultValue;
}
