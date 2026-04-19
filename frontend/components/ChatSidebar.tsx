"use client";

import { useEffect, useState } from "react";
import { Search, Pin, Plus, MessageSquare, Clock } from "lucide-react";
import { cn } from "@/lib/utils";

interface Conversation {
  id: string;
  preview: string;
  mode: string;
  updated_at: number;
  pinned?: boolean;
}

// Mock conversation history — in production this would be stored on 0g Storage
const MOCK_CONVERSATIONS: Conversation[] = [
  {
    id: "0xabc123_1745000000",
    preview: "How do I structure the auth module for the Postgres migration?",
    mode: "coding",
    updated_at: Date.now() / 1000 - 3600,
    pinned: true,
  },
  {
    id: "0xabc123_1744900000",
    preview: "What's the latest price of Ethereum?",
    mode: "assistant",
    updated_at: Date.now() / 1000 - 86400,
  },
  {
    id: "0xabc123_1744800000",
    preview: "Research: Layer 2 rollup comparison for my fintech app",
    mode: "research",
    updated_at: Date.now() / 1000 - 172800,
  },
];

function formatRelativeTime(unixSeconds: number): string {
  const now = Date.now() / 1000;
  const diff = now - unixSeconds;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`;
  return new Date(unixSeconds * 1000).toLocaleDateString();
}

const MODE_COLORS: Record<string, string> = {
  assistant: "bg-purple-500/20 text-purple-400",
  coding: "bg-blue-500/20 text-blue-400",
  research: "bg-green-500/20 text-green-400",
};

const MODE_ICONS: Record<string, string> = {
  assistant: "💬",
  coding: "💻",
  research: "🔬",
};

interface ChatSidebarProps {
  activeConversationId?: string;
  onSelectConversation: (id: string) => void;
  onNewConversation: () => void;
}

export default function ChatSidebar({
  activeConversationId,
  onSelectConversation,
  onNewConversation,
}: ChatSidebarProps) {
  const [conversations, setConversations] = useState<Conversation[]>(MOCK_CONVERSATIONS);
  const [search, setSearch] = useState("");
  const [filterMode, setFilterMode] = useState<string | null>(null);

  const filtered = conversations
    .filter((c) => {
      if (filterMode && c.mode !== filterMode) return false;
      if (search && !c.preview.toLowerCase().includes(search.toLowerCase())) return false;
      return true;
    })
    .sort((a, b) => {
      if (a.pinned && !b.pinned) return -1;
      if (!a.pinned && b.pinned) return 1;
      return b.updated_at - a.updated_at;
    });

  const pinned = filtered.filter((c) => c.pinned);
  const recent = filtered.filter((c) => !c.pinned);

  return (
    <div className="flex flex-col h-full w-64 border-r border-border bg-surface">
      {/* Search */}
      <div className="px-3 pt-3 pb-2">
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted" />
          <input
            type="text"
            placeholder="Search conversations..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className={cn(
              "w-full pl-8 pr-3 py-2 rounded-lg text-xs",
              "bg-surface-raised border border-border",
              "text-white placeholder:text-muted",
              "focus:outline-none focus:border-accent transition-colors"
            )}
          />
        </div>
      </div>

      {/* Mode filter */}
      <div className="px-3 pb-2 flex gap-1">
        {[null, "assistant", "coding", "research"].map((mode) => (
          <button
            key={mode ?? "all"}
            onClick={() => setFilterMode(mode)}
            className={cn(
              "flex-1 py-1 rounded-md text-[10px] font-medium transition-colors",
              filterMode === mode
                ? "bg-accent/20 text-accent border border-accent/30"
                : "text-muted hover:text-white hover:bg-surface-raised"
            )}
          >
            {mode ?? "All"}
          </button>
        ))}
      </div>

      {/* New conversation */}
      <div className="px-3 pb-2">
        <button
          onClick={onNewConversation}
          className={cn(
            "w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium",
            "bg-accent/10 border border-accent/20 text-accent",
            "hover:bg-accent/20 transition-colors"
          )}
        >
          <Plus className="w-3.5 h-3.5" />
          New conversation
        </button>
      </div>

      {/* Conversation list */}
      <div className="flex-1 overflow-y-auto px-2 space-y-0.5 pb-4">
        {/* Pinned */}
        {pinned.length > 0 && (
          <div className="pt-2">
            <p className="px-2 mb-1 text-[10px] text-muted uppercase tracking-wider font-semibold flex items-center gap-1">
              <Pin className="w-2.5 h-2.5" /> Pinned
            </p>
            {pinned.map((conv) => (
              <ConversationItem
                key={conv.id}
                conversation={conv}
                isActive={conv.id === activeConversationId}
                onSelect={onSelectConversation}
              />
            ))}
          </div>
        )}

        {/* Recent */}
        {recent.length > 0 && (
          <div className="pt-2">
            {pinned.length > 0 && (
              <p className="px-2 mb-1 text-[10px] text-muted uppercase tracking-wider font-semibold flex items-center gap-1">
                <Clock className="w-2.5 h-2.5" /> Recent
              </p>
            )}
            {recent.map((conv) => (
              <ConversationItem
                key={conv.id}
                conversation={conv}
                isActive={conv.id === activeConversationId}
                onSelect={onSelectConversation}
              />
            ))}
          </div>
        )}

        {filtered.length === 0 && (
          <div className="flex flex-col items-center justify-center py-8 text-center px-4">
            <MessageSquare className="w-6 h-6 text-muted mb-2" />
            <p className="text-xs text-muted">No conversations found.</p>
          </div>
        )}
      </div>
    </div>
  );
}

function ConversationItem({
  conversation,
  isActive,
  onSelect,
}: {
  conversation: Conversation;
  isActive: boolean;
  onSelect: (id: string) => void;
}) {
  const color = MODE_COLORS[conversation.mode] ?? MODE_COLORS.assistant;

  return (
    <button
      onClick={() => onSelect(conversation.id)}
      className={cn(
        "w-full text-left px-2 py-2 rounded-lg transition-colors mb-0.5",
        isActive
          ? "bg-accent/15 border border-accent/20"
          : "hover:bg-surface-raised border border-transparent"
      )}
    >
      <div className="flex items-center gap-1.5 mb-0.5">
        <span className="text-[10px]">{MODE_ICONS[conversation.mode]}</span>
        <span className={cn("text-[10px] px-1.5 py-0.5 rounded border font-medium", color)}>
          {conversation.mode}
        </span>
        <span className="text-[10px] text-muted ml-auto flex-shrink-0">
          {formatRelativeTime(conversation.updated_at)}
        </span>
      </div>
      <p className="text-xs text-white/70 line-clamp-2 leading-snug">
        {conversation.preview}
      </p>
    </button>
  );
}
