"""Proof data structures for 0g Mem."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict, field
from enum import Enum
from typing import Optional

from .merkle import MerkleProof


# ---------------------------------------------------------------------------
# Enums (mirrored in protocol.py for the WebSocket API)
# ---------------------------------------------------------------------------

class MemoryType(str, Enum):
    """Four memory types that structure agent memory."""
    EPISODIC   = "episodic"
    SEMANTIC   = "semantic"
    PROCEDURAL = "procedural"
    WORKING    = "working"


# ---------------------------------------------------------------------------
# Session-batched memory data structures
# ---------------------------------------------------------------------------

@dataclass
class MemoryBlob:
    """
    A single encrypted memory entry stored on 0g Storage.
    One blob may contain one or more typed memory items.
    """
    blob_id: str                  # Content hash on 0g Storage
    user_id: str
    items: list[dict]             # [{text, memory_type, created_at, session_id}, ...]
    embedding: list[float]         # For semantic search (dim=384)
    memory_type: str              # Primary type: episodic|semantic|procedural|working
    session_id: str
    created_at: int = field(default_factory=lambda: int(time.time()))

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "MemoryBlob":
        return cls(**d)


@dataclass
class MemoryIndex:
    """
    Lightweight search index for a user's memory — stored as a single blob on 0g Storage.
    Fetched once per session. Searched locally. Updated at session end.
    """
    user_id: str
    version: int
    entries: list[dict]           # [{blob_id, embedding, text, memory_type, created_at, session_id}, ...]
    last_updated: int = field(default_factory=lambda: int(time.time()))
    prev_index_cid: str = ""       # For git-style linked history

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "MemoryIndex":
        return cls(**d)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


@dataclass
class MemoryDiff:
    """
    Git-style diff between two memory versions.
    Stored on 0g Storage as a historical record.
    """
    user_id: str
    session_id: str
    version: int
    added: list[dict]             # Full blob data for new entries
    updated: list[tuple[str, dict]]  # [(old_blob_id, new_blob_data), ...]
    deleted: list[str]            # blob_ids that were removed
    timestamp: int = field(default_factory=lambda: int(time.time()))

    def to_dict(self) -> dict:
        d = asdict(self)
        d["updated"] = [(a, b) for a, b in self.updated]  # tuples not serializable
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


@dataclass
class MemoryVersion:
    """
    Points to the current state of a user's memory at a point in time.
    The memory_root (Merkle root) is anchored on 0g Chain.
    The index_cid and diff_cid point to blobs on 0g Storage.
    """
    version: int
    user_id: str
    memory_root: str              # Merkle root of all current blob_ids
    index_cid: str                # CID of the MemoryIndex blob
    diff_cid: str                 # CID of the MemoryDiff blob (empty for v1)
    prev_version_root: str = ""   # Previous memory_root (for linked list traversal)
    timestamp: int = field(default_factory=lambda: int(time.time()))

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


# ---------------------------------------------------------------------------
# Write Receipt
# ---------------------------------------------------------------------------

@dataclass
class WriteReceipt:
    """Returned after a successful memory write."""
    agent_id: str
    blob_id: str           # 0g Storage content hash (root hash)
    merkle_root: str       # Updated Merkle root after this write
    da_tx_hash: str        # 0g DA transaction hash (immutable write log)
    chain_tx_hash: str     # 0g Chain transaction hash (root anchor)
    timestamp: int = field(default_factory=lambda: int(time.time()))

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


@dataclass
class QueryProof:
    """Cryptographic proof of a memory retrieval event, verifiable against 0g Chain + DA."""
    agent_id: str
    query_hash: str            # sha256(query_text)
    blob_ids: list[str]
    scores: list[float]
    merkle_proofs: list[dict]  # inclusion proof per blob_id
    merkle_root: str           # root at query time, anchored on-chain
    da_read_tx: str            # DA tx hash of this retrieval
    chain_block: int           # block where root was anchored
    timestamp: int = field(default_factory=lambda: int(time.time()))

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    @classmethod
    def from_json(cls, data: str) -> "QueryProof":
        return cls(**json.loads(data))


@dataclass
class Operation:
    """A single read or write event in the audit log."""
    op_type: str          # "write" or "read"
    timestamp: int
    agent_id: str

    # Write fields
    blob_id: Optional[str] = None
    content_preview: Optional[str] = None   # first 100 chars of memory text
    merkle_root: Optional[str] = None
    da_tx_hash: Optional[str] = None
    chain_tx_hash: Optional[str] = None

    # Read fields
    query_preview: Optional[str] = None     # first 100 chars of query
    query_hash: Optional[str] = None
    retrieved_blob_ids: Optional[list] = None
    similarity_scores: Optional[list] = None
    da_read_tx: Optional[str] = None
    merkle_root_used: Optional[str] = None


@dataclass
class AuditReport:
    """Full audit report covering all memory reads and writes for an agent."""
    agent_id: str
    from_block: int
    to_block: int
    from_timestamp: int
    to_timestamp: int
    total_writes: int
    total_reads: int
    operations: list[Operation]
    merkle_roots_history: list[dict]
    eu_ai_act_compliant: bool = True
    eu_ai_act_articles: list[str] = field(
        default_factory=lambda: ["Article 12 - Logging", "Article 13 - Transparency"]
    )
    generated_at: int = field(default_factory=lambda: int(time.time()))

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    def summary(self) -> str:
        return (
            f"Agent: {self.agent_id}\n"
            f"Period: block {self.from_block} → {self.to_block}\n"
            f"Writes: {self.total_writes} | Reads: {self.total_reads}\n"
            f"EU AI Act Article 12 Compliant: {self.eu_ai_act_compliant}\n"
            f"Verifiable by: anyone with 0g Chain + DA access"
        )
