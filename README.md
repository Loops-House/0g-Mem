# 0G Mem

> The memory layer of a trustless agent runtime — decentralised, verifiable, and owned by you.

0G Mem is building toward a fully trustless AI agent runtime: think Hermes Agent meets OpenClaw, but on decentralised infrastructure. Any agent runs in a sandboxed environment where every inference and memory access is cryptographically provable. No single party — including us — controls agent state or execution.

We're building bottom-up, starting with the memory layer. Every memory read and write is encrypted client-side, logged to 0G DA, Merkle-proven, and anchored on 0G Chain — so any agent's memory history can be verified independently, without trusting the provider.

---

## Why this matters

Most AI memory providers (Mem0, Zep, LangMem, Supermemory) store your agent's memory on their servers. They have full access to it per their T&C. Memory is ephemeral, siloed, and platform-owned — it dies between sessions and cannot be ported across frameworks.

0G Mem fixes this:

| Problem | 0G Mem solution |
|---|---|
| Memory dies between sessions | Persistent, content-addressed storage on 0G |
| Provider owns and can read your memory | AES-256-GCM encrypted client-side — provider never sees plaintext |
| No way to verify memory wasn't tampered | SHA-256 Merkle proofs anchored on 0G Chain |
| Memory locked to one agent/framework | LangChain drop-in, AutoGen/CrewAI compatible SDK |
| No control over who accesses agent memory | On-chain shard-level access control via MemoryNFT |

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Your Agent / LLM                     │
│              (LangChain, AutoGen, CrewAI, custom)        │
└──────────────────────┬──────────────────────────────────┘
                       │  SDK call: memory.add() / memory.query()
                       ▼
┌─────────────────────────────────────────────────────────┐
│                   0G Mem Python SDK                      │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │  encryption  │  │  merkle tree │  │   embeddings  │  │
│  │ AES-256-GCM  │  │   SHA-256    │  │ sentence-     │  │
│  │ HKDF-SHA256  │  │   proofs     │  │ transformers  │  │
│  └──────┬───────┘  └──────┬───────┘  └───────┬───────┘  │
└─────────┼────────────────┼──────────────────┼──────────┘
          │                │                  │
     encrypted          Merkle root       cosine sim
     blob upload         anchor           local search
          │                │
          ▼                ▼
┌─────────────┐   ┌─────────────────┐   ┌──────────────┐
│  0G Storage │   │   0G Chain      │   │    0G DA     │
│  (blobs)    │   │ MemoryRegistry  │   │  audit log   │
│             │   │  MemoryNFT      │   │  (gRPC)      │
└─────────────┘   └─────────────────┘   └──────────────┘
```

### Write flow

```
memory.add(text)
  → embed text locally (sentence-transformers/all-MiniLM-L6-v2)
  → AES-256-GCM encrypt (key derived via HKDF-SHA256 from wallet private key)
  → upload encrypted blob to 0G Storage
  → append blob_id to local SHA-256 Merkle tree
  → post write commitment to 0G DA: {agent_id, blob_id, merkle_root, timestamp}
  → call MemoryRegistry.updateRoot(merkle_root, da_tx_hash) on 0G Chain
  → return WriteReceipt {blob_id, merkle_root, da_tx_hash, chain_tx_hash}
```

### Query flow

```
memory.query(text, top_k)
  → embed query locally
  → cosine similarity search against cached embeddings
  → fetch matched blobs from 0G Storage, decrypt client-side
  → generate Merkle inclusion proof for each returned blob
  → post read commitment to 0G DA: {agent_id, query_hash, blob_ids, merkle_root}
  → return (results, QueryProof {blob_ids, scores, merkle_proofs, da_read_tx, chain_block})
```

---

## Smart Contracts

Deployed on **0G Galileo Testnet (Chain ID 16602)**

### MemoryRegistry — `0xEDF95D9CFb157F5F38C1125B7DFB3968E05d2c4b`

Maintains a full, append-only Merkle root history per agent on-chain.

```solidity
// Every memory write anchors a new root
updateRoot(bytes32 merkleRoot, bytes32 daTxHash)

// Query historical state
getLatest(address agent) → MemoryState
getAt(address agent, uint index) → MemoryState
historyLength(address agent) → uint

// Stateless Merkle proof verification
verifyInclusion(address agent, bytes32 leaf, bytes32[] proof, bytes32 root) → bool
```

### MemoryNFT — `0x70ad85300f522A41689954a4153744BF6E57E488`

ERC-7857-inspired memory passport. One NFT per wallet, enforcing on-chain access control.

```solidity
mint()                                          // one per wallet, forever
grantAccess(address agent, bytes32[] shardIds)  // full access if shardIds empty
revokeAccess(address agent)                     // clears all grants immediately
hasAccess(address owner, address agent, bytes32 blobId) → bool
// Transfer clears all grants — new owner starts fresh
```

---

## One-click deploy (Telegram bot)

The fastest way to try 0G Mem — deploy your own Telegram bot with verifiable memory in under 5 minutes.

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new/template?template=https://github.com/violinadoley/0g-Mem&envs=AGENT_KEY,TELEGRAM_BOT_TOKEN,ZEROG_SERVICE_URL,ZEROG_API_KEY,ZEROG_MODEL,MEMORY_REGISTRY_ADDRESS,MEMORY_NFT_ADDRESS&AGENT_KEYDesc=Your+0G+wallet+private+key&TELEGRAM_BOT_TOKENDesc=Token+from+BotFather&ZEROG_SERVICE_URLDesc=0G+Compute+provider+URL&ZEROG_API_KEYDesc=0G+Compute+API+key&ZEROG_MODELDesc=Model+name&ZEROG_MODELDefault=qwen/qwen-2.5-7b-instruct&MEMORY_REGISTRY_ADDRESSDefault=0xEDF95D9CFb157F5F38C1125B7DFB3968E05d2c4b&MEMORY_NFT_ADDRESSDefault=0x70ad85300f522A41689954a4153744BF6E57E488)

Each user deploys their own instance — you are the operator and the user. Your `AGENT_KEY` controls your memory. Nobody else has custody.

---

## Quickstart (SDK)

```bash
git clone https://github.com/violinadoley/0g-Mem
cd 0g-mem
pip install -e .
cp .env.example .env
# Fill in AGENT_KEY in .env
```

```python
import os
from ogmem import VerifiableMemory

memory = VerifiableMemory(
    agent_id="my-agent",
    private_key=os.environ["AGENT_KEY"],
    network="0g-testnet",
)

# Write
receipt = memory.add("user prefers formal tone")
print(receipt.blob_id)        # content address on 0G Storage
print(receipt.chain_tx_hash)  # Merkle root anchored on 0G Chain
print(receipt.da_tx_hash)     # write commitment on 0G DA

# Query
results, proof = memory.query("what does the user prefer?")
print(results)                # ['user prefers formal tone']
print(proof.merkle_root)      # matches on-chain anchor

# Verify
valid = memory.verify_proof(proof)
print(valid)                  # True
```

---

## LangChain drop-in

```python
from langchain.chains import ConversationChain
from ogmem import VerifiableMemory

memory = VerifiableMemory(
    agent_id="my-agent",
    private_key=os.environ["AGENT_KEY"],
    network="0g-testnet",
)
chain = ConversationChain(llm=llm, memory=memory)
# memory persists across sessions, encrypted, verifiable on-chain
```

---

## NFT ownership and access control

```python
memory.mint_memory_nft()

# Grant full access to an agent
memory.grant_access("0xAgentWalletAddress")

# Grant shard-level access (specific memory blobs only)
receipt = memory.add("I take metformin daily")
memory.grant_access("0xDoctorAgentAddress", shard_blob_ids=[receipt.blob_id])

# Revoke anytime — single on-chain transaction
memory.revoke_access("0xAgentWalletAddress")
```

---

## Audit export

```python
report = memory.export_audit()
print(report.summary())
# Total writes: 12 | Total reads: 8 | EU AI Act compliant: True

with open("audit_report.json", "w") as f:
    f.write(report.to_json())
# Full Merkle root history + DA tx hashes — EU AI Act Article 12 compliant
```

---

## REST API

```bash
python -m uvicorn api.main:app --port 8000 --env-file .env
```

| Method | Endpoint | Description |
|---|---|---|
| POST | `/memory/{agent_id}/add` | Write encrypted memory entry |
| POST | `/memory/{agent_id}/query` | Semantic search with proof |
| GET | `/memory/{agent_id}/state` | Current on-chain Merkle state |
| GET | `/memory/{agent_id}/audit` | Full audit report (JSON) |
| POST | `/memory/{agent_id}/verify` | Verify a QueryProof |
| POST | `/memory/{agent_id}/grant` | Grant on-chain agent access |
| POST | `/memory/{agent_id}/revoke` | Revoke on-chain agent access |

Auth via headers: `X-Wallet-Address`, `X-Signature`, `X-Auth-Message`

---

## Frontend dashboard

```bash
cd frontend
npm install
npm run dev   # http://localhost:3000
```

Connect MetaMask with 0G Galileo Testnet added. Dashboard includes:
- Memory explorer (add / query)
- Audit report viewer
- Access control (grant / revoke)
- Proof verification

---

## Running the DA node (optional)

0G DA requires a local Docker node — no public disperser on Galileo testnet. Without it, DA falls back to local SHA-256 commitments (still functional, not dispersed).

```bash
git clone https://github.com/0gfoundation/0g-da-client.git ../0g-da-client
cd ../0g-da-client
git submodule update --init -- 0g-da-contract 0g-da-encoder 0g-da-signer

cd ../0g-mem
docker-compose up -d
```

---

## Project structure

```
ogmem/              # Core Python SDK
  memory.py         # VerifiableMemory class (main public API)
  encryption.py     # AES-256-GCM + HKDF-SHA256
  merkle.py         # SHA-256 Merkle tree + proof generation
  storage.py        # 0G Storage client (Node.js bridge)
  da.py             # 0G DA client (gRPC)
  chain.py          # 0G Chain interaction (web3.py)
  compute.py        # Embeddings + cosine similarity
  config.py         # Network configs + contract ABIs

contracts/          # Solidity smart contracts
  MemoryRegistry.sol  # On-chain Merkle root anchor
  MemoryNFT.sol       # ERC-7857-inspired access control

api/                # FastAPI REST server
  routes/memory.py  # 7 memory endpoints
  routes/nft.py     # NFT mint endpoint

frontend/           # Next.js 14 dashboard (wagmi + viem)
  app/deploy/       # One-click onboarding page
waitlist/           # Next.js 14 waitlist site (Supabase + Resend)
telegram_bot/       # Telegram bot (python-telegram-bot)
runtime/            # AgentRuntime + built-in tools
tui/                # Terminal UI (Textual)
Dockerfile.bot      # Docker image for Telegram bot deploy
railway.toml        # Railway one-click deploy config
render.yaml         # Render one-click deploy config
tests/              # 43+ pytest tests (mock clients, no network required)
examples/           # legal_assistant.py demo
docs/               # Architecture + pitch docs
```

---

## What's next

- **TypeScript/JS SDK** — mirror of Python SDK for frontend-native agents
- **ZK proofs** — replace Merkle proofs with ZK proofs for private verification
- **Multi-agent coordination** — shared verifiable memory across agent swarms
- **Group Telegram bots** — shared memory for team agents with per-member access grants

---

## Docs

- [Architecture](docs/ARCHITECTURE.md)
- [Project Description](docs/PROJECT_DESCRIPTION.md)
- [Pitch Deck](docs/PITCH_DECK.md)
