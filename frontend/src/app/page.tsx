import { Background } from "@/components/Background";
import { FeatureCards } from "@/components/FeatureCards";
import { Footer } from "@/components/Footer";
import { Hero } from "@/components/Hero";
import { MarketPreview } from "@/components/MarketPreview";
import { Navbar } from "@/components/Navbar";

export default function Home() {
  return (
    <main className="relative min-h-screen bg-black text-white">
      <Background />
      <Navbar />
      <Hero />
      <MarketPreview />
      <FeatureCards />
      <Footer />
    </main>
  );
}