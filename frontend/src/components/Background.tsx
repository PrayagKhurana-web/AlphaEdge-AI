export function Background() {
  return (
    <div
      aria-hidden="true"
      className="pointer-events-none absolute inset-x-0 top-0 h-[900px] overflow-hidden"
    >
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_80%_45%_at_50%_0%,rgba(56,189,248,0.14),transparent_70%)]" />
      <div className="absolute inset-0 bg-gradient-to-b from-black via-zinc-950/80 to-black" />
      <div className="absolute left-1/2 top-72 h-96 w-96 -translate-x-1/2 rounded-full bg-emerald-500/10 blur-[120px]" />
    </div>
  );
}