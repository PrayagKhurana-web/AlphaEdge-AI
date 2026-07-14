"use client";

import { useState } from "react";

const NAV_LINKS = [
  { label: "Dashboard", href: "/dashboard" },
  { label: "Markets", href: "/markets" },
  { label: "AI Picks", href: "/ai-picks" },
  { label: "News", href: "/news" },
  { label: "Pricing", href: "/pricing" },
];

export function Navbar() {
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 w-full border-b border-white/5 bg-black/40 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6 sm:px-10">
        <a href="/" className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_10px_2px_rgba(52,211,153,0.7)]" />
          <span className="text-sm font-semibold uppercase tracking-[0.25em] text-zinc-100">
            Alpha<span className="text-emerald-400">Edge</span> AI
          </span>
        </a>

        <nav className="hidden items-center gap-8 md:flex">
          {NAV_LINKS.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="relative text-sm font-medium text-zinc-400 transition-colors duration-200 hover:text-white after:absolute after:-bottom-1 after:left-0 after:h-px after:w-0 after:bg-emerald-400 after:transition-all after:duration-200 hover:after:w-full"
            >
              {link.label}
            </a>
          ))}
        </nav>

        <div className="hidden items-center gap-3 md:flex">
          <a
            href="/login"
            className="rounded-lg border border-zinc-700 px-5 py-2 text-sm font-medium text-zinc-200 transition-all duration-200 hover:border-zinc-500 hover:bg-zinc-900/60"
          >
            Login
          </a>

          <a
            href="/get-started"
            className="rounded-lg bg-emerald-500 px-5 py-2 text-sm font-semibold text-black shadow-[0_0_20px_-6px_rgba(52,211,153,0.7)] transition-all duration-200 hover:bg-emerald-400 hover:shadow-[0_0_30px_-6px_rgba(52,211,153,0.9)]"
          >
            Get Started
          </a>
        </div>

        <button
          type="button"
          onClick={() => setIsMenuOpen((prev) => !prev)}
          aria-label="Toggle navigation menu"
          aria-expanded={isMenuOpen}
          className="flex h-9 w-9 items-center justify-center rounded-lg border border-zinc-800 text-zinc-200 transition-colors duration-200 hover:border-zinc-600 md:hidden"
        >
          <span className="relative flex h-4 w-4 flex-col items-center justify-center">
            <span
              className={`absolute h-px w-4 bg-current transition-all duration-200 ${
                isMenuOpen ? "rotate-45" : "-translate-y-1.5"
              }`}
            />
            <span
              className={`absolute h-px w-4 bg-current transition-opacity duration-200 ${
                isMenuOpen ? "opacity-0" : "opacity-100"
              }`}
            />
            <span
              className={`absolute h-px w-4 bg-current transition-all duration-200 ${
                isMenuOpen ? "-rotate-45" : "translate-y-1.5"
              }`}
            />
          </span>
        </button>
      </div>

      {isMenuOpen && (
        <div className="border-t border-white/5 bg-black/80 backdrop-blur-xl md:hidden">
          <nav className="flex flex-col gap-1 px-6 py-4">
            {NAV_LINKS.map((link) => (
              <a
                key={link.href}
                href={link.href}
                onClick={() => setIsMenuOpen(false)}
                className="rounded-lg px-3 py-2 text-sm font-medium text-zinc-300 transition-colors duration-200 hover:bg-zinc-900/60 hover:text-white"
              >
                {link.label}
              </a>
            ))}

            <div className="mt-3 flex flex-col gap-2 border-t border-white/5 pt-3">
              <a
                href="/login"
                className="rounded-lg border border-zinc-700 px-4 py-2 text-center text-sm font-medium text-zinc-200 transition-all duration-200 hover:border-zinc-500 hover:bg-zinc-900/60"
              >
                Login
              </a>

              <a
                href="/get-started"
                className="rounded-lg bg-emerald-500 px-4 py-2 text-center text-sm font-semibold text-black transition-all duration-200 hover:bg-emerald-400"
              >
                Get Started
              </a>
            </div>
          </nav>
        </div>
      )}
    </header>
  );
}