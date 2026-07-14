import { Background } from "@/components/Background";
import { Navbar } from "@/components/Navbar";
import { Hero } from "@/components/Hero";
import { MarketPreview } from "@/components/MarketPreview";
import { FeatureCards } from "@/components/FeatureCards";

export default function Home() {
  return (
    <main className="relative min-h-screen overflow-hidden bg-black text-white">
      <Background />
      <Navbar />
      <Hero />
      <MarketPreview />
      <FeatureCards />
    </main>
  );
}