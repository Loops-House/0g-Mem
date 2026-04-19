"""Shared WebSocket message protocol for 0g Mem.

This module defines the wire protocol between:
  - Telegram / Desktop clients and the Agent Runtime
  - Agent Runtime and the Memory WebSocket API

Both teams should import from this module and treat it as immutable during the hackathon.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Literal, Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class MemoryType(str, Enum):
    """Four memory types that structure agent memory."""
    EPISODIC    = "episodic"     # Things that happened — events, conversations
    SEMANTIC    = "semantic"     # Things the agent knows about the user — preferences, facts
    PROCEDURAL  = "procedural"   # How the user likes things done — workflows, habits
    WORKING     = "working"      # Current task context — active goal, mid-task state


class AgentMode(str, Enum):
    """Agent operating modes (Desktop app)."""
    ASSISTANT = "assistant"  # General purpose
    CODING    = "coding"     # File access, code execution, diffs
    RESEARCH  = "research"   # Web search, research synthesis


class Channel(str, Enum):
    """Frontend channel that initiated the session."""
    TELEGRAM = "telegram"
    DESKTOP  = "desktop"


# ---------------------------------------------------------------------------
# Client → Agent Runtime  (Telegram / Desktop WebSocket)
# ---------------------------------------------------------------------------

@dataclass
class MsgSessionStart:
    """Client → Agent Runtime: begin a new session."""
    type: Literal["session_start"] = "session_start"
    session_id: str          # Stable ID for this session (e.g. f"{user_id}_{hour_timestamp}")
    user_id: str             # Wallet address of the user
    channel: Channel         # Which frontend initiated this
    mode: AgentMode = AgentMode.ASSISTANT  # Operating mode for this session

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, raw: str) -> "MsgSessionStart":
        return cls(**json.loads(raw))


@dataclass
class MsgUserMessage:
    """Client → Agent Runtime: a single user message in a session."""
    type: Literal["message"] = "message"
    session_id: str
    text: str
    mode: AgentMode = AgentMode.ASSISTANT

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, raw: str) -> "MsgUserMessage":
        return cls(**json.loads(raw))


@dataclass
class MsgSessionEnd:
    """Client → Agent Runtime: explicitly end a session early (optional — session also ends on timeout)."""
    type: Literal["session_end"] = "session_end"
    session_id: str

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, raw: str) -> "MsgSessionEnd":
        return cls(**json.loads(raw))


# ---------------------------------------------------------------------------
# Agent Runtime → Client  (Telegram / Desktop WebSocket)
# ---------------------------------------------------------------------------

@dataclass
class MsgMemoryRetrieved:
    """Agent Runtime → Client: memory context that was loaded for this turn."""
    type: Literal["memory_retrieved"] = "memory_retrieved"
    memories: list[dict]   # [{blob_id, text, memory_type, score, created_at}, ...]
    count: int = 0

    def __post_init__(self):
        self.count = len(self.memories)

    def to_json(self) -> str:
        return json.dumps(asdict(self))


@dataclass
class MsgToolCall:
    """Agent Runtime → Client: an agent tool is being executed."""
    type: Literal["tool_call"] = "tool_call"
    tool: str           # Tool name e.g. "web_search"
    input: str          # What the agent passed to the tool
    result: Optional[str] = None  # Filled when tool completes
    status: Literal["pending", "done", "error"] = "pending"

    def to_json(self) -> str:
        return json.dumps(asdict(self))


@dataclass
class MsgAgentResponse:
    """Agent Runtime → Client: a final text response."""
    type: Literal["response"] = "response"
    text: str
    memories_written: int = 0   # How many memories were queued for this turn
    tool_calls: int = 0        # How many tool calls were made
    session_id: str = ""

    def to_json(self) -> str:
        return json.dumps(asdict(self))


@dataclass
class MsgError:
    """Agent Runtime → Client: something went wrong."""
    type: Literal["error"] = "error"
    message: str
    code: Optional[str] = None

    def to_json(self) -> str:
        return json.dumps(asdict(self))


# ---------------------------------------------------------------------------
# Agent Runtime → Memory API  (WebSocket to memory service)
# ---------------------------------------------------------------------------

@dataclass
class MemRetrieveRequest:
    """Agent Runtime → Memory: fetch relevant memories for a query."""
    type: Literal["mem_retrieve"] = "mem_retrieve"
    user_id: str
    session_id: str
    query: str
    top_k: int = 5
    memory_types: Optional[list[MemoryType]] = None  # Filter by type, None = all

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, raw: str) -> "MemRetrieveRequest":
        return cls(**json.loads(raw))


@dataclass
class MemQueueWrite:
    """Agent Runtime → Memory: queue a memory to be written at session end."""
    type: Literal["mem_queue_write"] = "mem_queue_write"
    user_id: str
    session_id: str
    text: str
    memory_type: MemoryType = MemoryType.EPISODIC
    metadata: Optional[dict] = None

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, raw: str) -> "MemQueueWrite":
        return cls(**json.loads(raw))


@dataclass
class MemSessionStart:
    """Agent Runtime → Memory: initialize session state from persisted index."""
    type: Literal["mem_session_start"] = "mem_session_start"
    user_id: str
    session_id: str

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, raw: str) -> "MemSessionStart":
        return cls(**json.loads(raw))


@dataclass
class MemSessionEnd:
    """Agent Runtime → Memory: commit all queued writes, update index, anchor on chain."""
    type: Literal["mem_session_end"] = "mem_session_end"
    user_id: str
    session_id: str

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, raw: str) -> "MemSessionEnd":
        return cls(**json.loads(raw))


# ---------------------------------------------------------------------------
# Memory API → Agent Runtime  (WebSocket response from memory service)
# ---------------------------------------------------------------------------

@dataclass
class MemRetrieveResponse:
    """Memory → Agent Runtime: result of a mem_retrieve request."""
    type: Literal["mem_retrieve_response"] = "mem_retrieve_response"
    memories: list[dict]    # [{blob_id, text, memory_type, score, created_at}, ...]
    count: int = 0
    latency_ms: int = 0

    def __post_init__(self):
        self.count = len(self.memories)

    @classmethod
    def from_json(cls, raw: str) -> "MemRetrieveResponse":
        return cls(**json.loads(raw))


@dataclass
class MemWriteQueued:
    """Memory → Agent Runtime: confirm a write was queued."""
    type: Literal["mem_write_queued"] = "mem_write_queued"
    write_id: str        # Internal ID for this queued write
    memory_type: MemoryType
    queued_at: int = 0

    @classmethod
    def from_json(cls, raw: str) -> "MemWriteQueued":
        return cls(**json.loads(raw))


@dataclass
class MemSessionSummary:
    """Memory → Agent Runtime: result of session_end — what was committed."""
    type: Literal["mem_session_summary"] = "mem_session_summary"
    session_id: str
    writes_committed: int = 0
    merkle_root: str = ""
    chain_tx_hash: str = ""
    da_tx_hash: str = ""
    index_cid: str = ""    # CID of updated index on 0g Storage
    version: int = 0

    @classmethod
    def from_json(cls, raw: str) -> "MemSessionSummary":
        return cls(**json.loads(raw))


# ---------------------------------------------------------------------------
# Session Action Log (for DA logging — written by Agent Runtime)
# ---------------------------------------------------------------------------

@dataclass
class SessionAction:
    """A single action within a session — used to build the DA audit blob."""
    action_type: Literal["memory_retrieve", "inference", "tool_call", "memory_write", "session_start", "session_end"]
    timestamp: int = 0
    details: dict = None

    def __post_init__(self):
        if self.timestamp == 0:
            self.timestamp = int(time.time())
        if self.details is None:
            self.details = {}

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SessionAuditBlob:
    """Full session audit blob posted to 0g DA at session end."""
    session_id: str
    user_id: str
    channel: str
    agent_mode: str
    version: int
    merkle_root: str       # Memory Merkle root at session end
    da_tx_hash: str        # DA blob hash
    chain_tx_hash: str     # On-chain root anchor
    actions: list[SessionAction]
    started_at: int = 0
    ended_at: int = 0
    memories_written: int = 0
    memories_retrieved: int = 0
    tool_calls: int = 0

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    @classmethod
    def from_json(cls, raw: str) -> "SessionAuditBlob":
        return cls(**json.loads(raw))
