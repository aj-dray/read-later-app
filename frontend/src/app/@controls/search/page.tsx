import { ControlStrip } from "../default";
import { DropdownComponent, type DropdownOption } from "../../_components/IO";
import type { SearchMode, SearchScope } from "@/app/_lib/search";

import SearchControlsClient from "./SearchControlsClient";

export const modeOptions: DropdownOption[] = [
  { value: "lexical", label: "Lexical" },
  { value: "semantic", label: "Semantic" },
];

export const scopeOptions: DropdownOption[] = [
  { value: "items", label: "Full text" },
  { value: "chunks", label: "Chunks" },
];

export const DEFAULT_MODE: SearchMode = "lexical";
export const DEFAULT_SCOPE: SearchScope = "items";

export default function SearchControls() {
  const defaults = {
    mode: DEFAULT_MODE,
    scope: DEFAULT_SCOPE,
  };

  return (
    <SearchControlsClient
      modeOptions={modeOptions}
      scopeOptions={scopeOptions}
      defaults={defaults}
    />
  );
}
