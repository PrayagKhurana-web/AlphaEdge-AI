"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { useAuth } from "@/auth/useAuth";

const NAV_LINKS = [
  { label: "Dashboard", href: "/dashboard" },
  { label: "Markets", href: "/markets" },
  { label: "AI Picks", href: "/ai-picks" },
  { label: "Pulse", href: "/pulse" },
  { label: "Multibagger", href: "/multibagger" },
  { label: "News", href: "/news" },
  { label: "Pricing", href: "/pricing" },
];

export function Navbar() {
  const router = useRouter();
  const {
    user,
    isAuthenticated,
    isRestoringSession,
    logout,
  } = useAuth();

  const [isMenuOpen, setIsMenuOpen] = useState(false);

  function handleLogout(): void {
    logout();
    setIsMenuOpen(false);
    router.push("/");
  }

  return (
    <header className="sticky top-0 z-50 w-full border-b border-white/5 bg-black/70 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6 sm:px-10">
        <Link href="/" className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_10px_2px_rgba(52,211,153,0.7)]" />

          <span className="text-sm font-semibold uppercase tracking-[0.25em] text-zinc-100">
            Alpha<span className="text-emerald-400">Edge</span> AI
          </span>
        </Link>

        <nav className="hidden items-center gap-8 md:flex">
          {NAV_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="relative text-sm font-medium text-zinc-400 transition-colors duration-200 hover:text-white after:absolute after:-bottom-1 after:left-0 after:h-px after:w-0 after:bg-emerald-400 after:transition-all after:duration-200 hover:after:w-full"
            >
              {link.label}
            </Link>
          ))}
        </nav>

        <div className="hidden items-center gap-3 md:flex">
          {!isRestoringSession && isAuthenticated && user ? (
            <>
              <span
                title={user.email}
                className="max-w-48 truncate text-xs text-zinc-500"
              >
                {user.email}
              </span>

              <Link
                href="/dashboard"
                className="rounded-lg border border-zinc-700 px-4 py-2 text-sm font-medium text-zinc-200 transition hover:border-zinc-500 hover:bg-zinc-900"
              >
                Dashboard
              </Link>

              <button
                type="button"
                onClick={handleLogout}
                className="rounded-lg border border-red-500/20 px-4 py-2 text-sm font-medium text-red-300 transition hover:bg-red-500/10"
              >
                Log out
              </button>
            </>
          ) : (
            <>
              <Link
                href="/auth"
                className="rounded-lg border border-zinc-700 px-5 py-2 text-sm font-medium text-zinc-200 transition-colors hover:border-zinc-500 hover:bg-zinc-900"
              >
                Login
              </Link>

              <Link
                href="/auth"
                className="rounded-lg bg-emerald-500 px-5 py-2 text-sm font-semibold text-black transition-colors hover:bg-emerald-400"
              >
                Get Started
              </Link>
            </>
          )}
        </div>

        <button
          type="button"
          aria-label="Toggle navigation menu"
          aria-expanded={isMenuOpen}
          onClick={() =>
            setIsMenuOpen((current) => !current)
          }
          className="flex h-9 w-9 items-center justify-center rounded-lg border border-zinc-800 text-zinc-200 md:hidden"
        >
          <span className="text-lg">
            {isMenuOpen ? "X" : "Menu"}
          </span>
        </button>
      </div>

      {isMenuOpen && (
        <div className="border-t border-white/5 bg-black/95 md:hidden">
          <nav className="flex flex-col gap-1 px-6 py-4">
            {NAV_LINKS.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                onClick={() => setIsMenuOpen(false)}
                className="rounded-lg px-3 py-2 text-sm font-medium text-zinc-300 hover:bg-zinc-900 hover:text-white"
              >
                {link.label}
              </Link>
            ))}

            <div className="mt-3 flex flex-col gap-2 border-t border-white/5 pt-3">
              {!isRestoringSession &&
              isAuthenticated &&
              user ? (
                <>
                  <p className="truncate px-3 py-2 text-xs text-zinc-500">
                    {user.email}
                  </p>

                  <button
                    type="button"
                    onClick={handleLogout}
                    className="rounded-lg border border-red-500/20 px-4 py-2 text-center text-sm font-medium text-red-300"
                  >
                    Log out
                  </button>
                </>
              ) : (
                <>
                  <Link
                    href="/auth"
                    onClick={() => setIsMenuOpen(false)}
                    className="rounded-lg border border-zinc-700 px-4 py-2 text-center text-sm font-medium text-zinc-200"
                  >
                    Login
                  </Link>

                  <Link
                    href="/auth"
                    onClick={() => setIsMenuOpen(false)}
                    className="rounded-lg bg-emerald-500 px-4 py-2 text-center text-sm font-semibold text-black"
                  >
                    Get Started
                  </Link>
                </>
              )}
            </div>
          </nav>
        </div>
      )}
    </header>
  );
}
