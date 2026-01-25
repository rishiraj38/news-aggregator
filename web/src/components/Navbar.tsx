"use client";

import Link from "next/link";
import { useUser, UserButton } from "@clerk/nextjs";
import { Menu, X } from "lucide-react";
import { useState } from "react";

export default function Navbar() {
  const { isSignedIn } = useUser();
  const [isOpen, setIsOpen] = useState(false);

  return (
    <nav className="fixed w-full z-50 bg-neutral-950/80 backdrop-blur-md border-b border-white/5">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center">
            <Link
              href={isSignedIn ? "/dashboard" : "/"}
              className="flex items-center gap-3 transition hover:opacity-80"
            >
              <img
                src="/logo.png"
                alt="Helix Logo"
                className="w-8 h-8 object-contain"
              />
              <span className="text-xl font-bold text-white tracking-tight">
                Helix
              </span>
            </Link>
          </div>

          {/* Desktop Menu */}
          <div className="hidden md:block">
            <div className="ml-10 flex items-center space-x-6">
              <Link
                href="/dashboard"
                className="text-gray-400 hover:text-white text-sm font-medium transition-colors"
              >
                Dashboard
              </Link>
              {isSignedIn ? (
                <UserButton afterSignOutUrl="/" />
              ) : (
                <Link
                  href="/sign-in"
                  className="bg-white text-black px-5 py-2 rounded-full text-sm font-semibold hover:bg-gray-200 transition"
                >
                  Sign In
                </Link>
              )}
            </div>
          </div>

          {/* Mobile Menu Button + User Avatar */}
          <div className="md:hidden flex items-center gap-4">
            {isSignedIn && <UserButton afterSignOutUrl="/" />}
            <button
              onClick={() => setIsOpen(!isOpen)}
              className="text-gray-400 hover:text-white p-2"
            >
              {isOpen ? <X size={24} /> : <Menu size={24} />}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Menu Dropdown */}
      {isOpen && (
        <div className="md:hidden bg-neutral-950 border-b border-white/5">
          <div className="px-4 pt-2 pb-6 space-y-4">
            <Link
              href="/dashboard"
              className="block text-gray-400 hover:text-white text-base font-medium"
              onClick={() => setIsOpen(false)}
            >
              Dashboard
            </Link>
            {!isSignedIn && (
              <Link
                href="/sign-in"
                className="block w-full text-center bg-white text-black px-5 py-3 rounded-lg text-base font-semibold hover:bg-gray-200 transition"
                onClick={() => setIsOpen(false)}
              >
                Sign In
              </Link>
            )}
          </div>
        </div>
      )}
    </nav>
  );
}
