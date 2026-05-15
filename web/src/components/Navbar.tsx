"use client";

import Link from "next/link";
import { useUser, UserButton } from "@clerk/nextjs";
import { Menu, X } from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/utils";

export default function Navbar() {
  const { isSignedIn } = useUser();
  const [isOpen, setIsOpen] = useState(false);

  const links = (
    <>
      <Link
        href="/dashboard"
        className="text-sm font-medium text-ink-muted hover:text-ink transition-colors"
        onClick={() => setIsOpen(false)}
      >
        Feed
      </Link>
      {!isSignedIn && (
        <a
          href="#pricing"
          className="text-sm font-medium text-ink-muted hover:text-ink transition-colors"
          onClick={() => setIsOpen(false)}
        >
          Pricing
        </a>
      )}
    </>
  );

  return (
    <header className="fixed top-0 inset-x-0 z-[60] border-b border-line bg-surface-deep/85 backdrop-blur-md supports-[backdrop-filter]:bg-surface-deep/70">
      <nav className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex h-[3.75rem] items-center justify-between gap-4">
          <Link
            href={isSignedIn ? "/dashboard" : "/"}
            className="flex items-center gap-3 shrink-0 group"
            onClick={() => setIsOpen(false)}
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/logo.png"
              alt=""
              width={32}
              height={32}
              className="object-contain opacity-90 group-hover:opacity-100 transition-opacity"
            />
            <span className="font-display text-[1.15rem] sm:text-xl text-ink tracking-tight">
              Helix
            </span>
          </Link>

          <div className="hidden md:flex items-center gap-8">{links}</div>

          <div className="flex items-center gap-3 md:gap-4">
            {isSignedIn ? (
              <UserButton
                afterSignOutUrl="/"
                appearance={{
                  elements: {
                    avatarBox: "w-9 h-9 ring-1 ring-line-strong",
                  },
                }}
              />
            ) : (
              <Link
                href="/sign-in"
                className="hidden sm:inline-flex items-center justify-center rounded-md bg-accent px-4 py-2 text-sm font-semibold text-surface-deep hover:brightness-110 transition-[filter]"
              >
                Sign in
              </Link>
            )}
            <button
              type="button"
              aria-expanded={isOpen}
              aria-label={isOpen ? "Close menu" : "Open menu"}
              onClick={() => setIsOpen((o) => !o)}
              className="md:hidden p-2 -mr-2 rounded-md text-ink-muted hover:text-ink hover:bg-surface-raised transition-colors"
            >
              {isOpen ? <X size={22} strokeWidth={1.75} /> : <Menu size={22} strokeWidth={1.75} />}
            </button>
          </div>
        </div>

        <div
          className={cn(
            "md:hidden overflow-hidden transition-[max-height,opacity] duration-300 ease-out",
            isOpen ? "max-h-48 opacity-100 pb-4 border-b border-line" : "max-h-0 opacity-0 border-b border-transparent pointer-events-none",
          )}
        >
          <div className="flex flex-col gap-4 pt-2">
            {links}
            {!isSignedIn && (
              <Link
                href="/sign-in"
                className="inline-flex w-full items-center justify-center rounded-md bg-accent px-4 py-3 text-sm font-semibold text-surface-deep min-h-11"
                onClick={() => setIsOpen(false)}
              >
                Sign in
              </Link>
            )}
          </div>
        </div>
      </nav>
    </header>
  );
}
