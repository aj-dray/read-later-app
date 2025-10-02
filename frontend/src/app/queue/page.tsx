export const dynamic = "force-dynamic";

import { redirect } from "next/navigation";

import { getSession } from "@/app/_lib/auth";
import type { ItemSummary } from "@/app/_lib/items";
import { fetchItems } from "@/app/_lib/items";
import QueueClient from "./QueueClient";

export default async function QueuePage() {
  const session = await getSession();
  if (!session) {
    redirect("/login");
  }

  let items: ItemSummary[] = [];
  try {
    items = await fetchItems({
      limit: 100,
      orderBy: "created_at",
      order: "desc",
    });
  } catch (error) {
    if (error instanceof Error && error.message.includes("401")) {
      redirect("/login");
    }
    throw error;
  }

  return (
    <div
      className="flex h-full w-full flex-col bg-[#F0F0F0] overflow-auto"
      style={{
        paddingRight: "calc(var(--panels-width, 0px) + 25px)",
      }}
    >
      <QueueClient initialItems={items} />
    </div>
  );
}
