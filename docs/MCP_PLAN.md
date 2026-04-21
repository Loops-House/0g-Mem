# MCP Server Implementation Plan

## Overview

Model Context Protocol (MCP) is Anthropic's open standard for connecting AI assistants to external tools and data sources. Adding an MCP server to 0G Mem Agent makes verifiable memory a first-class citizen in any MCP-compatible host: Claude Desktop, Cursor, Zed, Continue, Cline, etc.

The key insight: **the same VerifiableMemory instance that powers the Telegram bot and TUI can be exposed as an MCP server**. One encrypted memory store, reachable from every AI tool the user runs.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│            MCP Host (Claude Desktop / Cursor / ...)      │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │                   MCP Client                        │  │
│  │  (built into host, speaks JSON-RPC over stdio)     │  │
│  └─────────────────────┬──────────────────────────────┘  │
└────────────────────────┼─────────────────────────────────┘
                         │  stdio (JSON-RPC 2.0)
                         ▼
┌─────────────────────────────────────────────────────────┐
│              ogmem/mcp_server.py  (new file)             │
│                                                          │
│  FastMCP server — 10 tools, 2 resources                  │
│                                                          │
│  Uses asyncio.run_in_executor() to wrap sync SDK calls   │
└──────────────────────────┬──────────────────────────────┘
                           │  Python method calls
                           ▼
┌─────────────────────────────────────────────────────────┐
│              VerifiableMemory (existing SDK)             │
│                                                          │
│  encryption  │  merkle  │  storage  │  chain  │  DA      │
└─────────────────────────────────────────────────────────┘
```

Transport: **stdio** (local process). The MCP host spawns `python -m ogmem.mcp_server` as a subprocess and communicates over stdin/stdout. No network port needed.

---

## Files to Create / Modify

| File | Change |
|---|---|
| `ogmem/mcp_server.py` | New — the MCP server (FastMCP pattern) |
| `pyproject.toml` | Add optional `[mcp]` dependency group |
| `README.md` | Add MCP section with install + config snippets |
| `docs/MCP_PLAN.md` | This file |

---

## Tool List (10 tools)

### Core memory operations

#### `memory_add`
```
Input:  text: str, metadata: dict (optional)
Output: { blob_id, merkle_root, da_tx_hash, chain_tx_hash }
```
Writes one memory entry. Encrypts client-side, uploads to 0G Storage, anchors Merkle root on 0G Chain, posts to 0G DA.

#### `memory_query`
```
Input:  query: str, top_k: int = 5
Output: { results: [str], proof: { blob_ids, merkle_proofs, da_read_tx, chain_block } }
```
Semantic search over all memories. Returns plaintext results + full Merkle proof bundle.

#### `memory_stats`
```
Input:  (none)
Output: { total_entries, last_updated, merkle_root, chain_block }
```
Quick read of current on-chain state — no blob fetches.

#### `memory_summary`
```
Input:  max_entries: int = 20
Output: { summary: str }
```
Fetches recent memories and returns a prose summary. Useful for "what do I know about X?" prompts.

#### `memory_distill`
```
Input:  topic: str (optional)
Output: { distilled_text: str, source_blob_ids: [str] }
```
Condenses multiple related memories into one canonical entry, writes it back, marks originals as superseded.

#### `memory_evolve`
```
Input:  blob_id: str, new_text: str
Output: { new_blob_id, merkle_root, ... }
```
Updates a specific memory entry. Writes new blob, appends new Merkle root — full history preserved on-chain.

#### `memory_delete`
```
Input:  blob_id: str
Output: { success: bool }
```
Soft-deletes by writing a tombstone entry. On-chain history is immutable; the SDK skips tombstoned entries during query.

### Verification

#### `memory_verify`
```
Input:  proof: dict (QueryProof JSON)
Output: { valid: bool, verified_at_block: int }
```
Stateless Merkle proof verification — calls `MemoryRegistry.verifyInclusion` on-chain.

### Access control

#### `memory_grant_access`
```
Input:  agent_address: str, shard_blob_ids: [str] (optional)
Output: { tx_hash: str }
```
Calls `MemoryNFT.grantAccess` on 0G Chain.

#### `memory_revoke_access`
```
Input:  agent_address: str
Output: { tx_hash: str }
```
Calls `MemoryNFT.revokeAccess` on 0G Chain.

---

## Resource List (2 resources)

### `memory://entries`
Returns all memory entries as a JSON array. Fetched lazily (only when host requests it). Gives the LLM a full dump of what's in memory for context.

### `memory://stats`
Returns current on-chain state snapshot: entry count, latest Merkle root, last write timestamp.

---

## Async Handling

VerifiableMemory is synchronous (web3.py + requests). MCP SDK is async. Bridge pattern:

```python
import asyncio
from functools import partial

loop = asyncio.get_event_loop()

async def _run_sync(fn, *args, **kwargs):
    return await loop.run_in_executor(None, partial(fn, *args, **kwargs))

@mcp.tool()
async def memory_add(text: str) -> dict:
    receipt = await _run_sync(memory.add, text)
    return {
        "blob_id": receipt.blob_id,
        "merkle_root": receipt.merkle_root.hex(),
        "da_tx_hash": receipt.da_tx_hash,
        "chain_tx_hash": receipt.chain_tx_hash,
    }
```

---

## Configuration

### Environment variables (same as existing SDK)

```env
AGENT_KEY=0x...          # wallet private key — derives encryption key
AGENT_ID=my-agent        # logical name (default: "default")
NETWORK=0g-testnet       # or custom RPC
```

### Claude Desktop (`~/Library/Application Support/Claude/claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "0g-mem-agent": {
      "command": "python",
      "args": ["-m", "ogmem.mcp_server"],
      "env": {
        "AGENT_KEY": "0x...",
        "AGENT_ID": "my-agent"
      }
    }
  }
}
```

### Cursor (`.cursor/mcp.json` in project root)

```json
{
  "mcpServers": {
    "0g-mem-agent": {
      "command": "python",
      "args": ["-m", "ogmem.mcp_server"],
      "env": {
        "AGENT_KEY": "0x..."
      }
    }
  }
}
```

---

## Optional dependency in `pyproject.toml`

```toml
[project.optional-dependencies]
mcp = ["mcp>=1.0.0"]
```

Install: `pip install "ogmem[mcp]"`

---

## Portability: how it ties together

Same wallet → same `AGENT_KEY` → same AES encryption key → same memory store, accessible from:

| Interface | How |
|---|---|
| Telegram bot | `python -m telegram_bot` (Railway) |
| TUI | `python -m tui` |
| MCP (Claude Desktop) | `python -m ogmem.mcp_server` (local) |
| MCP (Cursor) | same |
| REST API | `uvicorn api.main:app` |
| Python SDK | `from ogmem import VerifiableMemory` |

Every interface reads/writes the same encrypted blobs on 0G Storage. Memory isn't locked to any one tool.

---

## Honest Drawbacks

| Drawback | Detail |
|---|---|
| **Slow tools** | Each `memory_add` call hits 0G Storage + 0G Chain — 5–30s latency. Not suitable for hot-path inference loops. |
| **Local install required** | MCP uses stdio, so the server runs as a local process. User must `pip install ogmem[mcp]` and configure their host. No hosted option yet. |
| **Agent decides when to call** | The LLM chooses when to read/write memory. It may not call tools at the right moments without explicit prompting or system prompt guidance. |
| **No streaming** | Long memory dumps via `memory://entries` block until all blobs are fetched and decrypted. |
| **Single-user** | stdio process is per-user; no multi-tenant MCP hosting without a separate deployment per user. |

---

## Implementation Order

1. `ogmem/mcp_server.py` — FastMCP server with all 10 tools + 2 resources
2. `pyproject.toml` — add `[mcp]` optional dep
3. Test locally with Claude Desktop
4. Update `README.md` with MCP section
5. (Optional) Add `make mcp` target to `Makefile`
