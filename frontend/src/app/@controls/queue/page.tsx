import { ControlStrip } from "../default";
import { DropdownComponent, type DropdownOption } from "../../_components/IO";
import type { QueueFilter, QueueOrder } from "@/app/_lib/queue";
import QueueControlsClient from "./QueueControlsClient";

export const orderOptions: DropdownOption[] = [
  { value: "date", label: "Date Added" },
  { value: "random", label: "Random" },
  { value: "priority", label: "Priority" },
];

export const filterOptions: DropdownOption[] = [
  { value: "queued", label: "Queued" },
  { value: "all", label: "All" },
];

export const DEFAULT_ORDER: QueueOrder = "date";
export const DEFAULT_FILTER: QueueFilter = "queued";

export default function QueueControls() {
  const defaults = {
    order: DEFAULT_ORDER,
    filter: DEFAULT_FILTER,
  };

  return (
    <QueueControlsClient
      orderOptions={orderOptions}
      filterOptions={filterOptions}
      defaults={defaults}
    />
  );
}
