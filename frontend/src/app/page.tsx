import { Background } from "@/components/Background";
import { Hero } from "@/components/Hero";
import { Navbar } from "@/components/Navbar";

export default function Home() {
  return (
    <main className="relative min-h-screen overflow-hidden bg-black text-white">
      <Background />
      <Navbar />
      <Hero />
    </main>
  );
}