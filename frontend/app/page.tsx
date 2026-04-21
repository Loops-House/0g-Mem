"use client";

import Link from "next/link";
import { useAccount } from "wagmi";
import { useConnect } from "wagmi";
import { injected } from "wagmi/connectors";
import {
  Lock,
  Cpu,
  FileCheck,
  Terminal,
  MessageCircle,
  Puzzle,
  ArrowRight,
  ChevronRight,
} from "lucide-react";

const PILLARS = [
  {
    icon: Lock,
    label: "Encrypted Memory",
    desc: "Your context is encrypted client-side with your wallet key, stored on 0G Storage, and Merkle-anchored on 0G Chain. Nobody else can read it. Memory strengthens with retrieval, decays with disuse, and episodic history distills into facts over time.",
    color: "text-purple-600",
    bg: "bg-purple-50",
    border: "border-purple-200",
  },
  {
    icon: Cpu,
    label: "Decentralized Inference",
    desc: "Inference runs on 0G Compute — no third-party API dependency, no single point of failure. Every execution is logged to 0G DA: what the agent knew, which tools it called, what it decided.",
    color: "text-violet-600",
    bg: "bg-violet-50",
    border: "border-violet-200",
  },
  {
    icon: FileCheck,
    label: "Verifiable Execution",
    desc: "Every memory write is Merkle-proven and anchored on-chain. Every agent turn is posted to 0G DA. You can prove exactly what your agent knew and did at any point in time.",
    color: "text-indigo-600",
    bg: "bg-indigo-50",
    border: "border-indigo-200",
  },
];

const INTERFACES = [
  {
    icon: Terminal,
    label: "Terminal TUI",
    tag: "Deep work",
    desc: "A fully keyboard-driven terminal interface. Lives next to your code in a tmux split. Conversation history, memory panel, and agent modes — all in the terminal.",
    action: null,
  },
  {
    icon: MessageCircle,
    label: "Telegram Bot",
    tag: "On the go",
    desc: "Quick captures, fast lookups, on-the-go tasks. DM the bot and your agent already has full context from your terminal sessions. Deploy your own instance in one click.",
    action: { label: "Deploy Bot →", href: "/deploy" },
  },
  {
    icon: Puzzle,
    label: "Claude Desktop / Cursor",
    tag: "MCP",
    desc: "Plug into any MCP-compatible client with zero code changes. Your encrypted 0G memory becomes a tool inside Claude Desktop or Cursor — no migration needed.",
    action: null,
  },
];

const STEPS = [
  { step: "01", title: "Memory retrieved", desc: "Relevant memories fetched from 0G Storage before inference starts." },
  { step: "02", title: "Inference", desc: "Message + memory context sent to 0G Compute. Decentralized, no vendor." },
  { step: "03", title: "Tools if needed", desc: "Web search, code execution, APIs — each tool call logged." },
  { step: "04", title: "Memory written", desc: "New memories from the exchange written back to 0G Storage." },
  { step: "05", title: "DA log", desc: "Full execution trace posted to 0G DA. Immutable, provable record." },
];

export default function LandingPage() {
  const { isConnected } = useAccount();
  const { connect, isPending } = useConnect();

  return (
    <div
      style={{
        background: "linear-gradient(140deg, #f3eeff 0%, #faf8ff 50%, #ede6ff 100%)",
        minHeight: "100vh",
      }}
    >
      {/* ── Hero ─────────────────────────────────────────────────────── */}
      <section className="max-w-5xl mx-auto px-4 sm:px-6 pt-20 pb-16 text-center space-y-8">
        <div className="inline-flex items-center gap-2 bg-purple-100 border border-purple-200 rounded-full px-4 py-1.5 text-sm text-purple-700 font-medium">
          <span className="w-2 h-2 rounded-full bg-purple-600 animate-pulse" />
          Built on 0G Labs Infrastructure
        </div>

        <div className="space-y-5">
          <h1 className="text-5xl sm:text-7xl font-bold text-[#1a0533] tracking-tight leading-[1.1]">
            The AI agent stack
            <br />
            <span className="text-purple-600">you actually own.</span>
          </h1>
          <p className="text-lg sm:text-xl text-purple-900/60 max-w-2xl mx-auto leading-relaxed">
            Memory encrypted with your key. Inference on decentralized compute.
            Every decision logged on-chain. No vendor owns your context.
          </p>
        </div>

        <div className="flex items-center justify-center gap-3 flex-wrap">
          <Link
            href="/deploy"
            className="flex items-center gap-2 px-7 py-3.5 rounded-xl text-base font-semibold bg-purple-600 hover:bg-purple-700 text-white transition-all shadow-lg shadow-purple-200"
          >
            Deploy your bot <ArrowRight className="w-4 h-4" />
          </Link>
          {isConnected ? (
            <Link
              href="/memory"
              className="flex items-center gap-2 px-7 py-3.5 rounded-xl text-base font-medium border border-purple-300 text-purple-700 hover:bg-purple-50 transition-all"
            >
              Memory Explorer <ChevronRight className="w-4 h-4" />
            </Link>
          ) : (
            <button
              onClick={() => connect({ connector: injected() })}
              disabled={isPending}
              className="flex items-center gap-2 px-7 py-3.5 rounded-xl text-base font-medium border border-purple-300 text-purple-700 hover:bg-purple-50 transition-all disabled:opacity-50"
            >
              {isPending ? "Connecting…" : "Connect Wallet"}{" "}
              <ChevronRight className="w-4 h-4" />
            </button>
          )}
        </div>

        <div className="flex items-center justify-center gap-8 pt-2">
          {["Private", "Portable", "Provable"].map((tag) => (
            <span
              key={tag}
              className="text-xs font-bold text-purple-500 tracking-[0.15em] uppercase"
            >
              {tag}
            </span>
          ))}
        </div>
      </section>

      {/* ── Three pillars ─────────────────────────────────────────────── */}
      <section className="max-w-5xl mx-auto px-4 sm:px-6 py-16">
        <div className="text-center mb-10 space-y-2">
          <h2 className="text-3xl font-bold text-[#1a0533]">
            Three layers. Fully decentralized.
          </h2>
          <p className="text-purple-900/50 max-w-xl mx-auto text-sm">
            Every component is open, verifiable, and runs on 0G infrastructure.
          </p>
        </div>
        <div className="grid sm:grid-cols-3 gap-5">
          {PILLARS.map(({ icon: Icon, label, desc, color, bg, border }) => (
            <div
              key={label}
              className={`bg-white/70 backdrop-blur border ${border} rounded-2xl p-6 space-y-4`}
            >
              <div
                className={`w-11 h-11 rounded-xl ${bg} border ${border} flex items-center justify-center`}
              >
                <Icon className={`w-5 h-5 ${color}`} />
              </div>
              <div>
                <h3 className="text-base font-semibold text-[#1a0533] mb-2">
                  {label}
                </h3>
                <p className="text-sm text-purple-900/55 leading-relaxed">{desc}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── Interfaces ────────────────────────────────────────────────── */}
      <section className="max-w-5xl mx-auto px-4 sm:px-6 py-16">
        <div className="text-center mb-10 space-y-2">
          <h2 className="text-3xl font-bold text-[#1a0533]">Use it from anywhere.</h2>
          <p className="text-purple-900/50 max-w-xl mx-auto text-sm">
            Same memory, same runtime — across every interface you use.
          </p>
        </div>
        <div className="grid sm:grid-cols-3 gap-5">
          {INTERFACES.map(({ icon: Icon, label, tag, desc, action }) => (
            <div
              key={label}
              className="bg-white/70 backdrop-blur border border-purple-200 rounded-2xl p-6 space-y-4 flex flex-col"
            >
              <div className="flex items-center justify-between">
                <div className="w-11 h-11 rounded-xl bg-purple-50 border border-purple-200 flex items-center justify-center">
                  <Icon className="w-5 h-5 text-purple-600" />
                </div>
                <span className="text-xs font-semibold text-purple-500 bg-purple-50 border border-purple-200 rounded-full px-2.5 py-0.5">
                  {tag}
                </span>
              </div>
              <div className="flex-1">
                <h3 className="text-base font-semibold text-[#1a0533] mb-2">
                  {label}
                </h3>
                <p className="text-sm text-purple-900/55 leading-relaxed">{desc}</p>
              </div>
              {action && (
                <Link
                  href={action.href}
                  className="text-sm font-semibold text-purple-600 hover:text-purple-800 transition-colors"
                >
                  {action.label}
                </Link>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* ── How it works ──────────────────────────────────────────────── */}
      <section className="max-w-5xl mx-auto px-4 sm:px-6 py-16">
        <div className="text-center mb-10 space-y-2">
          <h2 className="text-3xl font-bold text-[#1a0533]">How it works.</h2>
          <p className="text-purple-900/50 text-sm">
            Every message you send goes through this pipeline.
          </p>
        </div>
        <div className="grid sm:grid-cols-5 gap-3">
          {STEPS.map(({ step, title, desc }) => (
            <div
              key={step}
              className="bg-white/70 backdrop-blur border border-purple-200 rounded-2xl p-5"
            >
              <span className="text-xs font-mono font-bold text-purple-400">{step}</span>
              <h4 className="text-sm font-semibold text-[#1a0533] mt-2 mb-1">{title}</h4>
              <p className="text-xs text-purple-900/50 leading-relaxed">{desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── CTA ───────────────────────────────────────────────────────── */}
      <section className="max-w-5xl mx-auto px-4 sm:px-6 py-16 pb-24">
        <div className="bg-gradient-to-br from-purple-600 to-violet-700 rounded-3xl px-8 py-14 text-center space-y-5 shadow-xl shadow-purple-200">
          <h2 className="text-3xl font-bold text-white">Ready to own your AI?</h2>
          <p className="text-purple-100 max-w-md mx-auto text-sm leading-relaxed">
            Deploy your Telegram bot in under 5 minutes, or connect your wallet
            to explore the memory dashboard.
          </p>
          <div className="flex items-center justify-center gap-3 flex-wrap pt-2">
            <Link
              href="/deploy"
              className="flex items-center gap-2 px-7 py-3 rounded-xl text-sm font-semibold bg-white text-purple-700 hover:bg-purple-50 transition-all"
            >
              Deploy Bot <ArrowRight className="w-4 h-4" />
            </Link>
            {isConnected ? (
              <Link
                href="/memory"
                className="flex items-center gap-2 px-7 py-3 rounded-xl text-sm font-semibold border border-white/40 text-white hover:bg-white/10 transition-all"
              >
                Memory Explorer <ChevronRight className="w-4 h-4" />
              </Link>
            ) : (
              <button
                onClick={() => connect({ connector: injected() })}
                disabled={isPending}
                className="flex items-center gap-2 px-7 py-3 rounded-xl text-sm font-semibold border border-white/40 text-white hover:bg-white/10 transition-all disabled:opacity-50"
              >
                {isPending ? "Connecting…" : "Connect Wallet"}{" "}
                <ChevronRight className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}
