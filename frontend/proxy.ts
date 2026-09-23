import { NextRequest, NextResponse } from "next/server";

/**
 * Route guard for the (app)/* route group.
 *
 * Next.js 16 renamed the `middleware` convention to `proxy` (both the file
 * and the exported function); the edge runtime is not supported here, the
 * runtime is always nodejs.
 *
 * httpOnly cookies are unreadable from client-side document.cookie, but
 * NextRequest.cookies runs server-side and CAN read them — httpOnly only
 * blocks JS access in the browser. So presence of access_token/refresh_token
 * is checked here, redirecting to /login when neither is set.
 *
 * /login, /setup (the first-run wizard: on a fresh deployment nobody can sign in yet, and its
 * one dangerous call is protected by the setup token on the server) and /verify/* (the public
 * QR-scan landing page, Phase 5) bypass the guard entirely.
 */

const PUBLIC_EXACT_PATHS = new Set(["/login", "/setup"]);

function isPublicPath(pathname: string): boolean {
  if (PUBLIC_EXACT_PATHS.has(pathname)) return true;
  if (pathname.startsWith("/verify/")) return true;
  return false;
}

export function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;

  if (isPublicPath(pathname)) {
    return NextResponse.next();
  }

  const accessToken = request.cookies.get("access_token")?.value;
  const refreshToken = request.cookies.get("refresh_token")?.value;

  if (!accessToken && !refreshToken) {
    const loginUrl = new URL("/login", request.url);
    // Keep the query too: on /inbox?c=42 it is the open conversation, and the login page's
    // safeNextPath decides whether the whole thing is a safe place to return to.
    if (pathname !== "/") {
      loginUrl.searchParams.set("next", pathname + search);
    }
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  // Run on everything except static assets / Next internals.
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)"],
};
