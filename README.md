# 0g Mem

Cryptographically verifiable, encrypted agent memory built on 0g Labs.

Every memory read and write is encrypted client-side, logged to 0g DA, Merkle-proven, and anchored on 0g Chain — so any agent's memory history can be verified independently.

## How it works

```
add(text)  →  AES-256-GCM encrypt (wallet key, client-side)
           →  upload to 0g Storage
           →  update Merkle tree
           →  post write commitment to 0g DA (gRPC)
           →  anchor Merkle root on 0g Chain
           →  return WriteReceipt {blob_id, merkle_root, da_tx_hash, chain_tx_hash}

query(text) →  embed + cosine similarity search (local, sentence-transformers)
            →  decrypt blob (client-side)
            →  generate Merkle inclusion proof
            →  post read log to 0g DA
            →  return (results, QueryProof)
```

## Quickstart

```bash
git clone https://github.com/violinadoley/0g-Mem
cd 0g-mem
pip install -e .
```

```python
import os
from ogmem import VerifiableMemory

memory = VerifiableMemory(
    agent_id="my-agent",
    private_key=os.environ["AGENT_KEY"],
    network="0g-testnet",
)

receipt = memory.add("user prefers formal tone")
print(receipt.blob_id)        # content address on 0g Storage
print(receipt.chain_tx_hash)  # Merkle root anchored on 0g Chain
print(receipt.da_tx_hash)     # write commitment on 0g DA

results, proof = memory.query("what does the user prefer?")
print(proof.da_read_tx)    # retrieval logged on 0g DA
print(proof.merkle_root)   # matches on-chain anchor
```

## NFT ownership + access control

```python
memory.mint_memory_nft()

# Grant full access
memory.grant_access("0xAgentWalletAddress")

# Grant scoped access (specific memory shard only)
receipt = memory.add("I take metformin daily")
memory.grant_access("0xDoctorAgentAddress", shard_blob_ids=[receipt.blob_id])

# Revoke anytime
memory.revoke_access("0xAgentWalletAddress")
```

## LangChain drop-in

```python
from langchain.chains import ConversationChain
from ogmem import VerifiableMemory

memory = VerifiableMemory(agent_id="my-agent", private_key=os.environ["AGENT_KEY"], network="0g-testnet")
chain = ConversationChain(llm=llm, memory=memory)
```

## Audit export

```python
report = memory.export_audit()
print(report.summary())
with open("audit_report.json", "w") as f:
    f.write(report.to_json())
```

## Features

| Feature | Status |
|---|---|
| Tamper-proof logs | Merkle proofs + 0g DA (gRPC) |
| Client-side encryption | AES-256-GCM, HKDF key from wallet |
| NFT memory ownership | ERC-7857-style on 0g Chain |
| Memory shards | Grant/revoke per blob per agent |
| EU AI Act Article 12 | Full audit export (JSON) |
| LangChain drop-in | `memory_variables`, `load_memory_variables`, `save_context` |

## Running the DA node

0g DA requires a local Docker node — no public disperser on Galileo testnet.

```bash
git clone https://github.com/0gfoundation/0g-da-client.git ../0g-da-client
cd ../0g-da-client
git submodule update --init -- 0g-da-contract 0g-da-encoder 0g-da-signer

cd ../0g-mem
docker-compose up -d
```

## Running the demo

```bash
docker-compose up -d
export $(grep -v "^#" .env | grep -v "^$" | xargs)
python examples/legal_assistant.py --live
```

## Docs

- [Architecture](docs/ARCHITECTURE.md)
- [Project Description](docs/PROJECT_DESCRIPTION.md)
