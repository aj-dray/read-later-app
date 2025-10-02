"use server";

import { cookies } from "next/headers";

import { getServiceBaseUrl } from "@/app/_lib/utils";

export type Session = {
  token: string;
  username?: string;
};

const SESSION_COOKIE_NAME = "later_session";

type JwtPayload = {
  exp?: number;
  sub?: string;
  [key: string]: unknown;
};

function decodeJwtPayload(token: string): JwtPayload | null {
  const parts = token.split(".");
  if (parts.length < 2) {
    return null;
  }

  const payloadSegment = parts[1];
  const normalised = payloadSegment.replace(/-/g, "+").replace(/_/g, "/");
  const padding = "=".repeat((4 - (normalised.length % 4)) % 4);

  try {
    const decoded = Buffer.from(normalised + padding, "base64").toString(
      "utf-8",
    );
    const payload = JSON.parse(decoded) as unknown;
    if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
      return null;
    }
    return payload as JwtPayload;
  } catch (error) {
    console.warn("Failed to decode JWT payload", error);
    return null;
  }
}

function isExpired(payload: JwtPayload): boolean {
  if (typeof payload.exp !== "number") {
    return true;
  }
  const expiryMillis = payload.exp * 1000;
  return Number.isFinite(expiryMillis) && expiryMillis <= Date.now();
}

export async function getSession(): Promise<Session | null> {
  const cookieStore = await cookies();
  const token = cookieStore.get(SESSION_COOKIE_NAME)?.value?.trim();
  if (!token) {
    return null;
  }

  const payload = decodeJwtPayload(token);
  if (!payload || isExpired(payload)) {
    return null;
  }
  return { token, username: payload.sub };
}

export async function setSession(token: string): Promise<void> {
  const cookieStore = await cookies();
  cookieStore.set({
    name: SESSION_COOKIE_NAME,
    value: token,
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 60 * 60 * 24 * 7, // one week
  });
}

export async function clearSession(): Promise<void> {
  const cookieStore = await cookies();
  cookieStore.delete(SESSION_COOKIE_NAME);
}

export async function requireSession(): Promise<Session> {
  const session = await getSession();
  if (!session) {
    throw new Error("Missing session");
  }
  return session;
}

export async function authedFetch(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const baseUrl = getServiceBaseUrl();
  const session = await getSession();

  const headers = new Headers(init.headers ?? {});
  if (session) {
    headers.set("Authorization", `Bearer ${session.token}`);
  }

  const isAbsoluteUrl = /^https?:\/\//i.test(path);
  const normalisedPath = path.startsWith("/") ? path : `/${path}`;
  const url = isAbsoluteUrl ? path : `${baseUrl}${normalisedPath}`;

  return fetch(url, {
    ...init,
    headers,
  });
}
