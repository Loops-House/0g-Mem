"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useAccount } from "wagmi";
import { useRouter } from "next/navigation";
import {
  Send,
  PanelRightClose,
  PanelRightOpen,
  Brain,
  Settings,
  Loader2,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import ChatSidebar from "@/components/ChatSidebar";
import ChatMessage from "@/components/ChatMessage";
import MemoryIndicator from "@/components/MemoryIndicator";
import ToolCard from "@/components/ToolCard";
import { AgentWSClient, type InboundMsg, type MemoryEntry } from "@/lib/websocket";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ─── Types ────────────────────────────────────────────────────────────────────

interface Message {
  id: string;
  role: "user" | "assistant";
  text: string;
  timestamp: number;
  memories?: MemoryEntry[];
  tools?: ToolCardData[];
  error?: string;
}

interface ToolCardData {
  id: string;
  tool: string;
  input: string;
  result?: string;
  status: "pending" | "done" | "error";
  latency_ms?: number;
}

interface Conversation {
  id: string;
  messages: Message[];
  mode: "assistant" | "coding" | "research";
  memoryCount: number;
  lastSession: string;
}

type AgentMode = "assistant" | "coding" | "research";

// ─── Helpers ─────────────────────────────────────────────────────────────────

function makeMsgId() {
  return Math.random().toString(36).slice(2);
}

function getModeLabel(mode: AgentMode): string {
  return { assistant: "Assistant", coding: "Coding", research: "Research" }[mode];
}

function makeSessionId(wallet: string): string {
  const hour = Math.floor(Date.now() / 3600000);
  return `${wallet}_${hour}`;
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function ChatPage() {
  const { address, isConnected } = useAccount();
  const router = useRouter();
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // ── Auth guard ─────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!isConnected) router.replace("/");
  }, [isConnected, router]);

  // ── Conversation state ──────────────────────────────────────────────────────
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [conversations, setConversations] = useState<Record<string, Conversation>>({});
  const [activeConversation, setActiveConversation] = useState<Conversation | null>(null);

  // ── Agent state ─────────────────────────────────────────────────────────────
  const [inputText, setInputText] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [wsClient, setWsClient] = useState<AgentWSClient | null>(null);

  // ── UI state ────────────────────────────────────────────────────────────────
  const [rightPanelOpen, setRightPanelOpen] = useState(false);
  const [mode, setMode] = useState<AgentMode>("assistant");

  // ── Pending tool cards (rendered as they arrive) ───────────────────────────
  const [toolCards, setToolCards] = useState<Record<string, ToolCardData>>({});

  // ── Auto-scroll ─────────────────────────────────────────────────────────────
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [activeConversation?.messages, toolCards]);

  // ── Connect WebSocket ────────────────────────────────────────────────────────
  const connectWS = useCallback(
    (userId: string, sessionId: string, agentMode: AgentMode) => {
      const client = new AgentWSClient(API_URL, userId, sessionId, agentMode);

      client.onMessage((msg: InboundMsg) => {
        switch (msg.type) {
          case "memory_retrieved": {
            // Update the last assistant message with retrieved memories
            setConversations((prev) => {
              if (!activeConversationId) return prev;
              const conv = prev[activeConversationId];
              if (!conv || conv.messages.length === 0) return prev;
              const msgs = [...conv.messages];
              const last = { ...msgs[msgs.length - 1] };
              if (last.role === "assistant") {
                last.memories = msg.memories;
              }
              msgs[msgs.length - 1] = last;
              return { ...prev, [activeConversationId]: { ...conv, messages: msgs } };
            });
            break;
          }

          case "tool_call": {
            const cardId = makeMsgId();
            setToolCards((prev) => ({
              ...prev,
              [cardId]: {
                id: cardId,
                tool: msg.tool,
                input: msg.input,
                result: msg.result ?? undefined,
                status: msg.status,
              },
            }));
            break;
          }

          case "response": {
            // Final response
            setConversations((prev) => {
              if (!activeConversationId) return prev;
              const conv = prev[activeConversationId];
              const msgs = [...conv.messages];
              const last = { ...msgs[msgs.length - 1] };
              if (last.role === "assistant") {
                last.text = msg.text;
                last.memories = last.memories ?? [];
              }
              msgs[msgs.length - 1] = last;
              return {
                ...prev,
                [activeConversationId]: {
                  ...conv,
                  messages: msgs,
                  memoryCount: conv.memoryCount + msg.memories_written,
                },
              };
            });
            setIsLoading(false);
            setToolCards({});
            break;
          }

          case "error": {
            setConversations((prev) => {
              if (!activeConversationId) return prev;
              const conv = prev[activeConversationId];
              const msgs = [...conv.messages];
              if (msgs.length > 0 && msgs[msgs.length - 1].role === "assistant") {
                msgs[msgs.length - 1] = {
                  ...msgs[msgs.length - 1],
                  error: msg.message,
                };
              }
              return { ...prev, [activeConversationId]: { ...conv, messages: msgs } };
            });
            setIsLoading(false);
            setToolCards({});
            break;
          }
        }
      });

      client.connect().catch((err) => {
        console.error("WS connect error:", err);
        setIsLoading(false);
      });

      setWsClient(client);
      return client;
    },
    [activeConversationId]
  );

  // ── Send message ─────────────────────────────────────────────────────────────
  const sendMessage = useCallback(
    async (text: string) => {
      if (!text.trim() || !address) return;

      const sessionId = makeSessionId(address);
      const convId = activeConversationId ?? sessionId;
      const now = Math.floor(Date.now() / 1000);

      // Create or update conversation
      const newMessage: Message = {
        id: makeMsgId(),
        role: "user",
        text,
        timestamp: now,
      };

      const placeholderAssistantMsg: Message = {
        id: makeMsgId(),
        role: "assistant",
        text: "",
        timestamp: now,
      };

      setConversations((prev) => {
        const existing = prev[convId];
        if (existing) {
          return {
            ...prev,
            [convId]: {
              ...existing,
              messages: [...existing.messages, newMessage, placeholderAssistantMsg],
            },
          };
        }
        return {
          ...prev,
          [convId]: {
            id: convId,
            messages: [newMessage, placeholderAssistantMsg],
            mode,
            memoryCount: 0,
            lastSession: "just now",
          },
        };
      });

      setActiveConversationId(convId);
      setActiveConversation(
        (prev) =>
          prev
            ? { ...prev, messages: [...prev.messages, newMessage, placeholderAssistantMsg] }
            : {
                id: convId,
                messages: [newMessage, placeholderAssistantMsg],
                mode,
                memoryCount: 0,
                lastSession: "just now",
              }
      );
      setIsLoading(true);
      setInputText("");
      setToolCards({});

      // Connect WS if needed
      let client = wsClient;
      if (!client) {
        client = connectWS(address, sessionId, mode);
      } else {
        // Update mode on WS client
        client.mode = mode;
      }

      client.send(text);
    },
    [address, activeConversationId, mode, wsClient, connectWS]
  );

  // ── Handle input submit ──────────────────────────────────────────────────────
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    sendMessage(inputText);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(inputText);
    }
  };

  // ── New conversation ─────────────────────────────────────────────────────────
  const handleNewConversation = () => {
    wsClient?.end();
    setWsClient(null);
    setActiveConversationId(null);
    setActiveConversation(null);
    setToolCards({});
    setIsLoading(false);
    inputRef.current?.focus();
  };

  // ── Switch conversation ──────────────────────────────────────────────────────
  const handleSelectConversation = (id: string) => {
    const conv = conversations[id];
    if (!conv) return;
    setActiveConversationId(id);
    setActiveConversation(conv);
    setMode(conv.mode);
  };

  // ── Current conversation reactive sync ───────────────────────────────────────
  useEffect(() => {
    if (activeConversationId) {
      setActiveConversation(conversations[activeConversationId] ?? null);
    }
  }, [conversations, activeConversationId]);

  // ── Derived state ────────────────────────────────────────────────────────────
  const messages = activeConversation?.messages ?? [];
  const lastAssistantMsg = messages.length > 0 ? [...messages].reverse().find((m) => m.role === "assistant") : null;
  const memories = lastAssistantMsg?.memories ?? [];
  const memoryCount = activeConversation?.memoryCount ?? 0;

  if (!isConnected || !address) return null;

  return (
    <div className="flex h-[calc(100vh-4rem)] overflow-hidden">
      {/* ── Left sidebar ─────────────────────────────────────────────────── */}
      <ChatSidebar
        activeConversationId={activeConversationId ?? undefined}
        onSelectConversation={handleSelectConversation}
        onNewConversation={handleNewConversation}
      />

      {/* ── Main chat area ───────────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-3 border-b border-border bg-surface/80 backdrop-blur-sm">
          <div className="flex items-center gap-3">
            <h2 className="text-sm font-semibold text-white">
              {activeConversation
                ? getModeLabel(activeConversation.mode)
                : "New conversation"}
            </h2>
            {memoryCount > 0 && (
              <span className="flex items-center gap-1 text-xs text-accent bg-accent/10 border border-accent/20 px-2 py-0.5 rounded-full">
                <Brain className="w-3 h-3" />
                {memoryCount} memories written
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            {/* Mode selector */}
            <div className="flex items-center bg-surface-raised border border-border rounded-lg p-0.5 gap-0.5">
              {(["assistant", "coding", "research"] as AgentMode[]).map((m) => (
                <button
                  key={m}
                  onClick={() => setMode(m)}
                  className={cn(
                    "px-2.5 py-1 rounded-md text-xs font-medium transition-colors",
                    mode === m
                      ? "bg-accent/20 text-accent border border-accent/30"
                      : "text-muted hover:text-white"
                  )}
                >
                  {getModeLabel(m)}
                </button>
              ))}
            </div>

            {/* Right panel toggle */}
            <button
              onClick={() => setRightPanelOpen((p) => !p)}
              className={cn(
                "p-1.5 rounded-lg transition-colors",
                rightPanelOpen
                  ? "bg-accent/10 text-accent"
                  : "text-muted hover:text-white hover:bg-surface-raised"
              )}
              title="Toggle memory panel"
            >
              {rightPanelOpen ? (
                <PanelRightClose className="w-4 h-4" />
              ) : (
                <PanelRightOpen className="w-4 h-4" />
              )}
            </button>
          </div>
        </div>

        {/* Memory context bar */}
        {memories.length > 0 && (
          <div className="px-6 py-2 bg-surface/50 border-b border-border">
            <MemoryIndicator memories={memories} count={memories.length} />
          </div>
        )}

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="w-14 h-14 rounded-2xl bg-accent/10 border border-accent/20 flex items-center justify-center mb-4">
                <Brain className="w-7 h-7 text-accent" />
              </div>
              <h3 className="text-base font-semibold text-white mb-1">
                {mode === "assistant"
                  ? "Talk to your agent"
                  : mode === "coding"
                  ? "Start coding"
                  : "Start researching"}
              </h3>
              <p className="text-sm text-muted max-w-xs">
                {mode === "assistant"
                  ? "Your preferences, context, and history are loaded from memory automatically."
                  : mode === "coding"
                  ? "I know your stack, conventions, and current projects from memory."
                  : "I'll connect your research to everything you've looked into before."}
              </p>
            </div>
          )}

          {messages.map((msg) => (
            <div key={msg.id}>
              <ChatMessage
                role={msg.role}
                text={msg.text}
                timestamp={msg.timestamp}
              />
              {msg.error && (
                <p className="mt-1 text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
                  Error: {msg.error}
                </p>
              )}
            </div>
          ))}

          {/* Pending tool cards */}
          {Object.values(toolCards).map((card) => (
            <ToolCard key={card.id} {...card} />
          ))}

          {isLoading && (
            <div className="flex items-center gap-2 text-muted text-sm">
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Thinking...</span>
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Input bar */}
        <div className="px-6 py-4 border-t border-border bg-surface/80 backdrop-blur-sm">
          <form onSubmit={handleSubmit} className="flex items-end gap-3">
            <textarea
              ref={inputRef}
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={
                mode === "coding"
                  ? "What are you working on?"
                  : mode === "research"
                  ? "What are you researching?"
                  : "Message your agent..."
              }
              rows={1}
              disabled={isLoading}
              className={cn(
                "flex-1 resize-none rounded-xl px-4 py-3 text-sm",
                "bg-surface-raised border border-border",
                "text-white placeholder:text-muted",
                "focus:outline-none focus:border-accent transition-colors",
                "disabled:opacity-50"
              )}
              style={{ maxHeight: "160px", minHeight: "48px" }}
            />
            <button
              type="submit"
              disabled={!inputText.trim() || isLoading}
              className={cn(
                "flex-shrink-0 w-10 h-10 rounded-xl flex items-center justify-center",
                "bg-accent hover:bg-accent-hover text-white",
                "disabled:opacity-40 disabled:cursor-not-allowed",
                "transition-colors"
              )}
            >
              {isLoading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
            </button>
          </form>
          <p className="text-[10px] text-muted mt-1.5 text-center">
            {address && `Signed in as ${address.slice(0, 10)}...`} &middot; Same agent, same memory as Telegram
          </p>
        </div>
      </div>

      {/* ── Right panel: memory context ──────────────────────────────────── */}
      {rightPanelOpen && (
        <div className="w-72 border-l border-border bg-surface flex flex-col animate-fade-in">
          <div className="flex items-center justify-between px-4 py-3 border-b border-border">
            <h3 className="text-sm font-semibold text-white flex items-center gap-1.5">
              <Brain className="w-4 h-4 text-accent" />
              Memory
            </h3>
            <button
              onClick={() => setRightPanelOpen(false)}
              className="p-1 text-muted hover:text-white transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {/* Summary */}
            <div className="bg-surface-raised border border-border rounded-xl p-3">
              <p className="text-xs text-muted mb-2">What I know about you</p>
              {memories.length > 0 ? (
                <div className="space-y-1.5">
                  {Object.entries(
                    memories.reduce<Record<string, MemoryEntry[]>>((acc, m) => {
                      const t = m.memory_type;
                      if (!acc[t]) acc[t] = [];
                      acc[t].push(m);
                      return acc;
                    }, {})
                  ).map(([type, mems]) => (
                    <div key={type}>
                      <p className="text-[10px] text-muted uppercase tracking-wider font-medium mb-1">
                        {type}
                      </p>
                      {mems.slice(0, 2).map((m) => (
                        <p key={m.blob_id} className="text-xs text-white/70 line-clamp-2">
                          {m.text}
                        </p>
                      ))}
                      {mems.length > 2 && (
                        <p className="text-[10px] text-accent">+{mems.length - 2} more</p>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-muted italic">
                  No memories loaded yet. Start a conversation to build context.
                </p>
              )}
            </div>

            {/* Quick stats */}
            {activeConversation && (
              <div className="grid grid-cols-2 gap-2">
                <StatPill label="Messages" value={String(messages.length)} />
                <StatPill label="Memories" value={String(memoryCount)} />
              </div>
            )}

            {/* Sessions */}
            <div>
              <p className="text-[10px] text-muted uppercase tracking-wider font-medium mb-2">
                Recent sessions
              </p>
              <div className="space-y-1">
                {Object.values(conversations)
                  .slice(0, 3)
                  .map((conv) => (
                    <button
                      key={conv.id}
                      onClick={() => handleSelectConversation(conv.id)}
                      className={cn(
                        "w-full text-left px-3 py-2 rounded-lg text-xs transition-colors",
                        "hover:bg-surface-raised border border-transparent",
                        conv.id === activeConversationId
                          ? "bg-accent/10 border-accent/20"
                          : ""
                      )}
                    >
                      <p className="text-white/70 line-clamp-1">{conv.id.split("_")[1] ?? conv.id}</p>
                      <p className="text-muted">{conv.messages.length} messages &middot; {conv.mode}</p>
                    </button>
                  ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Stat Pill ────────────────────────────────────────────────────────────────

function StatPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-surface-raised border border-border rounded-xl px-3 py-2 text-center">
      <p className="text-lg font-semibold text-white">{value}</p>
      <p className="text-[10px] text-muted">{label}</p>
    </div>
  );
}
