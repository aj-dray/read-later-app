export const dynamic = "force-dynamic";
export const revalidate = 0;
export const fetchCache = "force-no-store";

import { NextResponse } from "next/server";

import { authedFetch } from "@/app/_lib/items";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const search = url.search;
  const path = search ? `/clusters/generate${search}` : "/clusters/generate";

  try {
    const response = await authedFetch(path);
    const text = await response.text();
    const payload = text ? JSON.parse(text) : {};

    return NextResponse.json(payload, { status: response.status });
  } catch (error) {
    console.error("Failed to proxy clustering request", error);
    return NextResponse.json(
      { error: "Unable to generate clustering" },
      { status: 500 },
    );
  }
}
