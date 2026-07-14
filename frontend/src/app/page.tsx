import { Background } from "@/components/Background";
import { Hero } from "@/components/Hero";

export default function Home() {
  return (
    <main className="relative min-h-screen w-full overflow-hidden bg-black text-white">
      <Background />
      <Hero />
    </main>
  );
}