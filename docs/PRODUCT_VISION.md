# 0G — The Full Product

---

## What it is

A verifiable AI agent that lives in your terminal and knows you — across every session, every machine, every tool. Powered by decentralized infrastructure so no company owns your context. You talk to it through a TUI for deep work, through Telegram for quick things on the go. Same agent. Same memory. Two front doors.

Under the hood: your own encrypted memory store on 0G, inference through 0G Compute, every execution logged to 0G DA. The agent gets smarter about you over time and you can prove exactly what it knew at any point.

---

## The Stack

```
TUI                    Telegram Bot
(deep work)            (quick, mobile)
      ↓                      ↓
      └──────────┬───────────┘
                 ↓
          Agent Runtime
         (orchestration)
          ↓        ↓         ↓
     0G Compute  0G Mem    Tools
     (thinking) (memory)  (search, code
                           execution, APIs)
                    ↓
                 0G DA
            (log everything)
```

---

## Part 1 — The Memory Layer (0G Mem)

This is the foundation. Everything else sits on top of it.

Every interaction you have with the agent writes to your memory store. Your preferences, your projects, your context, your history — all encrypted with your private key, stored on 0G decentralized infrastructure. Nobody else can read it. Not even us.

**Four memory types:**

- **Episodic** — things that happened. "User asked about auth migration on Apr 14."
- **Semantic** — things the agent knows about you. "User is building a fintech app on 0G."
- **Procedural** — how you like things done. "Always TypeScript. Never verbose explanations."
- **Working** — current task context. "Currently migrating auth module to Postgres."

**Auto-evolving:**
Memory that gets retrieved frequently gets stronger. Memory untouched for 45 days starts decaying. Periodically old episodic memories get distilled into compact semantic facts — 200 raw conversation entries compressed into 15 clean facts about you. Every evolution anchored on 0G Chain. Provable.

**Session batching:**
Not one chain transaction per memory write. One transaction per session. 50 messages = 1 chain tx at the end. Practical, not expensive.

---

## Part 2 — The Agent Runtime

The orchestration layer that wires everything together. This is what happens every time you send a message:

**Step 1 — Memory retrieval**
Before the agent thinks about your message, it pulls relevant memories from 0G Mem. Context loaded before inference starts.

**Step 2 — Inference via 0G Compute**
Your message + memory context goes to 0G Compute. Decentralized, verifiable inference.

**Step 3 — Tools if needed**
Web search, code execution, API calls. Each tool call logged.

**Step 4 — Response**
Agent responds. In the TUI this is rich — syntax-highlighted code blocks, inline diffs, tool results. In Telegram it's clean text.

**Step 5 — Memory write**
After responding, new memories written from the exchange. Batched into the session commit.

**Step 6 — DA log**
Full execution trace — input, memories retrieved, tools called, inference result, output, memories written — posted to 0G DA. Immutable, provable record of exactly what happened.

---

## Part 3 — The TUI

One binary. Type `0g`. You're in. Runs everywhere — Mac, Linux, remote server over SSH. No Electron. No browser tab. Lives right next to your code in a terminal split.

```
┌──────────────────────────────────────────────────────────────────┐
│ 0G  ·  0xAb3f...  ·  127 memories  ·  coding           [?]     │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─ Conversations ────┐  ┌─ Chat ───────────────────────────┐   │
│  │ > auth migration   │  │                                  │   │
│  │   0g mem design    │  │  You: best way to handle refresh │   │
│  │   research         │  │  tokens in this setup            │   │
│  │   daily notes      │  │                                  │   │
│  │   ...              │  │  Agent: Given your Postgres      │   │
│  │                    │  │  setup and auth migration —      │   │
│  │                    │  │  separate table with TTL index.  │   │
│  │                    │  │                                  │   │
│  │                    │  │  ╔ memories used ══════════╗    │   │
│  │                    │  │  ║ "using Postgres"        ║    │   │
│  │                    │  │  ║ "migrating auth module" ║    │   │
│  │                    │  │  ╚═════════════════════════╝    │   │
│  │                    │  │                                  │   │
│  │                    │  │  ┌──────────────────────────┐   │   │
│  │                    │  │  │ > _                      │   │   │
│  │                    │  │  └──────────────────────────┘   │   │
│  └────────────────────┘  └──────────────────────────────────┘   │
│                                                                  │
│  [tab] panels  [m] memory  [ctrl+n] new  [/] commands           │
└──────────────────────────────────────────────────────────────────┘
```

Fully keyboard driven. No mouse needed.

**Opening:**
```bash
0g               # full TUI
0g "question"    # inline answer, no TUI
0g --coding      # opens in coding mode directly
```

**Keybindings:**

| Key | Action |
|---|---|
| `tab` | Switch panels |
| `m` | Memory panel |
| `ctrl+n` | New conversation |
| `ctrl+e` | Open response in `$EDITOR` |
| `ctrl+c` | Copy last response |
| `esc` | Back / close panel |

**Slash commands:**
```
/mode coding      coding agent
/mode research    research agent
/mode assistant   general assistant
/memory           memory explorer
/checkpoint       save task state
/tools            available tools
```

**Agent modes:**

- **Coding** — knows your stack and conventions. Outputs diffs you apply directly from the TUI.
- **Research** — web search with memory of everything you've ever researched. Connects current queries to past sessions.
- **Assistant** — general. Default.
- **Custom** — your own system prompt and tools, stored on 0G, versioned and auditable.

---

## Part 4 — The Telegram Bot

Same agent. Same memory. Just a different interface.

You DM the bot. It already knows everything the TUI sessions have written. One continuous memory across both.

**What Telegram is good for:**

Quick captures — "remember I decided to use Redis for session cache." Done. In memory.

Fast lookups — "what did I decide about the token storage?" Instant.

On-the-go tasks — drafting, summarizing, quick questions while away from your machine.

Notifications — when a background task finishes, it messages you here.

**What Telegram doesn't try to do:**

No diffs. No multi-step deep work. No code execution. For those, it points you back to the TUI:

```
You: help me refactor the auth module
Bot: Better in the TUI where I can show diffs.
     Run: 0g --coding
     Full context will be ready.
```

---

## Part 5 — The Memory Panel

Hit `m` from anywhere in the TUI. Same information as a dashboard — just lives inside the terminal.

```
┌─ Memory ────────────────────────────────────────────────────────┐
│  127 memories  ·  updated 3 min ago                             │
│                                                                  │
│  What the agent knows about you:                                 │
│  "TypeScript developer building fintech on 0G. Migrating        │
│   auth to Postgres. Concise answers, no verbose comments."      │
│                                                                  │
│  ── Memories ──────────────────────────────────── [f]ilter ──  │
│                                                                  │
│  [procedural]  Always TypeScript, never Python                  │
│                Cursor · Apr 12 · retrieved 14x          [d]elete│
│                                                                  │
│  [semantic]    Building fintech app on 0G Labs                  │
│                Claude · Apr 8 · retrieved 6x            [d]elete│
│                                                                  │
│  [episodic] ⚠  Asked about React 18 migration · stale 45d      │
│                retrieved 0x                     [k]eep [d]elete │
│                                                                  │
│  [/] search    [f] filter    [esc] close                        │
└─────────────────────────────────────────────────────────────────┘
```

**Activity tab** — inside the same panel:

```
  Today
  2:41 PM  read   "typescript preferences" → 2 memories
  2:38 PM  wrote  "user migrating auth to postgres"
  9:30 AM  read   "current project context" → 3 memories

  Apr 17
  ∞  evolved → 18 episodic entries distilled to 4 semantic facts
               chain tx: 0xf3a9...                   [v]iew proof
```

**Access tab** — who has access, what scope, revoke instantly.

**Portability tab** — export, snapshot, share, delete everything.

---

## What the user actually experiences

**Day 1:** Install binary. `0g setup` — connect wallet, 5 minutes. First session, agent knows nothing.

**Week 2:** Agent has learned your stack, preferences, current projects from daily use. Conversations start mid-context. You stop re-explaining yourself.

**Month 2:** You SSH into a remote server. Type `0g`. Same agent, same memory, same context. Works exactly the same — it's just a binary.

**Month 3:** You're deep in a migration. Laptop dies. New machine. `/checkpoint restore`. Pick up exactly where you left off.

**Month 4:** Agent makes a call you disagree with. Hit `m`, go to Activity, find the session. See exactly which three memories it retrieved before giving that answer. One is stale. Delete it. Fixed.

**Month 6:** You want to try a different inference provider. Swap it in config. Memory stays. History stays. Nothing changes except the model doing the thinking.

---

## What you never have to think about

Chain transactions. Merkle proofs. DA layers. Encryption keys. Any of it.

It's all happening. But the interface is just: a terminal, a chat, a memory panel. Hit `v` on any activity entry if you want the cryptographic proof. You never have to.

---

## What needs to be built

| Layer | What | Status |
|---|---|---|
| 0G Mem SDK | Memory, typed schema, batching, decay, distillation | Mostly built |
| REST API | Agent ↔ memory interface | Built |
| Agent Runtime | Orchestration, tool routing, DA logging, checkpointing | Not built |
| TUI | Terminal chat, keyboard driven, modes, memory panel | Not built |
| Telegram Bot | Quick interface, same runtime and memory | Not built |
| 0G Compute integration | Inference routing | Not built |

---

## The pitch

Every AI agent today — Claude, ChatGPT, Cursor, Copilot — is a front door to someone else's infrastructure. They own the memory. They own the context. You're renting your relationship with AI from them.

This is the version where you own it.

It lives in your terminal. It knows you. It gets smarter over time. And when you close it, everything it knows about you is yours — encrypted, verifiable, portable, permanent.

**An AI agent for people who don't trust black boxes.**
