export function Background() {
  return (
    <>
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_80%_50%_at_50%_-10%,rgba(56,189,248,0.15),transparent)]" />
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-black via-zinc-950 to-black" />
      <div className="pointer-events-none absolute left-1/2 top-1/3 h-[500px] w-[500px] -translate-x-1/2 rounded-full bg-emerald-500/10 blur-[120px]" />
    </>
  );
}