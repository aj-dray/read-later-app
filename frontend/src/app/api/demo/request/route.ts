export const dynamic = "force-dynamic";
export const revalidate = 0;
export const fetchCache = "force-no-store";

import { NextResponse } from "next/server";
import { getServiceBaseUrl } from "@/app/_lib/utils";

const RATE_LIMIT_MAX = 3;
const RATE_LIMIT_WINDOW_MS = 24 * 60 * 60 * 1000; // 1 day
const rateLimitStore = new Map<string, number[]>();

function getClientKey(request: Request) {
  const forwardedFor = request.headers.get("x-forwarded-for");
  if (forwardedFor) {
    return forwardedFor.split(",")[0]?.trim() ?? "unknown";
  }
  const realIp = request.headers.get("x-real-ip");
  if (realIp) {
    return realIp.trim();
  }
  return "unknown";
}

function pruneOldEntries(timestamps: number[], now: number) {
  return timestamps.filter((timestamp) => now - timestamp < RATE_LIMIT_WINDOW_MS);
}

function updateStore(clientKey: string, timestamps: number[]) {
  if (timestamps.length === 0) {
    rateLimitStore.delete(clientKey);
  } else {
    rateLimitStore.set(clientKey, timestamps);
  }
}

export async function POST(request: Request) {
  const clientKey = getClientKey(request);
  const now = Date.now();
  const existing = rateLimitStore.get(clientKey) ?? [];
  const recent = pruneOldEntries(existing, now);

  if (recent.length >= RATE_LIMIT_MAX) {
    updateStore(clientKey, recent);
    return NextResponse.json(
      {
        error: "Demo limit reached. Please try again tomorrow.",
      },
      { status: 429 },
    );
  }

  updateStore(clientKey, recent);

  try {
    const backendUrl = new URL("/demo/request", getServiceBaseUrl()).toString();

    const response = await fetch(backendUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });

    const text = await response.text();
    const payload = text ? JSON.parse(text) : {};
    const detail = typeof payload?.detail === "string" ? payload.detail : undefined;

    if (response.ok) {
      const latest = rateLimitStore.get(clientKey) ?? [];
      const updated = pruneOldEntries(latest, now);
      updated.push(now);
      updateStore(clientKey, updated);
      return NextResponse.json(payload, { status: response.status });
    }

    const errorPayload = detail ? { error: detail } : payload;
    return NextResponse.json(errorPayload, { status: response.status });
  } catch (error) {
    console.error("Failed to proxy demo request", error);
    return NextResponse.json({ error: "Unable to request demo" }, { status: 500 });
  }
}
