/**
 * Helper to normalize page path for consistent storage
 * This utility works on both client and server
 */
export function normalizePagePath(pathname: string): string {
  // Remove query params and fragments, normalize slashes
  let path = pathname.split("?")[0].split("#")[0];

  // Remove leading slash for consistent storage (e.g., "queue" not "/queue")
  if (path.startsWith("/")) {
    path = path.substring(1);
  }

  // Handle root path
  if (path === "") {
    path = "home";
  }

  return path;
}
