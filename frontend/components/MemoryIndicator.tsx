"use client";

import { useState } from "react";
import { Brain, ChevronDown, ChevronUp } from "lucide-react";
import { cn } from "@/lib/utils";
import type { MemoryEntry } from "@/lib/websocket";

interface MemoryIndicatorProps {
  memories: MemoryEntry[];
  count: number;
}

const MEMORY_TYPE_LABELS: Record<string, string> = {
  episodic: "Event",
  semantic: "Fact",
  procedural: "Habit",
  working: "Context",
};

const MEMORY_TYPE_COLORS: Record<string, string> = {
  episodic: "text-purple-400 bg-purple-400/10 border-purple-400/20",
  semantic: "text-blue-400 bg-blue-400/10 border-blue-400/20",
  procedural: "text-green-400 bg-green-400/10 border-green-400/20",
  working: "text-yellow-400 bg-yellow-400/10 border-yellow-400/20",
};

export default function MemoryIndicator({ memories, count }: MemoryIndicatorProps) {
  const [expanded, setExpanded] = useState(false);

  if (count === 0) return null;

  return (
    <div className="animate-fade-in">
      {/* Collapsed bar */}
      <button
        onClick={() => setExpanded((e) => !e)}
        className={cn(
          "flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs",
          "bg-accent/10 border border-accent/20 text-accent",
          "hover:bg-accent/20 transition-colors cursor-pointer"
        )}
      >
        <Brain className="w-3 h-3" />
        <span>Using {count} memory{count !== 1 ? "ies" : ""}</span>
        {expanded ? (
          <ChevronUp className="w-3 h-3" />
        ) : (
          <ChevronDown className="w-3 h-3" />
        )}
      </button>

      {/* Expanded memory cards */}
      {expanded && memories.length > 0 && (
        <div className="mt-2 space-y-1.5 animate-slide-up">
          {memories.map((mem, i) => {
            const color = MEMORY_TYPE_COLORS[mem.memory_type] ?? MEMORY_TYPE_COLORS.episodic;
            return (
              <div
                key={mem.blob_id ?? i}
                className={cn(
                  "flex items-start gap-2 rounded-lg border px-3 py-2 text-left",
                  "bg-surface border-border",
                  color
                )}
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5 mb-0.5">
                    <span
                      className={cn(
                        "text-[10px] font-medium uppercase tracking-wide px-1.5 py-0.5 rounded border",
                        color
                      )}
                    >
                      {MEMORY_TYPE_LABELS[mem.memory_type] ?? mem.memory_type}
                    </span>
                    <span className="text-[10px] text-muted">
                      {Math.round((mem.score ?? 0) * 100)}% match
                    </span>
                  </div>
                  <p className="text-xs text-white/80 leading-relaxed line-clamp-2">
                    {mem.text}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
