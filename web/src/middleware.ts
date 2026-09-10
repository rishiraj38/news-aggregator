import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import type { NextFetchEvent, NextRequest } from "next/server";
import { NextResponse } from "next/server";

const isPublicRoute = createRouteMatcher([
  "/",
  "/sitemap.xml",
  "/robots.txt",
  "/manifest.webmanifest",
  "/google(.*).html",
  "/sign-in(.*)",
  "/sign-up(.*)",
  "/api/webhooks(.*)",
]);

const withClerk = clerkMiddleware(async (auth, request) => {
  if (!isPublicRoute(request)) {
    const { userId, redirectToSignIn } = await auth();
    if (!userId) {
      return redirectToSignIn();
    }
  }
});

/**
 * The marketing homepage bypasses Clerk entirely.
 *
 * On a Clerk *development* instance (pk_test_…), the middleware answers any
 * cookieless, browser-like request with a "handshake" redirect to
 * clerk.accounts.dev and back to set a cookie. Search crawlers keep no cookies,
 * so for them it's an endless loop — Google Search Console reported "Redirect
 * error" and never indexed the site. The homepage needs no server-side auth
 * (signed-in visitors are forwarded client-side by SignedInRedirect), so it
 * skips the middleware. Every other route is still protected.
 *
 * A Clerk production instance on a custom domain doesn't do this handshake for
 * signed-out visitors, which would make this bypass unnecessary.
 */
export default function middleware(request: NextRequest, event: NextFetchEvent) {
  if (request.nextUrl.pathname === "/") {
    return NextResponse.next();
  }
  return withClerk(request, event);
}

export const config = {
  matcher: [
    // Skip Next.js internals and all static files, unless found in search params
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest|xml|txt)).*)",
    // Always run for API routes
    "/(api|trpc)(.*)",
  ],
};
