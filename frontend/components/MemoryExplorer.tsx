"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Brain,
  RefreshCw,
  Loader2,
  Filter,
  ChevronDown,
  Search,
  Shield,
  Clock,
  AlertTriangle,
} from "lucide-react";
import { getMemoryState, queryMemory } from "@/lib/api";
import { getAuthHeaders } from "@/lib/auth";
import { cn } from "@/lib/utils";

interface MemoryExplorerProps {
  agentId: string;
  refreshTrigger?: number;
}

// ─── Memory type ──────────────────────────────────────────────────────────────

type MemoryType = "all" | "episodic" | "semantic" | "procedural" | "working";

const MEMORY_TYPE_CONFIG: Record<
  Exclude<MemoryType, "all">,
  { label: string; color: string; bg: string; icon: string }
> = {
  episodic: {
    label: "Events",
    color: "text-purple-400",
    bg: "bg-purple-500/10",
    icon: "💬",
  },
  semantic: {
    label: "Facts",
    color: "text-blue-400",
    bg: "bg-blue-500/10",
    icon: "🧠",
  },
  procedural: {
    label: "Habits",
    color: "text-green-400",
    bg: "bg-green-500/10",
    icon: "⚙️",
  },
  working: {
    label: "Context",
    color: "text-yellow-400",
    bg: "bg-yellow-500/10",
    icon: "🎯",
  },
};

// ─── Memory item ─────────────────────────────────────────────────────────────

interface MemoryItem {
  blob_id: string;
  text: string;
  memory_type: string;
  score: number;
  timestamp: number;
}

// ─── Summary generator ───────────────────────────────────────────────────────

function generateMemorySummary(memories: MemoryItem[]): string {
  if (memories.length === 0) {
    return "I don't know much about you yet. Start chatting to build context!";
  }

  const byType = memories.reduce<Record<string, MemoryItem[]>>((acc, m) => {
    if (!acc[m.memory_type]) acc[m.memory_type] = [];
    acc[m.memory_type].push(m);
    return acc;
  }, {});

  const facts = (byType["semantic"] ?? []).slice(0, 4);
  const procedures = (byType["procedural"] ?? []).slice(0, 3);
  const context = (byType["working"] ?? []).slice(0, 2);

  const parts: string[] = [];

  if (facts.length > 0) {
    const factTexts = facts.map((f) => f.text).join("; ");
    parts.push(`I know: ${factTexts}`);
  }
  if (procedures.length > 0) {
    const procTexts = procedures.map((p) => p.text).join("; ");
    parts.push(`You prefer: ${procTexts}`);
  }
  if (context.length > 0) {
    const ctxTexts = context.map((c) => c.text).join("; ");
    parts.push(`Currently working on: ${ctxTexts}`);
  }

  return parts.join(" | ") || "I know a few things about you — check the memories below.";
}

// ─── Main component ─────────────────────────────────────────────────────────

export default function MemoryExplorer({
  agentId,
  refreshTrigger,
}: MemoryExplorerProps) {
  const [memories, setMemories] = useState<MemoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterType, setFilterType] = useState<MemoryType>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [showSummary, setShowSummary] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const authHeaders = await getAuthHeaders(agentId);

      // Get all memories via a broad query — in production, the memory
      // service's session index would be used instead
      const res = await queryMemory(agentId, "everything about me", 50, authHeaders);

      // Parse raw results — best effort
      const items: MemoryItem[] = res.results.map((text: string, i: number) => ({
        blob_id: res.proof.blob_ids[i] ?? `idx-${i}`,
        text,
        memory_type: "semantic", // Default — typed storage comes with session layer
        score: res.proof.scores?.[i] ?? 0,
        timestamp: Date.now() / 1000,
      }));

      setMemories(items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load memories.");
    } finally {
      setLoading(false);
    }
  }, [agentId]);

  useEffect(() => {
    load();
  }, [load, refreshTrigger]);

  // ── Filter ──────────────────────────────────────────────────────────────────

  const filtered = memories.filter((m) => {
    if (filterType !== "all" && m.memory_type !== filterType) return false;
    if (
      searchQuery &&
      !m.text.toLowerCase().includes(searchQuery.toLowerCase())
    )
      return false;
    return true;
  });

  // ── Counts ─────────────────────────────────────────────────────────────────

  const counts = memories.reduce<Record<MemoryType, number>>(
    (acc, m) => {
      const t = m.memory_type as MemoryType;
      if (t in acc) acc[t]++;
      return acc;
    },
    { all: memories.length, episodic: 0, semantic: 0, procedural: 0, working: 0 }
  );

  // ── Summary ────────────────────────────────────────────────────────────────

  const summary = generateMemorySummary(memories);
  const staleThreshold = 45 * 24 * 3600; // 45 days
  const staleMemories = memories.filter(
    (m) => Date.now() / 1000 - m.timestamp > staleThreshold
  );

  return (
    <div className="space-y-4">
      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Brain className="w-4 h-4 text-accent" />
          <h2 className="text-sm font-semibold text-white">Memory Explorer</h2>
          <span className="text-xs text-muted bg-surface-raised border border-border px-2 py-0.5 rounded-full">
            {counts.all} total
          </span>
        </div>
        <button
          onClick={load}
          disabled={loading}
          className="text-muted hover:text-white transition-colors disabled:opacity-50"
        >
          <RefreshCw className={cn("w-4 h-4", loading && "animate-spin")} />
        </button>
      </div>

      {/* ── Summary banner ──────────────────────────────────────────────────── */}
      {showSummary && (
        <button
          onClick={() => setShowSummary(false)}
          className="w-full text-left bg-accent/5 border border-accent/20 rounded-xl px-4 py-3 hover:bg-accent/10 transition-colors"
        >
          <div className="flex items-center gap-2 mb-1.5">
            <Shield className="w-3.5 h-3.5 text-accent" />
            <span className="text-xs font-semibold text-accent">What the agent knows about you</span>
          </div>
          <p className="text-sm text-white/80 leading-relaxed italic">{summary}</p>
        </button>
      )}

      {/* ── Stale memory warning ─────────────────────────────────────────────── */}
      {staleMemories.length > 0 && (
        <div className="flex items-center gap-2 bg-yellow-500/10 border border-yellow-500/20 rounded-xl px-4 py-2.5">
          <AlertTriangle className="w-4 h-4 text-yellow-400 flex-shrink-0" />
          <p className="text-xs text-yellow-400">
            {staleMemories.length} stale memory/stored — tap to review and clean up.
          </p>
        </div>
      )}

      {/* ── Stats row ───────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-4 gap-2">
        {(Object.keys(MEMORY_TYPE_CONFIG) as Exclude<MemoryType, "all">[]).map(
          (t) => {
            const cfg = MEMORY_TYPE_CONFIG[t];
            const isActive = filterType === t;
            return (
              <button
                key={t}
                onClick={() => setFilterType(isActive ? "all" : t)}
                className={cn(
                  "flex flex-col items-center gap-0.5 py-2 rounded-xl border transition-colors",
                  isActive
                    ? `${cfg.bg} border-current/30`
                    : "bg-surface-raised border-border hover:border-border/80"
                )}
              >
                <span className="text-base">{cfg.icon}</span>
                <span className={cn("text-[10px] font-medium", isActive ? cfg.color : "text-muted")}>
                  {counts[t]}
                </span>
                <span className="text-[9px] text-muted uppercase tracking-wider">
                  {cfg.label}
                </span>
              </button>
            );
          }
        )}
      </div>

      {/* ── Search ──────────────────────────────────────────────────────────── */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted" />
        <input
          type="text"
          placeholder="Search memories…"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className={cn(
            "w-full pl-9 pr-3 py-2.5 rounded-xl text-xs",
            "bg-surface-raised border border-border",
            "text-white placeholder:text-muted",
            "focus:outline-none focus:border-accent transition-colors"
          )}
        />
      </div>

      {/* ── Error ───────────────────────────────────────────────────────────── */}
      {error && (
        <p className="text-xs text-error bg-error/10 border border-error/20 rounded-lg px-3 py-2">
          {error}
        </p>
      )}

      {/* ── Loading ─────────────────────────────────────────────────────────── */}
      {loading && !memories.length && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-5 h-5 animate-spin text-muted" />
        </div>
      )}

      {/* ── Memory list ─────────────────────────────────────────────────────── */}
      {!loading && filtered.length === 0 && (
        <div className="text-center py-10">
          <Brain className="w-8 h-8 text-muted mx-auto mb-2" />
          <p className="text-sm text-muted">
            {filterType !== "all"
              ? `No ${MEMORY_TYPE_CONFIG[filterType as Exclude<MemoryType, "all">].label.toLowerCase()} memories yet.`
              : "No memories yet. Start chatting to build context!"}
          </p>
        </div>
      )}

      {!loading && filtered.length > 0 && (
        <div className="space-y-2 max-h-96 overflow-y-auto pr-1">
          {filtered.map((mem, i) => {
            const cfg = MEMORY_TYPE_CONFIG[mem.memory_type as Exclude<MemoryType, "all">] ?? MEMORY_TYPE_CONFIG.episodic;
            const isStale = Date.now() / 1000 - mem.timestamp > staleThreshold;

            return (
              <div
                key={mem.blob_id ?? i}
                className={cn(
                  "rounded-xl border px-4 py-3 animate-fade-in",
                  "bg-surface-raised border-border",
                  isStale && "opacity-60 border-yellow-500/20"
                )}
              >
                <div className="flex items-center gap-2 mb-1.5">
                  <span className="text-sm">{cfg.icon}</span>
                  <span
                    className={cn(
                      "text-[10px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded border",
                      cfg.color,
                      cfg.bg,
                      `border-current/30`
                    )}
                  >
                    {cfg.label}
                  </span>
                  {isStale && (
                    <span className="text-[10px] text-yellow-400 flex items-center gap-0.5">
                      <Clock className="w-2.5 h-2.5" /> Stale
                    </span>
                  )}
                  {mem.score > 0 && (
                    <span className="text-[10px] text-muted ml-auto">
                      {Math.round(mem.score * 100)}% match
                    </span>
                  )}
                </div>
                <p className="text-xs text-white/80 leading-relaxed">{mem.text}</p>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
