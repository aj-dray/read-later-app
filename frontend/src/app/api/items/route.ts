export const dynamic = "force-dynamic";
export const revalidate = 0;
export const fetchCache = "force-no-store";

import { NextResponse } from "next/server";
import { fetchItems, type ItemSummary } from "@/app/_lib/items";

function sanitiseIds(rawIds: readonly string[]): string[] {
  const set = new Set<string>();
  rawIds.forEach((entry) => {
    entry
      .split(",")
      .map((value) => value.trim())
      .filter((value) => value.length > 0)
      .forEach((value) => set.add(value));
  });
  return Array.from(set);
}

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const idParams = searchParams.getAll("ids");

  try {
    const ids = sanitiseIds(idParams);

    if (ids.length > 0) {
      const items = await fetchItems({
        filters: [
          {
            column: "id",
            operator: "IN",
            value: ids,
          },
        ],
        limit: Math.max(ids.length, 1),
      });

      const itemById = new Map(items.map((item) => [item.id, item]));
      const ordered: ItemSummary[] = ids
        .map((id) => itemById.get(id))
        .filter((item): item is ItemSummary => Boolean(item));

      items.forEach((item) => {
        if (
          !ids.includes(item.id) &&
          !ordered.some((entry) => entry.id === item.id)
        ) {
          ordered.push(item);
        }
      });

      return NextResponse.json({ items: ordered });
    }

    const limitParam = searchParams.get("limit");
    const limit = limitParam ? Number.parseInt(limitParam, 10) : 50;
    const safeLimit = Number.isFinite(limit)
      ? Math.min(Math.max(limit, 1), 200)
      : 50;

    const items = await fetchItems({
      limit: safeLimit,
      orderBy: "created_at",
      order: "desc",
    });

    return NextResponse.json({ items });
  } catch (error) {
    console.error("Failed to proxy item fetch", { error });
    return NextResponse.json(
      {
        error: "Unable to fetch items",
      },
      { status: 500 },
    );
  }
}
