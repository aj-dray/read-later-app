"use client";

import { useCallback } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { ControlStrip } from "../default";
import { DropdownComponent, type DropdownOption } from "../../_components/IO";
import type { QueueFilter, QueueOrder } from "@/app/_lib/queue";
import { useSettings, useSetting } from "@/app/_contexts/SettingsContext";

interface QueueControlsClientProps {
  orderOptions: DropdownOption[];
  filterOptions: DropdownOption[];
  defaults: {
    order: QueueOrder;
    filter: QueueFilter;
  };
}

export default function QueueControlsClient({
  orderOptions,
  filterOptions,
  defaults,
}: QueueControlsClientProps) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { loading } = useSettings();

  // Use global settings with URL sync
  const [order, setOrder] = useSetting("order");
  const [filter, setFilter] = useSetting("filter");

  const updateParam = useCallback(
    (key: "order" | "filter", value: string, defaultValue: string) => {
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

  const handleOrderSelect = useCallback(
    (option: DropdownOption) => {
      const newOrder = option.value as QueueOrder;
      if (newOrder === order) {
        return;
      }

      // Update global settings and URL
      setOrder(newOrder);
      updateParam("order", newOrder, defaults.order);
    },
    [order, updateParam, setOrder, defaults.order],
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

  return (
    <>
      <ControlStrip
        label="Order"
        io={DropdownComponent}
        ioProps={{
          options: orderOptions,
          selectedValue: order,
          onSelect: handleOrderSelect,
          placeholder: "Select order",
        }}
      />
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
    </>
  );
}
