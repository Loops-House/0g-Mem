"""VerifiableMemory: cryptographically provable agent memory on 0g."""

import hashlib
import json
import os
import pathlib
import time
from typing import Optional

from .chain import ChainClient
from .compute import ComputeClient
from .config import NETWORKS, NetworkConfig
from .da import DAClient
from .encryption import derive_encryption_key
from .merkle import MerkleTree
from .proof import AuditReport, Operation, QueryProof, WriteReceipt
from .storage import StorageClient


class VerifiableMemory:
    """Agent memory stored on 0g Storage with Merkle proofs anchored on-chain."""

    def __init__(
        self,
        agent_id: str,
        private_key: str,
        network: str = "0g-testnet",
        registry_contract_address: Optional[str] = None,
        nft_contract_address: Optional[str] = None,
        openai_api_key: Optional[str] = None,
        encrypted: bool = True,
        # Override individual network components (for testing)
        _storage: Optional[StorageClient] = None,
        _compute: Optional[ComputeClient] = None,
        _da: Optional[DAClient] = None,
        _chain: Optional[ChainClient] = None,
    ):
        self.agent_id = agent_id
        self._private_key = private_key
        self._tree = MerkleTree()
        self._entries: list[dict] = []  # index of {blob_id, embedding, text}
        self._last_proof: Optional[QueryProof] = None

        self._index_path = pathlib.Path(f".ogmem_index_{agent_id}.json")
        self._load_index()

        self._encrypted = encrypted
        self._enc_key: Optional[bytes] = derive_encryption_key(private_key) if encrypted else None

        net: NetworkConfig = NETWORKS[network]

        self._storage = _storage or StorageClient(
            indexer_rpc=net.storage_indexer_rpc,
            flow_contract=net.flow_contract_address,
            private_key=private_key,
            chain_rpc=net.rpc_url,
        )
        self._compute = _compute or ComputeClient(
            serving_broker_url=net.serving_broker_url,
            openai_api_key=openai_api_key or os.environ.get("OPENAI_API_KEY"),
        )
        self._da = _da or DAClient(disperser_rpc=net.da_disperser_rpc)
        self._chain = _chain or ChainClient(
            rpc_url=net.rpc_url,
            private_key=private_key,
            registry_contract_address=registry_contract_address or _PLACEHOLDER_REGISTRY,
            nft_contract_address=nft_contract_address,
        )

    def add(self, text: str, metadata: dict | None = None) -> WriteReceipt:
        """Store a memory entry on 0g Storage and anchor its Merkle root on-chain."""
        timestamp = int(time.time())

        embedding = self._compute.embed(text)

        entry = {
            "agent_id": self.agent_id,
            "text": text,
            "embedding": embedding,
            "timestamp": timestamp,
            "metadata": metadata or {},
        }

        if self._encrypted and self._enc_key:
            blob_id = self._storage.upload_encrypted(entry, self._enc_key)
        else:
            blob_id = self._storage.upload(entry)

        self._tree.add_leaf(blob_id)
        merkle_root = self._tree.get_root()

        self._entries.append({
            "blob_id": blob_id,
            "embedding": embedding,
            "text": text,
            "timestamp": timestamp,
        })
        self._save_index()

        da_tx_hash = self._da.post_write_commitment(
            agent_id=self.agent_id,
            blob_id=blob_id,
            merkle_root=merkle_root,
            timestamp=timestamp,
        )

        chain_tx_hash = self._chain.update_root(
            merkle_root=merkle_root,
            da_tx_hash=da_tx_hash,
        )

        return WriteReceipt(
            agent_id=self.agent_id,
            blob_id=blob_id,
            merkle_root=merkle_root,
            da_tx_hash=da_tx_hash,
            chain_tx_hash=chain_tx_hash,
            timestamp=timestamp,
        )

    def query(self, text: str, top_k: int = 3) -> tuple[list[str], QueryProof]:
        """Search memory and return (results, proof). Proof includes Merkle paths + DA read log."""
        if not self._entries:
            return [], self._empty_proof(text)

        timestamp = int(time.time())
        query_hash = hashlib.sha256(text.encode()).hexdigest()

        query_vec = self._compute.embed(text)
        candidate_vecs = [e["embedding"] for e in self._entries]
        matches = self._compute.similarity_search(query_vec, candidate_vecs, top_k=top_k)

        results = []
        blob_ids = []
        scores = []
        merkle_proofs = []

        for idx, score in matches:
            entry = self._entries[idx]
            results.append(entry["text"])
            blob_ids.append(entry["blob_id"])
            scores.append(round(score, 6))
            try:
                mp = self._tree.get_proof(entry["blob_id"])
                merkle_proofs.append({
                    "leaf": mp.leaf,
                    "siblings": mp.siblings,
                    "directions": mp.directions,
                    "root": mp.root,
                })
            except ValueError:
                merkle_proofs.append({})

        merkle_root = self._tree.get_root()
        chain_state = self._chain.get_latest_root(self._chain.agent_address)
        chain_block = chain_state.block_number if chain_state else 0

        da_read_tx = self._da.post_read_commitment(
            agent_id=self.agent_id,
            query_hash=query_hash,
            blob_ids=blob_ids,
            scores=scores,
            merkle_root=merkle_root,
            timestamp=timestamp,
        )

        proof = QueryProof(
            agent_id=self.agent_id,
            query_hash=query_hash,
            blob_ids=blob_ids,
            scores=scores,
            merkle_proofs=merkle_proofs,
            merkle_root=merkle_root,
            da_read_tx=da_read_tx,
            chain_block=chain_block,
            timestamp=timestamp,
        )
        self._last_proof = proof
        return results, proof

    def last_proof(self) -> Optional[QueryProof]:
        """Return the proof from the most recent query()."""
        return self._last_proof

    def verify_proof(self, proof: QueryProof) -> bool:
        """Verify Merkle inclusion proofs and confirm the root matches the on-chain anchor."""
        from .merkle import MerkleTree, MerkleProof

        for blob_id, mp_dict in zip(proof.blob_ids, proof.merkle_proofs):
            if not mp_dict:
                return False
            if blob_id != mp_dict.get("leaf"):
                return False
            mp = MerkleProof(
                leaf=mp_dict["leaf"],
                siblings=mp_dict["siblings"],
                directions=mp_dict["directions"],
                root=mp_dict["root"],
            )
            if not MerkleTree.verify(mp):
                return False
            if mp.root != proof.merkle_root:
                return False

        on_chain = self._chain.get_historical_root(
            self._chain.agent_address,
            proof.chain_block,
        )
        if on_chain and on_chain.merkle_root != proof.merkle_root:
            return False

        return True

    def export_audit(self, from_block: int = 0, to_block: int = -1) -> AuditReport:
        """Reconstruct the agent's full memory history from 0g DA commitments."""
        history = self._da.fetch_agent_history(self.agent_id)
        history.sort(key=lambda x: x.get("timestamp", 0))

        operations = []
        total_writes = 0
        total_reads = 0
        from_timestamp = history[0]["timestamp"] if history else int(time.time())
        to_timestamp = history[-1]["timestamp"] if history else int(time.time())

        for event in history:
            if event["type"] == "memory_write":
                total_writes += 1
                if self._encrypted and self._enc_key:
                    blob = self._storage.download_encrypted(event["blob_id"], self._enc_key)
                else:
                    blob = self._storage.download(event["blob_id"])
                content_preview = (blob["text"][:100] + "...") if blob else "[unavailable]"
                operations.append(Operation(
                    op_type="write",
                    timestamp=event["timestamp"],
                    agent_id=self.agent_id,
                    blob_id=event["blob_id"],
                    content_preview=content_preview,
                    merkle_root=event["merkle_root"],
                    da_tx_hash=event.get("da_tx_hash"),
                ))
            elif event["type"] == "memory_read":
                total_reads += 1
                operations.append(Operation(
                    op_type="read",
                    timestamp=event["timestamp"],
                    agent_id=self.agent_id,
                    query_hash=event["query_hash"],
                    retrieved_blob_ids=event["blob_ids"],
                    similarity_scores=event["scores"],
                    merkle_root_used=event["merkle_root"],
                    da_read_tx=event.get("da_tx_hash"),
                ))

        chain_history = self._chain.get_all_roots(self._chain.agent_address)
        roots_history = [
            {
                "merkle_root": s.merkle_root,
                "block_number": s.block_number,
                "timestamp": s.timestamp,
            }
            for s in chain_history
        ]

        return AuditReport(
            agent_id=self.agent_id,
            from_block=from_block,
            to_block=to_block,
            from_timestamp=from_timestamp,
            to_timestamp=to_timestamp,
            total_writes=total_writes,
            total_reads=total_reads,
            operations=operations,
            merkle_roots_history=roots_history,
        )

    def mint_memory_nft(self) -> str:
        """Mint the caller's memory NFT on 0g Chain. Returns chain_tx_hash."""
        return self._chain.mint_memory_nft()

    def grant_access(
        self,
        agent_address: str,
        shard_blob_ids: list[str] | None = None,
    ) -> str:
        """Grant an agent access on-chain. Pass shard_blob_ids to limit scope. Returns chain_tx_hash."""
        return self._chain.grant_access(agent_address, shard_blob_ids)

    def revoke_access(self, agent_address: str) -> str:
        """Revoke all on-chain access for an agent. Returns chain_tx_hash."""
        return self._chain.revoke_access(agent_address)

    def check_access(self, agent_address: str, blob_id: str) -> bool:
        """Return True if agent_address has access to blob_id."""
        return self._chain.check_access(
            self._chain.agent_address,
            agent_address,
            blob_id,
        )

    def memory_token_id(self) -> int:
        """Return the on-chain NFT token ID for this wallet (0 if not minted)."""
        return self._chain.get_memory_token_id(self._chain.agent_address)

    @property
    def memory_variables(self) -> list[str]:
        return ["history"]

    def load_memory_variables(self, inputs: dict) -> dict:
        """LangChain hook — called before each chain invocation."""
        query = inputs.get("input", "")
        if not query:
            return {"history": ""}
        results, _ = self.query(query, top_k=5)
        return {"history": "\n".join(results)}

    def save_context(self, inputs: dict, outputs: dict) -> None:
        """LangChain hook — called after each chain invocation."""
        human = inputs.get("input", "")
        ai = outputs.get("response", outputs.get("output", ""))
        if human:
            self.add(f"Human: {human}")
        if ai:
            self.add(f"AI: {ai}")

    def clear(self) -> None:
        """Reset in-memory state. Does not delete blobs from 0g Storage."""
        self._tree = MerkleTree()
        self._entries = []
        self._last_proof = None

    def _load_index(self) -> None:
        if self._index_path.exists():
            try:
                data = json.loads(self._index_path.read_text())
                self._entries = data.get("entries", [])
                for entry in self._entries:
                    self._tree.add_leaf(entry["blob_id"])
            except Exception:
                self._entries = []

    def _save_index(self) -> None:
        self._index_path.write_text(json.dumps({"entries": self._entries}, indent=2))

    def _empty_proof(self, text: str) -> QueryProof:
        return QueryProof(
            agent_id=self.agent_id,
            query_hash=hashlib.sha256(text.encode()).hexdigest(),
            blob_ids=[],
            scores=[],
            merkle_proofs=[],
            merkle_root=self._tree.get_root(),
            da_read_tx="",
            chain_block=0,
        )


# Placeholder — replace with actual deployed contract address
_PLACEHOLDER_REGISTRY = "0x0000000000000000000000000000000000000001"
