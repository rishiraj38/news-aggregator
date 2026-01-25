import Link from "next/link";
import Navbar from "@/components/Navbar";
import { Check, ArrowRight, Brain, Zap, Shield } from "lucide-react";
import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";

export default async function Home() {
  const { userId } = await auth();

  if (userId) {
    redirect("/dashboard");
  }

  return (
    <main className="min-h-screen bg-neutral-950 text-white selection:bg-purple-900/30">
      <Navbar />

      {/* Hero Section */}
      <section className="pt-32 pb-20 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto flex flex-col items-center text-center">
        <div className="inline-flex items-center rounded-full border border-purple-500/20 bg-purple-500/5 px-3 py-1 text-sm font-medium text-purple-300 mb-8">
          <span className="flex h-2 w-2 rounded-full bg-purple-400 mr-2 animate-pulse"></span>
          v2.0: Dynamic Search Engine
        </div>

        <h1 className="text-5xl sm:text-7xl font-bold tracking-tight mb-8 text-white">
          Cut through the <br />
          <span className="text-transparent bg-clip-text bg-linear-to-br from-purple-400 to-blue-500">
            Information Noise
          </span>
        </h1>

        <p className="text-lg sm:text-xl text-gray-400 max-w-2xl mb-12 leading-relaxed">
          Helix uses autonomous agents to scan thousands of sources daily. We
          rank, summarize, and deliver only what matters to your career.
        </p>

        <div className="flex flex-col sm:flex-row gap-4">
          <Link
            href="/dashboard"
            className="px-8 py-3.5 rounded-full bg-white text-black font-semibold text-lg hover:bg-gray-100 transition flex items-center justify-center"
          >
            Start Free Trial <ArrowRight className="ml-2 w-5 h-5" />
          </Link>
          <Link
            href="#pricing"
            className="px-8 py-3.5 rounded-full border border-white/10 hover:border-white/20 hover:bg-white/5 transition text-lg font-medium text-gray-300"
          >
            View Pricing
          </Link>
        </div>
      </section>

      {/* Features Grid */}
      <section className="py-24 bg-neutral-900/30 border-y border-white/5">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 grid md:grid-cols-3 gap-12">
          <div className="p-6 rounded-2xl bg-white/5 border border-white/5">
            <Brain className="w-10 h-10 text-purple-400 mb-6" />
            <h3 className="text-xl font-bold mb-3">AI Curation</h3>
            <p className="text-gray-400">
              Our agents read 5,000+ articles daily so you don't have to.
            </p>
          </div>
          <div className="p-6 rounded-2xl bg-white/5 border border-white/5">
            <Zap className="w-10 h-10 text-blue-400 mb-6" />
            <h3 className="text-xl font-bold mb-3">Zero Noise</h3>
            <p className="text-gray-400">
              Strict relevance filters ensure you only see engineering-grade
              content.
            </p>
          </div>
          <div className="p-6 rounded-2xl bg-white/5 border border-white/5">
            <Shield className="w-10 h-10 text-green-400 mb-6" />
            <h3 className="text-xl font-bold mb-3">Source Verified</h3>
            <p className="text-gray-400">
              We prioritize primary sources: Docs, GitHub repos, and Papers.
            </p>
          </div>
        </div>
      </section>

      {/* Pricing Section */}
      <section id="pricing" className="py-24 px-4 bg-neutral-950">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-3xl font-bold mb-4">Transparent Pricing</h2>
            <p className="text-gray-400">
              Invest in your knowledge. Cancel anytime.
            </p>
          </div>

          <div className="grid md:grid-cols-2 gap-8 max-w-4xl mx-auto">
            {/* Free Tier */}
            <div className="p-8 rounded-2xl border border-white/10 bg-neutral-900 hover:border-white/20 transition">
              <h3 className="text-xl font-bold mb-2">Explorer</h3>
              <div className="text-4xl font-bold mb-6">$0</div>
              <p className="text-gray-400 mb-6">Essential daily briefing.</p>
              <ul className="space-y-4 mb-8 text-gray-400 text-sm">
                <li className="flex items-center">
                  <Check className="w-4 h-4 mr-3 text-white" /> Top 3 Articles
                  Daily
                </li>
                <li className="flex items-center">
                  <Check className="w-4 h-4 mr-3 text-white" /> Weekend Recap
                </li>
              </ul>
              <Link
                href="/sign-in"
                className="block w-full text-center py-3 rounded-xl border border-white/10 hover:bg-white/5 transition text-sm font-medium"
              >
                Get Started
              </Link>
            </div>

            {/* Pro Tier */}
            <div className="p-8 rounded-2xl border border-purple-500/30 bg-purple-900/10 relative">
              <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-purple-600 text-white px-3 py-1 text-xs font-bold rounded-full tracking-wider uppercase shadow-lg shadow-purple-900/50">
                Most Popular
              </div>
              <h3 className="text-xl font-bold mb-2 text-white">Full Access</h3>
              <div className="flex items-baseline mb-6">
                <span className="text-4xl font-bold">$7</span>
                <span className="text-gray-400 ml-2">/mo</span>
              </div>
              <p className="text-purple-200/80 mb-6">
                Complete research suite.
              </p>
              <ul className="space-y-4 mb-8 text-gray-300 text-sm">
                <li className="flex items-center">
                  <Check className="w-4 h-4 mr-3 text-purple-400" /> Unlimited
                  Daily Digest
                </li>
                <li className="flex items-center">
                  <Check className="w-4 h-4 mr-3 text-purple-400" /> Custom
                  Tracked Keywords
                </li>
                <li className="flex items-center">
                  <Check className="w-4 h-4 mr-3 text-purple-400" /> Arxiv Paper
                  Search
                </li>
                <li className="flex items-center">
                  <Check className="w-4 h-4 mr-3 text-purple-400" /> Priority
                  Email Delivery
                </li>
              </ul>
              <Link
                href="/sign-in"
                className="block w-full text-center py-3 rounded-xl bg-white text-black font-bold hover:bg-gray-200 transition text-sm"
              >
                Start 7-Day Free Trial
              </Link>
            </div>
          </div>
        </div>
      </section>

      <footer className="py-12 border-t border-white/10 text-center text-gray-500 text-sm">
        <p>© 2026 Helix Intelligence. All rights reserved.</p>
      </footer>
    </main>
  );
}
