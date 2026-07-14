const QUICK_LINKS = [
  { label: "Dashboard", href: "/dashboard" },
  { label: "Markets", href: "/markets" },
  { label: "AI Picks", href: "/ai-picks" },
  { label: "News", href: "/news" },
  { label: "Pricing", href: "/pricing" },
];

const LEGAL_LINKS = [
  { label: "Privacy Policy", href: "/privacy" },
  { label: "Terms", href: "/terms" },
  { label: "Disclaimer", href: "/disclaimer" },
  { label: "Contact", href: "/contact" },
];

export function Footer() {
  return (
    <footer className="relative z-10 w-full border-t border-white/10 bg-zinc-950 px-6 py-12 sm:px-10">
      <div className="mx-auto max-w-7xl">
        <div className="grid grid-cols-1 gap-10 md:grid-cols-3">
          <div>
            <div className="mb-4 flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_10px_2px_rgba(52,211,153,0.7)]" />

              <span className="text-sm font-semibold uppercase tracking-[0.25em] text-zinc-100">
                Alpha<span className="text-emerald-400">Edge</span> AI
              </span>
            </div>

            <p className="max-w-sm text-sm leading-relaxed text-zinc-400">
              AI-powered stock intelligence platform built for Indian
              investors.
            </p>
          </div>

          <div>
            <h3 className="mb-4 text-sm font-semibold uppercase tracking-wider text-zinc-200">
              Quick Links
            </h3>

            <ul className="space-y-3">
              {QUICK_LINKS.map((link) => (
                <li key={link.href}>
                  <a
                    href={link.href}
                    className="text-sm text-zinc-400 transition-colors hover:text-emerald-400"
                  >
                    {link.label}
                  </a>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <h3 className="mb-4 text-sm font-semibold uppercase tracking-wider text-zinc-200">
              Legal
            </h3>

            <ul className="space-y-3">
              {LEGAL_LINKS.map((link) => (
                <li key={link.href}>
                  <a
                    href={link.href}
                    className="text-sm text-zinc-400 transition-colors hover:text-emerald-400"
                  >
                    {link.label}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="mt-10 flex flex-col gap-3 border-t border-white/10 pt-6 text-center md:flex-row md:items-center md:justify-between md:text-left">
          <p className="text-xs text-zinc-500">
            © 2026 AlphaEdge AI. All rights reserved.
          </p>

          <p className="max-w-xl text-xs text-zinc-500">
            Probability-based insights for education and research only. Not
            SEBI-registered investment advice.
          </p>
        </div>
      </div>
    </footer>
  );
}