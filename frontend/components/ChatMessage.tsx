"use client";

import { useMemo } from "react";
import { cn } from "@/lib/utils";

interface ChatMessageProps {
  role: "user" | "assistant";
  text: string;
  timestamp?: number;
  className?: string;
}

export default function ChatMessage({ role, text, timestamp, className }: ChatMessageProps) {
  const isUser = role === "user";

  const formattedTime = useMemo(() => {
    if (!timestamp) return null;
    return new Date(timestamp * 1000).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
  }, [timestamp]);

  return (
    <div
      className={cn(
        "flex",
        isUser ? "justify-end" : "justify-start",
        className
      )}
    >
      <div
        className={cn(
          "max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-relaxed animate-fade-in",
          isUser
            ? "bg-accent text-white rounded-br-md"
            : "bg-surface-raised border border-border text-white rounded-bl-md"
        )}
      >
        {/* Render text with basic markdown-like formatting */}
        <p className="whitespace-pre-wrap">{text}</p>

        {formattedTime && (
          <p
            className={cn(
              "text-[10px] mt-1.5 opacity-60",
              isUser ? "text-white/70" : "text-muted"
            )}
          >
            {formattedTime}
          </p>
        )}
      </div>
    </div>
  );
}
