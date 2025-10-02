"use server";

import { revalidatePath } from "next/cache";

import { redirect } from "next/navigation";

import { getSession } from "@/app/_lib/auth";
import { CLIENT_UPDATABLE_STATUSES, type ClientStatus } from "@/app/_lib/items";
import { deleteItem, updateItem } from "@/app/_lib/items";
import { getServiceBaseUrl } from "@/app/_lib/utils";

export type AddItemActionState =
  | { status: "idle" }
  | { status: "success"; itemId: string }
  | { status: "error"; message: string };

export async function addItemAction(
  _prevState: AddItemActionState,
  formData: FormData,
): Promise<AddItemActionState> {
  const rawUrl = formData.get("url");
  const url = typeof rawUrl === "string" ? rawUrl.trim() : "";
  if (!url) {
    return { status: "error", message: "Please enter a valid URL." };
  }

  const session = await getSession();
  if (!session) {
    return {
      status: "error",
      message: "You need to sign in before adding items.",
    };
  }

  try {
    const baseUrl = getServiceBaseUrl();

    const headers: Record<string, string> = {
      Authorization: `Bearer ${session.token}`,
      "Content-Type": "application/json",
    };

    const response = await fetch(`${baseUrl}/items/add`, {
      method: "POST",
      headers,
      body: JSON.stringify({ url }),
    });

    if (!response.ok) {
      let message = "Unable to add item.";
      if (response.status === 409) {
        // Friendlier message for duplicate URL
        message = "This URL is already in your queue.";
      }
      try {
        const data = (await response.json()) as { detail?: string };
        if (data?.detail) {
          message = data.detail;
        }
      } catch (error) {
        console.warn("Failed to parse add item response", error);
      }
      return { status: "error", message };
    }

    const payload = (await response.json()) as { item_id?: string };
    const itemId = payload?.item_id?.trim();
    if (!itemId) {
      return {
        status: "error",
        message: "Item created but no identifier was returned.",
      };
    }

    revalidatePath("/queue");
    return { status: "success", itemId };
  } catch (error) {
    console.error("Failed to call item add endpoint", error);
    return {
      status: "error",
      message: "An unexpected error occurred while adding the item.",
    };
  }
}

function normaliseReturnPath(path: string): string {
  if (!path) {
    return "/queue";
  }

  const trimmed = path.trim();
  if (!trimmed) {
    return "/queue";
  }

  try {
    const url = new URL(trimmed, "http://localhost");
    return url.pathname + url.search;
  } catch (error) {
    console.warn("Invalid return path supplied to action", { path, error });
    return "/queue";
  }
}

type ClientUpdatableStatus = (typeof CLIENT_UPDATABLE_STATUSES)[number];

function sanitiseStatus(input: ClientUpdatableStatus): ClientUpdatableStatus {
  if (CLIENT_UPDATABLE_STATUSES.includes(input)) {
    return input;
  }
  throw new Error(`Invalid status supplied: ${input}`);
}

function revalidateCommonPaths(target: string) {
  revalidatePath("/queue");
  revalidatePath("/search");
  const [basePath] = target.split("?");
  if (basePath) {
    revalidatePath(basePath);
  }
}

export async function updateItemStatusAction(
  itemId: string,
  status: ClientUpdatableStatus,
  returnPath: string,
) {
  const session = await getSession();
  if (!session) {
    redirect("/login");
  }

  const safeStatus = sanitiseStatus(status);
  const nextPath = normaliseReturnPath(returnPath);

  const now = new Date().toISOString();
  const payload: Parameters<typeof updateItem>[1] = {
    client_status: safeStatus,
    client_status_at: now,
  };

  try {
    await updateItem(itemId, payload);
  } catch (error) {
    console.error("Failed to update item status", {
      itemId,
      status: safeStatus,
      error,
    });
    throw error;
  }

  revalidateCommonPaths(nextPath);
  redirect(nextPath);
}

export type DeleteItemActionResult = { success: true };

export async function deleteItemAction(
  itemId: string,
  returnPath: string,
): Promise<DeleteItemActionResult> {
  const session = await getSession();
  if (!session) {
    redirect("/login");
  }

  const nextPath = normaliseReturnPath(returnPath);

  try {
    await deleteItem(itemId);
  } catch (error) {
    console.error("Failed to delete item", { itemId, error });
    throw error;
  }

  revalidateCommonPaths(nextPath);
  return { success: true };
}
