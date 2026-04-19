"use client";

import { useState } from "react";
import { Terminal, ChevronDown, ChevronUp, CheckCircle, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";

interface ToolCardProps {
  tool: string;
  input: string;
  result: string | null;
  status: "pending" | "done" | "error";
  latency_ms?: number;
}

const TOOL_ICONS: Record<string, string> = {
  web_search: "🌐",
  tavily_search: "🌐",
  coding: "💻",
};

export default function ToolCard({ tool, input, result, status, latency_ms }: ToolCardProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      className={cn(
        "rounded-xl border text-sm animate-slide-up overflow-hidden",
        status === "pending"
          ? "bg-yellow-500/5 border-yellow-500/20"
          : status === "error"
          ? "bg-red-500/5 border-red-500/20"
          : "bg-surface border-border"
      )}
    >
      {/* Header — always visible */}
      <button
        onClick={() => setExpanded((e) => !e)}
        className="w-full flex items-center gap-2 px-4 py-2.5 text-left hover:bg-white/5 transition-colors cursor-pointer"
      >
        <span className="text-base">{TOOL_ICONS[tool] ?? "🔧"}</span>
        <span className="font-mono text-xs text-white/70 flex-1">{tool}</span>

        {status === "pending" && (
          <span className="flex items-center gap-1 text-xs text-yellow-400">
            <span className="w-1.5 h-1.5 rounded-full bg-yellow-400 animate-pulse" />
            Running
          </span>
        )}
        {status === "done" && (
          <CheckCircle className="w-3.5 h-3.5 text-green-400" />
        )}
        {status === "error" && (
          <XCircle className="w-3.5 h-3.5 text-red-400" />
        )}

        {result && (
          expanded ? (
            <ChevronUp className="w-3.5 h-3.5 text-muted" />
          ) : (
            <ChevronDown className="w-3.5 h-3.5 text-muted" />
          )
        )}
      </button>

      {/* Expanded details */}
      {expanded && (
        <div className="px-4 pb-3 space-y-2">
          {/* Input */}
          <div>
            <p className="text-[10px] text-muted uppercase tracking-wide font-medium mb-0.5">
              Input
            </p>
            <pre className="font-mono text-xs text-white/70 bg-background rounded-lg px-3 py-2 whitespace-pre-wrap break-all">
              {input}
            </pre>
          </div>

          {/* Result */}
          {result !== null && (
            <div>
              <div className="flex items-center justify-between mb-0.5">
                <p className="text-[10px] text-muted uppercase tracking-wide font-medium">Result</p>
                {latency_ms !== undefined && (
                  <p className="text-[10px] text-muted">{latency_ms}ms</p>
                )}
              </div>
              <pre className="font-mono text-xs text-white/70 bg-background rounded-lg px-3 py-2 whitespace-pre-wrap break-all max-h-48 overflow-y-auto">
                {result}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
