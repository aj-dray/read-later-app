"use client";

import { useState, useEffect, useCallback } from "react";
import { usePathname } from "next/navigation";
import {
  getUserControls,
  setUserControls,
  updateUserControl,
  type UserControlStates,
} from "@/app/_lib/user-controls";
import {
  getControlValue,
  normalizePagePath,
} from "@/app/_lib/user-controls-utils";

export interface UseUserControlsReturn {
  controlStates: UserControlStates;
  loading: boolean;
  error: string | null;
  getControl: <T>(key: string, defaultValue: T) => T;
  setControl: (key: string, value: unknown) => Promise<void>;
  setAllControls: (states: UserControlStates) => Promise<void>;
  refreshControls: () => Promise<void>;
}

export function useUserControls(): UseUserControlsReturn {
  const pathname = usePathname();
  const [controlStates, setControlStates] = useState<UserControlStates>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const pagePath = normalizePagePath(pathname);

  // Load controls when component mounts or page changes
  const loadControls = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const states = await getUserControls(pagePath);
      setControlStates(states);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load controls");
      console.error("Error loading user controls:", err);
    } finally {
      setLoading(false);
    }
  }, [pagePath]);

  useEffect(() => {
    loadControls();
  }, [loadControls]);

  // Get a control value with fallback
  const getControl = useCallback(
    <T>(key: string, defaultValue: T): T => {
      return getControlValue(controlStates, key, defaultValue);
    },
    [controlStates],
  );

  // Set a single control value
  const setControl = useCallback(
    async (key: string, value: unknown) => {
      try {
        // Optimistically update local state
        setControlStates((prev) => ({ ...prev, [key]: value }));

        // Save to backend
        const success = await updateUserControl(pagePath, key, value);
        if (!success) {
          // Revert on failure
          setControlStates((prev) => {
            const updated = { ...prev };
            if (controlStates[key] !== undefined) {
              updated[key] = controlStates[key];
            } else {
              delete updated[key];
            }
            return updated;
          });
          setError("Failed to save control state");
        }
      } catch (err) {
        // Revert on error
        setControlStates((prev) => {
          const updated = { ...prev };
          if (controlStates[key] !== undefined) {
            updated[key] = controlStates[key];
          } else {
            delete updated[key];
          }
          return updated;
        });
        setError(err instanceof Error ? err.message : "Failed to save control");
        console.error("Error setting user control:", err);
      }
    },
    [pagePath, controlStates],
  );

  // Set all control values
  const setAllControls = useCallback(
    async (states: UserControlStates) => {
      const previousStates = controlStates;
      try {
        // Optimistically update local state
        setControlStates(states);

        // Save to backend
        const success = await setUserControls(pagePath, states);
        if (!success) {
          // Revert on failure
          setControlStates(previousStates);
          setError("Failed to save control states");
        }
      } catch (err) {
        // Revert on error
        setControlStates(previousStates);
        setError(
          err instanceof Error ? err.message : "Failed to save controls",
        );
        console.error("Error setting user controls:", err);
      }
    },
    [pagePath, controlStates],
  );

  return {
    controlStates,
    loading,
    error,
    getControl,
    setControl,
    setAllControls,
    refreshControls: loadControls,
  };
}
