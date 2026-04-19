"""Session-batched memory layer for 0g Mem.

Three-layer cache architecture:
  Layer 1 — Session Cache (RAM):  Working memory for the current session.
                                      Reads cached here after first fetch.
                                      Writes queued here — nothing hits 0g yet.
                                      Cost: FREE

  Layer 2 — Memory Index (0g Storage): Lightweight JSON: {blob_id, embedding, type, summary}
                                      Fetched once per session start.
                                      Searched locally for recall — free compute.
                                      Updated at session end — one write.

  Layer 3 — Memory Blobs (0g Storage): Full encrypted memory content.
                                        Only fetched when index search identifies relevance.
                                        Top-K targeted fetches only.
                                        Cost: near-free bandwidth, no gas.

Session lifecycle:
  session_start(session_id)
      └── fetch index from 0g Storage (1 read)
      └── load into RAM
      └── COST: ~1 tiny storage read

  [conversation happens]
      └── recall() → search index locally → fetch top-K blobs → FREE
      └── store() → queue in session_writes → NO 0g write yet → FREE

  session_end()
      └── if no writes → return immediately → COST: ZERO
      └── upload new blobs to 0g Storage (batch, parallel)
      └── build diff object → upload to 0g Storage
      └── update index → upload to 0g Storage
      └── ONE chain transaction → update memory root pointer
      └── ONE DA entry → Merkle root of session actions
      └── COST: N storage writes + 1 chain tx + 1 DA blob
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Optional

from .chain import ChainClient
from .compute import ComputeClient
from .config import NETWORKS, NetworkConfig
from .da import DAClient
from .encryption import derive_encryption_key
from .merkle import MerkleTree
from .proof import (
    AuditReport,
    MemoryBlob,
    MemoryDiff,
    MemoryIndex,
    MemoryType,
    MemoryVersion,
    Operation,
    QueryProof,
    WriteReceipt,
)
from .storage import StorageClient


# ---------------------------------------------------------------------------
# Levenshtein typo correction (free — no write)
# ---------------------------------------------------------------------------

def _levenshtein_distance(a: str, b: str) -> int:
    """Return the Levenshtein distance between two strings."""
    m, n = len(a), len(b)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            dp[i][j] = min(dp[i - 1][j] + 1, dp[i][j - 1] + 1, dp[i - 1][j - 1] + cost)
    return dp[m][n]


# ---------------------------------------------------------------------------
# Session memory write queue entry
# ---------------------------------------------------------------------------

@dataclass
class QueuedWrite:
    """A memory write queued during a session — committed at session_end."""
    write_id: str
    text: str
    memory_type: MemoryType
    embedding: list[float]
    metadata: dict = field(default_factory=dict)
    queued_at: int = field(default_factory=lambda: int(time.time()))

    @property
    def blob_id(self) -> str:
        return hashlib.sha256(self.text.encode()).hexdigest()


# ---------------------------------------------------------------------------
# SessionMemory — the session-batched memory client
# ---------------------------------------------------------------------------

class SessionMemory:
    """
    Session-batched memory client.

    Use this instead of (or alongside) VerifiableMemory when you want:
      - Free in-session reads (index search + targeted blob fetches)
      - Batched writes (one chain tx + one DA blob per session)
      - Structured memory types (episodic / semantic / procedural / working)
      - Git-style versioning (diffs + linked list of versions)

    The existing VerifiableMemory.add() and .query() still work — they write
    immediately and are useful for low-latency single-shot use cases.
    SessionMemory is designed for agent runtimes where many messages happen
    per session and cost efficiency matters.
    """

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
        self._encrypted = encrypted
        self._enc_key: Optional[bytes] = (
            derive_encryption_key(private_key) if encrypted else None
        )

        net: NetworkConfig = NETWORKS[network]

        self._storage = _storage or StorageClient(
            indexer_rpc=net.storage_indexer_rpc,
            flow_contract=net.flow_contract_address,
            private_key=private_key,
            chain_rpc=net.rpc_url,
        )
        self._compute = _compute or ComputeClient(
            serving_broker_url=net.serving_broker_url,
            openai_api_key=openai_api_key,
        )
        self._da = _da or DAClient(disperser_rpc=net.da_disperser_rpc)
        self._chain = _chain or ChainClient(
            rpc_url=net.rpc_url,
            private_key=private_key,
            registry_contract_address=(
                registry_contract_address
                or "0x0000000000000000000000000000000000000001"
            ),
            nft_contract_address=nft_contract_address,
        )

        # Session state — populated by session_start()
        self._session_id: Optional[str] = None
        self._session_started_at: int = 0

        # Layer 1: RAM cache — loaded at session_start
        self._index: Optional[MemoryIndex] = None
        self._index_cid: str = ""

        # Layer 3 blob cache: blob_id → deserialized blob (populated on demand)
        self._blob_cache: dict[str, dict] = {}

        # Local Merkle tree over all blob_ids (for proofs)
        self._tree = MerkleTree()

        # Session write queue — nothing sent to 0g until session_end
        self._write_queue: list[QueuedWrite] = []

        # Reads that happened this session (for audit)
        self._reads_this_session: list[dict] = []

    # ── Public API ────────────────────────────────────────────────────────────

    def session_start(self, session_id: str) -> MemoryIndex:
        """
        Start a new session. Loads the memory index from 0g Storage into RAM.

        Cost: 1 storage read (near-free). No chain tx.
        """
        self._reset_session()
        self._session_id = session_id
        self._session_started_at = int(time.time())

        # Try to load persisted index from 0g Storage
        index_data = self._load_index_from_storage()
        if index_data:
            self._index = MemoryIndex.from_dict(index_data)
        else:
            # Fresh start — no previous memory
            self._index = MemoryIndex(
                user_id=self.agent_id,
                version=0,
                entries=[],
            )

        # Rebuild Merkle tree from index entries
        for entry in self._index.entries:
            self._tree.add_leaf(entry.get("blob_id", ""))

        # DA log session start
        self._da.post_write_commitment(
            agent_id=self.agent_id,
            blob_id=f"session:{session_id}:start",
            merkle_root=self._tree.get_root(),
            timestamp=self._session_started_at,
        )

        return self._index

    def store(
        self,
        text: str,
        memory_type: MemoryType = MemoryType.EPISODIC,
        metadata: Optional[dict] = None,
    ) -> str:
        """
        Queue a memory write for the current session.
        Returns a write_id. Nothing is sent to 0g yet.

        Cost: FREE (RAM only)
        """
        self._require_session()

        # Typo correction — free, no write
        text = self._correct_typo(text)

        embedding = self._compute.embed(text)
        write_id = hashlib.sha256(
            f"{self._session_id}:{text}:{time.time_ns()}".encode()
        ).hexdigest()

        qw = QueuedWrite(
            write_id=write_id,
            text=text,
            memory_type=memory_type,
            embedding=embedding,
            metadata=metadata or {},
        )
        self._write_queue.append(qw)
        return write_id

    def recall(
        self,
        query: str,
        top_k: int = 5,
        memory_types: Optional[list[MemoryType]] = None,
    ) -> list[dict]:
        """
        Search memory using the local index and fetch top-K relevant blobs.

        Layer 1 (RAM): index search is FREE compute.
        Layer 3 (blob fetch): only top-K blobs fetched from 0g Storage.

        Returns: list of {blob_id, text, memory_type, score, created_at}
        """
        self._require_session()
        if not self._index:
            return []

        timestamp = int(time.time())
        query_hash = hashlib.sha256(query.encode()).hexdigest()

        # Embed query
        query_vec = self._compute.embed(query)

        # Filter entries by memory type
        candidates = [
            (i, e)
            for i, e in enumerate(self._index.entries)
            if memory_types is None
            or e.get("memory_type") in [t.value for t in memory_types]
        ]

        # Cosine similarity search against cached embeddings
        candidate_vecs = [e["embedding"] for _, e in candidates]
        matches = self._compute.similarity_search(query_vec, candidate_vecs, top_k=top_k)

        results = []
        blob_ids_found = []
        scores = []

        for idx, score in matches:
            entry = self._entries[idx]
            blob_id = entry["blob_id"]
            blob_ids_found.append(blob_id)
            scores.append(round(score, 6))

            # Fetch blob from Layer 3 if not cached
            blob = self._fetch_blob(blob_id)
            if blob:
                results.append({
                    "blob_id": blob_id,
                    "text": blob.get("text", entry.get("text", "")),
                    "memory_type": entry.get("memory_type", "episodic"),
                    "score": score,
                    "created_at": entry.get("created_at", 0),
                })
            else:
                # Fall back to index entry text if blob unavailable
                results.append({
                    "blob_id": blob_id,
                    "text": entry.get("text", ""),
                    "memory_type": entry.get("memory_type", "episodic"),
                    "score": score,
                    "created_at": entry.get("created_at", 0),
                })

        # Log read to DA (batchable — one entry at session end)
        self._reads_this_session.append({
            "type": "memory_read",
            "query_hash": query_hash,
            "blob_ids": blob_ids_found,
            "scores": scores,
            "timestamp": timestamp,
        })

        return results

    def session_end(self) -> MemoryVersion:
        """
        End the session: commit all queued writes to 0g Storage,
        update the index, anchor the Merkle root on-chain, post to DA.

        Cost: N blob uploads + 1 index upload + 1 chain tx + 1 DA blob
        """
        self._require_session()

        if not self._write_queue:
            # No writes — return empty version, no chain tx
            return MemoryVersion(
                version=(self._index.version if self._index else 0),
                user_id=self.agent_id,
                memory_root=self._tree.get_root(),
                index_cid=self._index_cid,
                diff_cid="",
            )

        now = int(time.time())
        prev_root = self._tree.get_root()
        prev_version = self._index.version if self._index else 0

        # Step 1: Upload new blob_ids to 0g Storage
        new_entries = []
        for qw in self._write_queue:
            blob_data = {
                "user_id": self.agent_id,
                "session_id": self._session_id,
                "items": [
                    {
                        "text": qw.text,
                        "memory_type": qw.memory_type.value,
                        "created_at": qw.queued_at,
                        "session_id": self._session_id,
                    }
                ],
                "embedding": qw.embedding,
                "memory_type": qw.memory_type.value,
                "created_at": qw.queued_at,
            }

            if self._encrypted and self._enc_key:
                blob_id = self._storage.upload_encrypted(blob_data, self._enc_key)
            else:
                blob_id = self._storage.upload(blob_data)

            self._tree.add_leaf(blob_id)
            new_entries.append({
                "blob_id": blob_id,
                "embedding": qw.embedding,
                "text": qw.text,
                "memory_type": qw.memory_type.value,
                "created_at": qw.queued_at,
                "session_id": self._session_id,
            })

        # Step 2: Build MemoryDiff and upload
        diff = MemoryDiff(
            user_id=self.agent_id,
            session_id=self._session_id,
            version=prev_version + 1,
            added=new_entries,
            updated=[],
            deleted=[],
        )
        diff_cid = self._storage.upload(diff.to_dict())

        # Step 3: Update index and upload
        new_version = prev_version + 1
        self._index = MemoryIndex(
            user_id=self.agent_id,
            version=new_version,
            entries=(self._index.entries if self._index else []) + new_entries,
            last_updated=now,
            prev_index_cid=self._index_cid,
        )
        index_cid = self._storage.upload(self._index.to_dict())
        self._index_cid = index_cid

        # Step 4: Anchor on chain — ONE transaction
        merkle_root = self._tree.get_root()
        da_tx_hash = self._da.post_write_commitment(
            agent_id=self.agent_id,
            blob_id=index_cid,
            merkle_root=merkle_root,
            timestamp=now,
        )
        chain_tx_hash = self._chain.update_root(
            merkle_root=merkle_root,
            da_tx_hash=da_tx_hash,
        )

        # Step 5: Post DA blob with session audit
        audit_blob = {
            "type": "session_audit",
            "session_id": self._session_id,
            "user_id": self.agent_id,
            "version": new_version,
            "reads": self._reads_this_session,
            "writes": [
                {
                    "write_id": qw.write_id,
                    "text": qw.text,
                    "memory_type": qw.memory_type.value,
                    "blob_id": new_entries[i]["blob_id"],
                }
                for i, qw in enumerate(self._write_queue)
            ],
            "merkle_root": merkle_root,
            "chain_tx_hash": chain_tx_hash,
            "started_at": self._session_started_at,
            "ended_at": now,
        }
        self._da._submit(audit_blob)

        version = MemoryVersion(
            version=new_version,
            user_id=self.agent_id,
            memory_root=merkle_root,
            index_cid=index_cid,
            diff_cid=diff_cid,
            prev_version_root=prev_root,
            timestamp=now,
        )

        self._write_queue.clear()
        self._reads_this_session.clear()

        return version

    def get_index(self) -> Optional[MemoryIndex]:
        """Return the current in-memory index."""
        return self._index

    @property
    def _entries(self) -> list[dict]:
        """Compatibility shim — used by recall() to iterate index entries."""
        return self._index.entries if self._index else []

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _require_session(self) -> None:
        if not self._session_id:
            raise RuntimeError(
                "No active session. Call session_start(session_id) first."
            )

    def _reset_session(self) -> None:
        self._session_id = None
        self._session_started_at = 0
        self._index = None
        self._index_cid = ""
        self._blob_cache.clear()
        self._tree = MerkleTree()
        self._write_queue.clear()
        self._reads_this_session.clear()

    def _load_index_from_storage(self) -> Optional[dict]:
        """Try to load the latest index CID from chain, then fetch blob."""
        try:
            state = self._chain.get_latest_root(self._chain.agent_address)
            if not state:
                return None
            # The last blob_id stored was the index — stored as blob_id in latest entry
            # We need to look at DA history to find the last index_cid
            # For now, try fetching from the chain state's da_tx_hash
            # This is a simplification — a full implementation would
            # store the index_cid explicitly in a separate field
            history = self._da.fetch_agent_history(self.agent_id)
            write_entries = [
                e for e in history
                if e.get("type") == "memory_write"
            ]
            if not write_entries:
                return None
            last_entry = sorted(write_entries, key=lambda x: x.get("timestamp", 0))[-1]
            blob_id = last_entry.get("blob_id", "")
            if not blob_id:
                return None
            if self._encrypted and self._enc_key:
                return self._storage.download_encrypted(blob_id, self._enc_key)
            return self._storage.download(blob_id)
        except Exception:
            return None

    def _fetch_blob(self, blob_id: str) -> Optional[dict]:
        """Fetch a blob from Layer 3 (0g Storage), with in-memory cache."""
        if blob_id in self._blob_cache:
            return self._blob_cache[blob_id]

        try:
            if self._encrypted and self._enc_key:
                blob = self._storage.download_encrypted(blob_id, self._enc_key)
            else:
                blob = self._storage.download(blob_id)
            if blob:
                self._blob_cache[blob_id] = blob
            return blob
        except Exception:
            return None

    def _correct_typo(self, text: str) -> str:
        """
        Detect and correct typos via Levenshtein distance.
        Applied to queued writes only — free, no extra cost.
        """
        if not self._index:
            return text
        words = text.split()
        corrected = []
        for word in words:
            best_match = word
            min_dist = float("inf")
            for entry in self._index.entries:
                entry_text = entry.get("text", "")
                entry_words = entry_text.split()
                for ew in entry_words:
                    d = _levenshtein_distance(word.lower(), ew.lower())
                    if d < min_dist and d <= 4 and d > 0:
                        min_dist = d
                        best_match = ew
            corrected.append(best_match)
        return " ".join(corrected)
