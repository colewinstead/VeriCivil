import { authkitProxy } from "@workos-inc/authkit-nextjs";
import { NextResponse, type NextFetchEvent, type NextRequest } from "next/server";

const configuredProxy = authkitProxy({
  redirectUri: process.env.NEXT_PUBLIC_WORKOS_REDIRECT_URI || "http://localhost:3000/auth/callback",
});

export default function proxy(request: NextRequest, event: NextFetchEvent) {
  const configured = Boolean(
    process.env.WORKOS_API_KEY
      && process.env.WORKOS_CLIENT_ID
      && process.env.WORKOS_COOKIE_PASSWORD
      && process.env.NEXT_PUBLIC_WORKOS_REDIRECT_URI,
  );
  return configured ? configuredProxy(request, event) : NextResponse.next();
}

export const config = {
  matcher: [
    "/account/:path*",
    "/admin/:path*",
    "/login",
    "/auth/:path*",
    "/api/entitlement",
    "/api/analytics/:path*",
    "/api/admin/:path*",
    "/api/billing/:path*",
  ],
};
