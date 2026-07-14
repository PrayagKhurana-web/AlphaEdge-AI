const MARKET_ITEMS = [
  { name: "NIFTY 50", value: "24,572.30", change: "+0.82%" },
  { name: "SENSEX", value: "80,645.12", change: "+0.64%" },
  { name: "BANK NIFTY", value: "52,318.75", change: "-0.21%" },
  { name: "INDIA VIX", value: "13.42", change: "-1.08%" },
];

export function MarketPreview() {
  return (
    <section className="relative z-10 border-y border-white/5 bg-zinc-950/50 backdrop-blur">
      <div className="mx-auto grid max-w-7xl grid-cols-2 gap-px bg-white/5 md:grid-cols-4">
        {MARKET_ITEMS.map((item) => {
          const isPositive = item.change.startsWith("+");

          return (
            <div key={item.name} className="bg-black/70 px-5 py-5">
              <p className="text-xs font-medium uppercase tracking-wider text-zinc-500">
                {item.name}
              </p>

              <div className="mt-2 flex items-end justify-between gap-3">
                <p className="text-lg font-semibold text-zinc-100">
                  {item.value}
                </p>

                <p
                  className={`text-sm font-medium ${
                    isPositive ? "text-emerald-400" : "text-red-400"
                  }`}
                >
                  {item.change}
                </p>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}