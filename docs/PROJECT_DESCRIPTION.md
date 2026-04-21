# 0G Mem — Project Description

---

## High-Level Overview

**0G Mem** is a cryptographically verifiable, encrypted, and user-owned memory layer for AI agents built on 0G Labs.

When an AI agent "remembers" something, that memory is typically a black box — you can't prove what the agent knew, what it retrieved, when it did so, or whether it was tampered with. 0G Mem treats every read and write as a cryptographic event: encrypted, Merkle-proven, immutably logged, and anchored on-chain using 0G's full infrastructure stack (Storage + DA + Chain).

Nobody — not the app, not the cloud provider, not 0G itself — can alter what the agent knew or retrieved.

### Three problems it solves

**1. Auditability**
Enterprises and regulators (EU AI Act Article 12) need to know exactly what an AI agent retrieved before making a decision. Today there is no cryptographic answer to "what did this agent know?" 0G Mem makes every retrieval event provable — the query, the results, the scores, the memory state — all immutably logged and independently verifiable.

**2. Ownership**
Memory lives in a platform's database. When you leave the platform, your agent's memory vanishes. 0G Mem ties memory ownership to your wallet via an ERC-7857-style NFT — your memory follows your wallet, forever. Transfer the NFT, transfer all memory ownership.

**3. Access Control**
In multi-agent systems (orchestrator + specialist agents), memory sharing is all-or-nothing. 0G Mem introduces **memory shards**: grant a medical agent access only to your health records, and a finance agent only to your transaction history — all enforced on-chain, revocable at any time.

---

## Detailed Overview

### Writing a memory

```python
receipt = memory.add("user prefers formal tone")
```

1. The text is embedded into a 384-dimensional semantic vector using `sentence-transformers/all-MiniLM-L6-v2` (runs locally, no API key needed)
2. The data is encrypted with AES-256-GCM using a key derived from your wallet's private key via HKDF-SHA256 — the server never sees plaintext
3. The encrypted blob is uploaded to 0G Storage; its content hash becomes the `blob_id`
4. The `blob_id` is added to a Merkle tree; the new root is computed
5. A write commitment `{agent_id, blob_id, merkle_root, timestamp}` is posted to 0G DA — an immutable, append-only audit log
6. The Merkle root is anchored on 0G Chain via the `MemoryRegistry` smart contract
7. A `WriteReceipt` is returned: `{blob_id, merkle_root, da_tx_hash, chain_tx_hash}`

### Querying memory

```python
results, proof = memory.query("what tone does the user prefer?")
```

1. The query is embedded into a vector (same local model)
2. Cosine similarity search over stored embedding vectors finds the top-k most relevant memories
3. A Merkle inclusion proof is generated for each retrieved blob
4. A read commitment `{agent_id, query_hash, blob_ids, scores, merkle_root}` is posted to 0G DA
5. The current on-chain Merkle root is fetched from 0G Chain to cross-check
6. A `QueryProof` is returned alongside results — anyone can verify it independently

### Verifying a proof

```python
is_valid = memory.verify_proof(proof)  # stateless — anyone can call this
```

- Checks each blob's Merkle inclusion proof is valid against the claimed root
- Checks the claimed root matches the on-chain anchor at the recorded block
- No trust in 0G Mem required — only 0G Chain and 0G DA

### Ownership & access control

```python
# Mint once per wallet — your memory passport on-chain
memory.mint_memory_nft()

# Grant full access to an agent
memory.grant_access("0xAgentAddress")

# Grant shard access — only specific blobs
receipt = memory.add("I take metformin daily")
memory.grant_access("0xDoctorAgent", shard_blob_ids=[receipt.blob_id])

# Revoke anytime — immediate on-chain effect
memory.revoke_access("0xAgentAddress")

# Anyone can check access without trusting 0G Mem
memory.check_access("0xAgent", blob_id)
```

Transferring the NFT transfers all memory ownership to a new wallet. On transfer, all existing access grants are cleared.

### EU AI Act compliance

```python
report = memory.export_audit()
print(report.summary())
report.to_json()  # Article 12 compliant — all reads, writes, timestamps, roots
```

Generates a full audit report covering every read and write event for an agent — with Merkle roots, DA hashes, on-chain anchors, and similarity scores — structured for EU AI Act Article 12 and Article 13 compliance.

### LangChain drop-in

```python
from langchain.chains import ConversationChain

chain = ConversationChain(llm=llm, memory=memory)  # 3 lines, done
```

`VerifiableMemory` implements `load_memory_variables` and `save_context` — fully compatible with LangChain's `BaseMemory` interface.

### REST API

All SDK functionality is exposed over HTTP for language-agnostic integration:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/memory/{agent_id}/add` | Write a memory entry |
| `POST` | `/memory/{agent_id}/query` | Query memory + return proof |
| `GET` | `/memory/{agent_id}/state` | Current Merkle root + chain state |
| `GET` | `/memory/{agent_id}/audit` | Full EU AI Act audit report |
| `POST` | `/memory/{agent_id}/verify` | Verify a proof (stateless) |
| `POST` | `/memory/{agent_id}/grant` | Grant agent access |
| `POST` | `/memory/{agent_id}/revoke` | Revoke agent access |
| `POST` | `/memory/nft/mint` | Mint memory NFT |

### Key design decisions

| Decision | Why |
|----------|-----|
| Client-side encryption | Server sees only ciphertext. Key is derived from wallet — no key management service needed |
| Wallet = identity | No accounts, no usernames. Your private key is your identity and your encryption key |
| Merkle tree over all blobs | Proves the state of memory at any point in time with O(log n) proof size |
| 0G DA for audit log | Immutable, ordered, permissionless — no trusted third party |
| Local embeddings (sentence-transformers) | Free, fast, runs on-device. No API key required |
| NFT shard access model | Per-blob access control enforced on-chain, no redesign of storage layer needed |
| Persistent local index | Embeddings cached locally so queries are fast without re-downloading blobs |

---

## Architecture

### System diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         APPLICATION LAYER                           │
│                                                                     │
│   LangChain App          REST API              Custom Agent         │
│   (drop-in memory)       (FastAPI)             (direct SDK)         │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        SDK CORE  (ogmem/)                             │
│                                                                     │
│   VerifiableMemory                                                  │
│     │                                                               │
│     ├── add(text)                                                   │
│     │     1. ComputeClient.embed()          → float[384] vector     │
│     │     2. encrypt(blob, AES-256-GCM)     → ciphertext            │
│     │     3. StorageClient.upload()         → blob_id               │
│     │     4. MerkleTree.add_leaf(blob_id)   → new root              │
│     │     5. DAClient.post_write_commitment → da_tx_hash            │
│     │     6. ChainClient.update_root()      → chain_tx_hash         │
│     │     └─ returns WriteReceipt                                   │
│     │                                                               │
│     └── query(text)                                                 │
│           1. ComputeClient.embed()          → query vector          │
│           2. cosine similarity search       → top-k matches         │
│           3. MerkleTree.get_proof(blob_id)  → inclusion proof       │
│           4. DAClient.post_read_commitment  → da_read_tx            │
│           5. ChainClient.get_latest_root()  → chain state           │
│           └─ returns (results, QueryProof)                          │
└──────┬────────────────┬───────────────┬──────────────┬─────────────┘
       │                │               │              │
       ▼                ▼               ▼              ▼
┌──────────────┐ ┌────────────┐ ┌───────────┐ ┌─────────────────────┐
│ ogmem/compute  │ │ogmem/storage │ │  ogmem/da   │ │    ogmem/chain        │
│              │ │            │ │           │ │                     │
│ sentence-    │ │ 0G Storage │ │  0G DA    │ │  MemoryRegistry     │
│ transformers │ │ Indexer    │ │ Disperser │ │  (Merkle root       │
│ (local,      │ │ REST API   │ │ REST API  │ │   anchor)           │
│  dim=384)    │ │            │ │           │ │                     │
│              │ │ Flow Ctr.  │ │           │ │  MemoryNFT          │
│ + 0G Serving │ │ (on-chain  │ │           │ │  (ERC-7857 NFT      │
│ + OpenAI     │ │  submit)   │ │           │ │   ownership +       │
│ (fallbacks)  │ │            │ │           │ │   shard ACL)        │
└──────────────┘ └────────────┘ └───────────┘ └─────────────────────┘
                                                        │
                               ┌────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    0G CHAIN  (EVM, Chain ID 16602)                  │
│                                                                     │
│  MemoryRegistry  0xEDF95D9CFb157F5F38C1125B7DFB3968E05d2c4b         │
│  ──────────────────────────────────────────────────────────────     │
│  updateRoot(merkleRoot, daTxHash)  → anchors state per agent        │
│  getLatest(agent)  → most recent Merkle root + block + timestamp    │
│  getAt(agent, index)  → historical root at any past index           │
│  historyLength(agent)  → total number of writes ever made           │
│                                                                     │
│  MemoryNFT  0x70ad85300f522A41689954a4153744BF6E57E488              │
│  ──────────────────────────────────────────────────────────────     │
│  mint()  → one NFT per wallet — your memory passport                │
│  grantAccess(agent, shardIds)  → full or shard-level grant          │
│  revokeAccess(agent)  → clears full + all shard grants              │
│  hasAccess(owner, agent, blobId)  → stateless ACL check             │
│  transferFrom(from, to, tokenId)  → transfers all memory ownership  │
└─────────────────────────────────────────────────────────────────────┘
```

### Write flow

```
User text
   │
   ├──► ComputeClient ──► embedding vector [384 floats]
   │                      (cached in local index for search)
   │
   ├──► encrypt(AES-256-GCM, HKDF key derived from wallet private key)
   │         │
   │         ▼
   │    ciphertext blob ──► 0G Storage ──► blob_id (content hash)
   │
   ├──► MerkleTree.add_leaf(blob_id) ──► new merkle_root
   │
   ├──► 0G DA ──► da_tx_hash  (immutable write log entry)
   │
   └──► 0G Chain ──► MemoryRegistry.updateRoot(merkle_root, da_tx_hash)
                           │
                           ▼
                     WriteReceipt {
                       blob_id,
                       merkle_root,
                       da_tx_hash,
                       chain_tx_hash
                     }
```

### Query flow

```
Query text
   │
   ├──► ComputeClient.embed() ──► query vector
   │
   ├──► cosine_similarity(query_vec, stored_vecs) ──► top-k (index, score) pairs
   │
   ├──► for each match:
   │       decrypt blob (client-side, with wallet key)
   │       MerkleTree.get_proof(blob_id) ──► MerkleProof {leaf, siblings, directions, root}
   │
   ├──► ChainClient.get_latest_root() ──► on-chain chain_block
   │
   ├──► 0G DA ──► da_read_tx  (immutable read log entry)
   │
   └──► QueryProof {
          query_hash,       ← sha256(query_text), hashed for privacy
          blob_ids,         ← what was retrieved
          scores,           ← cosine similarity scores
          merkle_proofs,    ← inclusion proof per blob
          merkle_root,      ← state of memory at query time
          da_read_tx,       ← DA tx proving retrieval happened
          chain_block       ← block where root was anchored
        }
```

### Proof verification (by any third party)

```
Given a QueryProof:
  { blob_ids, merkle_proofs, merkle_root, chain_block, da_read_tx }

Step 1 — Merkle verification (local, no network needed):
  For each blob_id:
    recompute path using siblings + directions
    check final hash == proof.merkle_root  ✓

Step 2 — On-chain verification:
  call MemoryRegistry.getAt(agent, chain_block)
  check returned root == proof.merkle_root  ✓

Step 3 — DA verification (optional):
  fetch da_read_tx from 0G DA
  check payload contains correct agent_id, query_hash, blob_ids  ✓

All three pass → the retrieval is proven to have happened,
with that exact memory state, at that exact block.
No trust in 0G Mem required — only 0G Chain and 0G DA.
```

### Encryption key derivation

```
wallet private key (hex)
        │
        ▼
   HKDF-SHA256
   salt = "0g-mem-encryption-key"
   length = 32 bytes
        │
        ▼
   AES-256-GCM key  (never leaves your machine)
        │
        ├──► encrypt(plaintext) → nonce (12B) ║ ciphertext ║ tag (16B)
        └──► decrypt(ciphertext) → plaintext
```

### NFT access control model

```
Owner wallet
   │
   └──► mint()  →  MemoryNFT token #N  (one per wallet, forever)
                        │
                        ├──► grantAccess(AgentA)
                        │       agentFullAccess[tokenId][AgentA] = true
                        │       → AgentA can read ALL blobs
                        │
                        ├──► grantAccess(AgentB, [blob_id_1, blob_id_2])
                        │       shardAccess[tokenId][AgentB][blob_id_1] = true
                        │       shardAccess[tokenId][AgentB][blob_id_2] = true
                        │       → AgentB can only read those 2 blobs
                        │
                        └──► revokeAccess(AgentA)
                                agentFullAccess[tokenId][AgentA] = false
                                ← all shard grants also cleared

Any app can call hasAccess(owner, agent, blobId) on-chain.
No trust in 0G Mem required.
```

### Module map

```
ogmem/
├── memory.py       VerifiableMemory — main public class, orchestrates all layers
├── compute.py      Embedding generation (sentence-transformers → 0G Serving → OpenAI)
├── storage.py      Blob upload/download via 0G Storage indexer REST API + Flow contract
├── da.py           Write/read commitment logging to 0G DA disperser
├── chain.py        MemoryRegistry + MemoryNFT contract interaction (web3.py)
├── merkle.py       Binary Merkle tree — add leaves, generate + verify proofs
├── proof.py        Data classes: WriteReceipt, QueryProof, AuditReport, Operation
├── encryption.py   AES-256-GCM encrypt/decrypt, HKDF-SHA256 key derivation
└── config.py       Network config, contract addresses, ABIs

api/
└── main.py         FastAPI REST server — 8 endpoints exposing VerifiableMemory over HTTP

contracts/
├── MemoryRegistry.sol   On-chain Merkle root anchor + full history per agent
└── MemoryNFT.sol        ERC-7857-style NFT ownership + shard access control

tests/
├── test_memory.py   43 integration tests (full pipeline with mock clients)
├── test_merkle.py   Merkle tree correctness + edge cases
└── test_proof.py    Proof serialization + audit report structure

examples/
└── legal_assistant.py   End-to-end demo — legal contract Q&A with verifiable proofs
```

### Deployed contracts (0G Galileo Testnet, Chain ID 16602)

| Contract | Address |
|----------|---------|
| MemoryRegistry | `0xEDF95D9CFb157F5F38C1125B7DFB3968E05d2c4b` |
| MemoryNFT | `0x70ad85300f522A41689954a4153744BF6E57E488` |
| Flow (0G) | `0x22E03a6A89B950F1c82ec5e74F8eCa321a105296` |

### Infrastructure dependencies

| Component | Provider | Status |
|-----------|----------|--------|
| EVM Chain | 0G Galileo Testnet (Chain ID 16602) | ✅ Fully working |
| Semantic embeddings | sentence-transformers/all-MiniLM-L6-v2 (local, dim=384) | ✅ Fully working |
| Merkle proofs | Pure Python (in-SDK, SHA-256) | ✅ Fully working |
| AES-256-GCM encryption | Python `cryptography` + HKDF-SHA256 | ✅ Fully working |
| NFT access control | MemoryNFT deployed on 0G Chain | ✅ Fully working |
| 0G Storage | `indexer-storage-testnet-turbo.0g.ai` via @0gfoundation/0g-ts-sdk (Node.js bridge) | ✅ Fully working |
| 0G DA | Local Docker node, gRPC localhost:51001 (no public disperser on Galileo) | ✅ Fully working |
