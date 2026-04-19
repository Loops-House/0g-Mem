# 0g Mem — Technical Architecture

> Verifiable Agent Memory Infrastructure built on 0g Labs

---

## 1. Problem Statement

AI agents make decisions based on retrieved memory. Today:
- **Nobody can prove what an agent retrieved** when it made a decision
- **Memory is mutable and centralized** — can be tampered with post-hoc
- **EU AI Act Article 12** mandates tamper-proof logs for high-risk AI by Aug 2026
- **Multi-agent systems** have no defense against memory poisoning

0g Mem solves this by making every memory read/write **cryptographically verifiable,
immutable, and auditable** — using 0g's full stack as the only platform that combines
Storage + DA + Chain in one ecosystem.

---

## 2. System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                          AI Agent / App                             │
│            (LangChain / LangGraph / AutoGen / Custom)               │
└────────────────────────────┬────────────────────────────────────────┘
                             │ SDK calls (3 lines of code)
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      0g Mem SDK (Python)                            │
│                                                                     │
│   VerifiableMemory.add(text)      →  write pipeline                 │
│   VerifiableMemory.query(text)    →  read pipeline + proof          │
│   VerifiableMemory.export_audit() → compliance report               │
└────┬──────────────┬──────────────┬──────────────┬───────────────────┘
     │              │              │              │
     ▼              ▼              ▼              ▼
┌─────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐
│   0g    │  │  Local   │  │   0g     │  │   0g Chain   │
│ Storage │  │Embeddings│  │    DA    │  │  (EVM L1)    │
│         │  │          │  │          │  │              │
│ Memory  │  │sentence- │  │Commitment│  │MemoryRegistry│
│  blobs  │  │transformers  proofs  │  │  contract    │
│         │  │(dim=384) │  │  (gRPC) │  │              │
└─────────┘  └──────────┘  └──────────┘  └──────────────┘
```

---

## 3. Core Data Flow

### 3.1 Write Path (agent adds a memory)

```
Agent calls: memory.add("user prefers formal responses")

Step 1: EMBED
  → sentence-transformers/all-MiniLM-L6-v2 (runs locally, no API needed)
  → Returns: float[384] embedding vector
  → Cached in local index for future similarity search

Step 2: ENCRYPT
  → AES-256-GCM with key derived via HKDF-SHA256 from wallet private key
  → Server never sees plaintext

Step 3: STORAGE
  → Upload encrypted blob to 0g Storage via @0gfoundation/0g-ts-sdk (Node.js bridge)
  → Returns: blob_id (keccak256 Merkle root of blob content)

Step 4: MERKLE UPDATE
  → Add blob_id as leaf to local SHA-256 Merkle tree
  → Compute new Merkle root

Step 5: DA COMMITMENT
  → Post via gRPC to local 0g DA node (localhost:51001):
    { type: "memory_write", agent_id, blob_id, merkle_root, timestamp }
  → Returns: da_tx_hash ("grpc:<request_id_hex>")

Step 6: CHAIN ANCHOR
  → Call MemoryRegistry.updateRoot(merkle_root, da_tx_hash) on 0g Chain
  → On-chain state: agent_address → {merkle_root, block_number, da_tx_hash, timestamp}

Returns to agent: WriteReceipt { blob_id, merkle_root, da_tx_hash, chain_tx_hash }
```

### 3.2 Read Path (agent queries memory)

```
Agent calls: result, proof = memory.query("what does the user prefer?")

Step 1: EMBED QUERY
  → sentence-transformers/all-MiniLM-L6-v2 (local)
  → Returns: float[384] query vector

Step 2: SIMILARITY SEARCH
  → Cosine similarity against cached local embedding index
  → Returns: top-k {blob_id, score} pairs

Step 3: FETCH + DECRYPT
  → Download matched blobs from 0g Storage
  → Decrypt client-side with HKDF-derived key

Step 4: PROOF GENERATION
  → For each returned blob_id, generate Merkle inclusion proof
    (blob_id is a leaf; prove it's in the committed Merkle root)
  → Proof = {leaf, siblings[], root, path}

Step 5: DA LOG
  → Post via gRPC to 0g DA:
    { type: "memory_read", agent_id, query_hash, blob_ids, scores, merkle_root }
  → Returns: da_read_tx (immutable retrieval log)

Step 6: CHAIN CHECK
  → Fetch current Merkle root from MemoryRegistry on 0g Chain
  → Cross-check with local root

Returns to agent: (results, QueryProof {
    query_hash, blob_ids, scores,
    merkle_proofs, merkle_root,
    da_read_tx, chain_block
})
```

### 3.3 Audit Export Path

```
User calls: audit = memory.export_audit(agent_id)

Step 1: Fetch all on-chain state anchors from MemoryRegistry (by agent address)
Step 2: For each anchor, fetch DA commitment from in-process store
Step 3: Reconstruct timeline: every write + every read, in order
Step 4: For each read: verify retrieved blobs match committed Merkle root
Step 5: Generate structured report:
  {
    agent_id,
    period: {from_block, to_block},
    total_writes: N,
    total_reads: M,
    operations: [...],
    eu_ai_act_compliant: true,
    verifiable_by: "anyone with 0g Chain + DA access"
  }
Step 6: Export as JSON (report.to_json())
```

---

## 4. Component Architecture

### 4.1 Smart Contracts (deployed on 0g Galileo Testnet, Chain ID 16602)

**MemoryRegistry** — `0xEDF95D9CFb157F5F38C1125B7DFB3968E05d2c4b`
```
updateRoot(bytes32 merkleRoot, bytes32 daTxHash)
  → anchors new state per agent, appends to history

getLatest(address agent) → MemoryState { merkleRoot, blockNumber, daTxHash, timestamp }
getAt(address agent, uint256 index) → MemoryState
historyLength(address agent) → uint256
```

**MemoryNFT** — `0x70ad85300f522A41689954a4153744BF6E57E488`
```
mint() → one NFT per wallet, forever
grantAccess(address agent, bytes32[] shardIds) → full or per-blob access
revokeAccess(address agent) → clears all grants
hasAccess(address owner, address agent, bytes32 blobId) → bool
```

### 4.2 SDK Structure

```
ogmem/
├── memory.py      VerifiableMemory — main public API + LangChain BaseMemory impl
├── storage.py     0g Storage client (Node.js bridge → @0gfoundation/0g-ts-sdk)
├── compute.py     Embedding client (sentence-transformers local → OpenAI fallback)
├── da.py          0g DA client (gRPC to local Docker DA node)
├── chain.py       0g Chain client (MemoryRegistry + MemoryNFT via web3.py)
├── merkle.py      SHA-256 Merkle tree — add leaves, generate + verify proofs
├── proof.py       Data classes: WriteReceipt, QueryProof, AuditReport
├── encryption.py  AES-256-GCM encrypt/decrypt, HKDF-SHA256 key derivation
└── config.py      Network config, contract addresses, ABIs

proto/
├── disperser.proto        gRPC proto for 0g DA disperser
├── disperser_pb2.py       generated protobuf stubs (run: make proto)
└── disperser_pb2_grpc.py  generated gRPC stubs

scripts/
└── zg_storage.js  Node.js bridge — wraps @0gfoundation/0g-ts-sdk for upload/download

api/
├── main.py        FastAPI app setup
├── models.py      Pydantic request/response models
├── dependencies.py  Shared auth + VerifiableMemory instance cache
└── routes/
    ├── memory.py  Memory endpoints (add, query, state, audit, verify, grant, revoke)
    └── nft.py     NFT mint endpoint

contracts/
├── MemoryRegistry.sol   On-chain Merkle root anchor + full history per agent
└── MemoryNFT.sol        ERC-7857-style NFT ownership + shard access control
```

### 4.3 API Server (api/main.py)

```
POST /memory/{agent_id}/add      → write memory entry
POST /memory/{agent_id}/query    → query + return proof
GET  /memory/{agent_id}/state    → current Merkle root + chain state
GET  /memory/{agent_id}/audit    → full EU AI Act audit report (JSON)
POST /memory/{agent_id}/verify   → verify a proof (stateless, third-party use)
POST /memory/{agent_id}/grant    → grant agent access (on-chain)
POST /memory/{agent_id}/revoke   → revoke agent access (on-chain)
POST /memory/nft/mint            → mint memory NFT
```

### 4.4 Infrastructure

```
Component             Provider                        Status
─────────────────────────────────────────────────────────────────────
0g Chain (EVM)        Galileo Testnet, Chain ID 16602  ✅ Live
0g Storage            indexer-storage-testnet-turbo    ✅ Live (Node.js bridge)
0g DA                 Local Docker node, gRPC :51001   ✅ Live (docker-compose)
Embeddings            sentence-transformers (local)    ✅ Live (dim=384)
AES-256-GCM encrypt   Python cryptography library      ✅ Live
Merkle proofs         Pure Python (in-SDK)             ✅ Live
MemoryRegistry        Deployed on 0g Chain             ✅ Live
MemoryNFT             Deployed on 0g Chain             ✅ Live
```

---

## 5. Why Each 0g Component Is Necessary

| Component | What it does in 0g Mem | Why you can't replace it |
|---|---|---|
| **0g Storage** | Stores memory blobs content-addressed | Immutable + decentralized — no central party can alter or delete |
| **0g DA** | Posts operation logs (reads + writes) via gRPC | High-throughput, cheap, permanent — anchors the audit trail without bloating L1 |
| **0g Chain** | Smart contract anchors Merkle roots on-chain | Anyone can independently verify state without trusting 0g Mem as a company |

Using all three together: no single party (including 0g Mem the company) can tamper with
what an agent knew. The proof is independently verifiable by anyone.

---

## 6. Security Properties

| Property | How it's achieved |
|---|---|
| **Tamper-evident writes** | Blob content is hash-addressed in 0g Storage; changing content changes hash |
| **Immutable audit log** | DA commitments are permanent (gRPC → 0g DA node → dispersed to DA nodes) |
| **Non-repudiable reads** | Every retrieval logged to DA before result returned to agent |
| **Third-party verifiability** | Anyone with 0g Chain + DA access can replay and verify the full history |
| **Memory poisoning resistance** | Writes require agent's private key signature; others can't write to your memory |
| **Historical queries** | On-chain history of Merkle roots allows proving state at any past block |
| **Client-side encryption** | Key derived from wallet via HKDF-SHA256 — server never sees plaintext |

---

## 7. EU AI Act Article 12 Compliance Mapping

| Article 12 Requirement | How 0g Mem satisfies it |
|---|---|
| "Automatic logging of operations" | Every read/write posted to 0g DA automatically |
| "Traceability throughout the AI system's lifetime" | Immutable chain of Merkle roots on 0g Chain |
| "Logs cannot be modified" | DA layer is append-only; on-chain state is immutable |
| "Appropriate retention periods" | 0g Storage has configurable persistence guarantees |
| "Logging of input data used" | Read log includes query hash + retrieved blob IDs + similarity scores |

---

## 8. LangChain Integration (3 lines)

```python
from langchain.chains import ConversationChain
from ogmem import VerifiableMemory

memory = VerifiableMemory(
    agent_id="my-legal-assistant",
    private_key=os.environ["AGENT_KEY"],
    network="0g-testnet"
)

# Drop into any LangChain chain — works exactly like ConversationBufferMemory
chain = ConversationChain(llm=llm, memory=memory)
response = chain.predict(input="Summarize the liability clauses")

# Every interaction is now cryptographically logged
```

`VerifiableMemory` implements `load_memory_variables()` and `save_context()` — fully
compatible with LangChain's `BaseMemory` interface.

---

## 9. Tech Stack

| Layer | Technology |
|---|---|
| SDK | Python 3.10+ |
| Smart contracts | Solidity 0.8.x (0g Chain, EVM-compatible) |
| Contract interaction | web3.py |
| Storage bridge | Node.js + @0gfoundation/0g-ts-sdk |
| DA transport | gRPC (grpcio) → local 0g DA Docker node |
| API server | FastAPI + uvicorn |
| Merkle tree | Custom SHA-256 implementation |
| Embeddings | sentence-transformers/all-MiniLM-L6-v2 (local, dim=384) |
| Encryption | AES-256-GCM + HKDF-SHA256 (Python cryptography) |
| Testing | pytest (43 tests) |

---

## 10. Status & Roadmap

### v0.1.0 (current)
- `VerifiableMemory` SDK — `add()`, `query()`, `verify_proof()`, `export_audit()`
- 0g Storage integration via @0gfoundation/0g-ts-sdk Node.js bridge
- 0g DA integration — gRPC submission to local Docker DA node
- 0g Chain integration — MemoryRegistry + MemoryNFT deployed on Galileo testnet
- AES-256-GCM client-side encryption, HKDF-SHA256 key derivation
- SHA-256 Merkle tree — inclusion proof generation and verification
- LangChain BaseMemory drop-in
- EU AI Act Article 12 audit export (JSON)
- FastAPI REST server (8 endpoints)
- 43 tests

### Roadmap
- PyPI release (`pip install 0g-mem`)
- Web dashboard — memory timeline + proof visualizer
- ZK proof upgrade (replace Merkle proofs with ZK proofs)
- JS/TS SDK
- PDF audit report export
