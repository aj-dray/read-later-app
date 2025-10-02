"use server";

import { revalidatePath } from "next/cache";
import { CLIENT_UPDATABLE_STATUSES, updateItem } from "@/app/_lib/items";
import { getSession } from "@/app/_lib/auth";
import type { ClientStatus } from "@/app/_lib/items";

type ClientUpdatableStatus = (typeof CLIENT_UPDATABLE_STATUSES)[number];

export async function updateItemStatusInQueue(
  itemId: string,
  status: ClientUpdatableStatus,
): Promise<{
  success: boolean;
  newStatus?: ClientUpdatableStatus;
  error?: string;
}> {
  if (!CLIENT_UPDATABLE_STATUSES.includes(status)) {
    return {
      success: false,
      error: `Status "${status}" cannot be set manually`,
    };
  }

  try {
    const session = await getSession();
    if (!session) {
      return { success: false, error: "Authentication required" };
    }

    const now = new Date().toISOString();
    const payload = { client_status: status, client_status_at: now };
    await updateItem(itemId, payload);

    // Revalidate the queue page to update the UI
    revalidatePath("/queue");

    return { success: true, newStatus: status };
  } catch (error) {
    console.error("Failed to update item status in queue", {
      itemId,
      status,
      error,
    });

    return {
      success: false,
      error: error instanceof Error ? error.message : "Unknown error",
    };
  }
}
