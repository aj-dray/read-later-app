"use client";

import { useCallback } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { ControlStrip } from "../default";
import { DropdownComponent, type DropdownOption } from "../../_components/IO";
import type { SearchMode, SearchScope } from "@/app/_lib/search";
import { useSettings, useSetting } from "@/app/_contexts/SettingsContext";

interface SearchControlsClientProps {
  modeOptions: DropdownOption[];
  scopeOptions: DropdownOption[];
  defaults: {
    mode: SearchMode;
    scope: SearchScope;
  };
}

export default function SearchControlsClient({
  modeOptions,
  scopeOptions,
  defaults,
}: SearchControlsClientProps) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { loading } = useSettings();

  // Use global settings with URL sync
  const [mode, setMode] = useSetting("mode");
  const [scope, setScope] = useSetting("scope");

  const updateParam = useCallback(
    (key: "mode" | "scope", value: string, defaultValue: string) => {
      const currentQuery = searchParams.toString();
      const next = new URLSearchParams(currentQuery);
      if (value === defaultValue) {
        next.delete(key);
      } else {
        next.set(key, value);
      }

      const nextQuery = next.toString();
      const target = nextQuery ? `${pathname}?${nextQuery}` : pathname;
      const current = currentQuery ? `${pathname}?${currentQuery}` : pathname;

      if (target === current) {
        return;
      }

      router.replace(target);
    },
    [pathname, router, searchParams],
  );

  const handleModeSelect = useCallback(
    (option: DropdownOption) => {
      const newMode = option.value as SearchMode;
      if (newMode === mode) {
        return;
      }

      // Update global settings and URL
      setMode(newMode);
      updateParam("mode", newMode, defaults.mode);
    },
    [mode, updateParam, setMode, defaults.mode],
  );

  const handleScopeSelect = useCallback(
    (option: DropdownOption) => {
      const newScope = option.value as SearchScope;
      if (newScope === scope) {
        return;
      }

      // Update global settings and URL
      setScope(newScope);
      updateParam("scope", newScope, defaults.scope);
    },
    [scope, updateParam, setScope, defaults.scope],
  );

  return (
    <>
      <ControlStrip
        label="Type"
        io={DropdownComponent}
        ioProps={{
          options: modeOptions,
          selectedValue: mode,
          onSelect: handleModeSelect,
          placeholder: "Select type",
        }}
      />
      <ControlStrip
        label="Scope"
        io={DropdownComponent}
        ioProps={{
          options: scopeOptions,
          selectedValue: scope,
          onSelect: handleScopeSelect,
          placeholder: "Select scope",
        }}
      />
    </>
  );
}
