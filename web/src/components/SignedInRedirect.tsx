"use client";

import { useAuth } from "@clerk/nextjs";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

/**
 * Sends signed-in visitors from the marketing homepage to their dashboard.
 *
 * This used to be a server-side redirect, which required Clerk's middleware on
 * "/". Doing it in the browser keeps the homepage free of that middleware, so
 * search crawlers get a plain 200 instead of Clerk's development-instance
 * handshake loop. Signed-out visitors, crawlers included, are never redirected.
 */
export default function SignedInRedirect() {
  const { isLoaded, isSignedIn } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (isLoaded && isSignedIn) router.replace("/dashboard");
  }, [isLoaded, isSignedIn, router]);

  return null;
}
