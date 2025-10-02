import "server-only";

const FALLBACK_SERVICE_URL = "http://localhost:8000";

function normaliseBaseUrl(input: string | undefined): string {
  if (!input || !input.trim()) {
    return FALLBACK_SERVICE_URL;
  }
  return input.replace(/\/$/, "");
}

export function getServiceBaseUrl(): string {
  const baseUrl =
    process.env.BACKEND_URL ||
    process.env.LATER_SERVICE_URL ||
    process.env.NEXT_PUBLIC_LATER_SERVICE_URL;
  return normaliseBaseUrl(baseUrl);
}
