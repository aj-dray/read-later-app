import { NextRequest, NextResponse } from "next/server";

const MOBILE_USER_AGENTS = ["Android", "iPhone", "iPad"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const userAgent = request.headers.get("user-agent") || "";

  const isMobile = MOBILE_USER_AGENTS.some((agent) =>
    userAgent.includes(agent),
  );

  // Redirect mobile users to /mobile for non-mobile pages
  if (
    isMobile &&
    pathname !== "/mobile" &&
    !pathname.startsWith("/api/") &&
    pathname !== "/login" &&
    pathname !== "/logout"
  ) {
    return NextResponse.redirect(new URL("/mobile", request.url));
  }

  // Prevent desktop users from accessing /mobile
  if (!isMobile && pathname.startsWith("/mobile")) {
    return NextResponse.redirect(new URL("/", request.url));
  }
  // Pass device classification to the app via request headers so server components can read it
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-device", isMobile ? "mobile" : "desktop");
  return NextResponse.next({ request: { headers: requestHeaders } });
}

export const config = {
  matcher: [
    // Match all routes except for static assets and special Next.js files
    "/((?!api|_next/static|_next/image|favicon.ico).*)",
  ],
};
