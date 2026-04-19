"""0g Mem Agent Runtime — ReAct orchestration loop.

Every message goes through:
  1. Memory retrieval via WebSocket (memory team handles session batching)
  2. 0g Compute inference (with fallback chain)
  3. ReAct tool-calling loop
  4. Session end → memory team commits, DA logs the full trace

Inference uses the 0g Compute Network. Two options:

  OPTION A — Local proxy (recommended for demo):
    1. Install: pnpm add @0glabs/0g-serving-broker -g
    2. Serve locally: 0g-compute-cli inference serve --provider <PROVIDER_ADDR> --port 3000
    3. Set env: OG_COMPUTE_LOCAL_PROXY=http://localhost:3000

  OPTION B — Direct API key:
    1. Get secret: 0g-compute-cli inference get-secret --provider <PROVIDER_ADDR>
    2. Get service URL from: 0g-compute-cli inference list-providers
    3. Set env: OG_COMPUTE_API_KEY=app-sk-... and OG_COMPUTE_SERVICE_URL=https://...

  Fallbacks (tried in order if 0g is unavailable):
    1. OpenAI (if OPENAI_API_KEY is set)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any, Literal, Optional

import httpx
import websockets

import protocol as p
from agent.tools import ToolRegistry, ToolResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Inference Client
# ---------------------------------------------------------------------------

@dataclass
class InferenceConfig:
    """Configuration for an inference endpoint (0g Compute, OpenAI, etc.)."""
    base_url: str       # e.g. "http://localhost:3000" or "https://api.openai.com/v1"
    model: str          # e.g. "qwen-2.5-7b-instruct" or "gpt-4o-mini"
    api_key: Optional[str] = None
    timeout_seconds: int = 120


@dataclass
class InferenceResult:
    """Parsed result from an inference call."""
    content: str
    tool_calls: list[dict]   # [{name, arguments: dict}, ...]
    finish_reason: str


class InferenceClient:
    """
    Calls 0g Compute (via local proxy or direct API key) with OpenAI fallback.

    0g Compute is the primary inference backend — it's decentralized, TEE-verified,
    and fits the "every component runs on 0g" architecture story.

    Two 0g setup options:
      A) Local proxy: 0g-compute-cli inference serve --provider <ADDR>
         → sets OG_COMPUTE_LOCAL_PROXY=http://localhost:3000
      B) Direct API key: 0g-compute-cli inference get-secret --provider <ADDR>
         → sets OG_COMPUTE_API_KEY=app-sk-... + OG_COMPUTE_SERVICE_URL=https://...
    """

    # 0g testnet chatbot model
    OG_MODEL = "qwen-2.5-7b-instruct"

    def __init__(self, config: InferenceConfig | None = None):
        self._primary_config = config  # set if 0g is configured
        self._fallbacks: list[InferenceConfig] = self._build_fallbacks()

    def _build_fallbacks(self) -> list[InferenceConfig]:
        fallbacks = []

        # OpenAI fallback
        openai_key = os.environ.get("OPENAI_API_KEY")
        if openai_key:
            fallbacks.append(InferenceConfig(
                base_url="https://api.openai.com/v1",
                model="gpt-4o-mini",
                api_key=openai_key,
            ))

        return fallbacks

    def _get_0g_config(self) -> Optional[InferenceConfig]:
        """
        Build an InferenceConfig for 0g Compute.

        Checks two env var patterns:
          1. OG_COMPUTE_LOCAL_PROXY  — local CLI proxy (e.g. http://localhost:3000)
          2. OG_COMPUTE_SERVICE_URL + OG_COMPUTE_API_KEY — direct API key access
        """
        local_proxy = os.environ.get("OG_COMPUTE_LOCAL_PROXY", "").strip()
        if local_proxy:
            return InferenceConfig(
                base_url=local_proxy,
                model=self.OG_MODEL,
                api_key=None,  # local proxy needs no auth
            )

        service_url = os.environ.get("OG_COMPUTE_SERVICE_URL", "").strip()
        api_key = os.environ.get("OG_COMPUTE_API_KEY", "").strip()
        if service_url and api_key:
            return InferenceConfig(
                base_url=f"{service_url}/v1/proxy",
                model=self.OG_MODEL,
                api_key=api_key,
            )

        return None

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict],
        tool_choice: str = "auto",
        max_turns: int = 5,
    ) -> InferenceResult:
        """
        Send a chat request. Tries 0g Compute first, then each fallback.
        """
        candidates: list[InferenceConfig] = []

        config = self._get_0g_config()
        if config:
            candidates.append(config)
        candidates.extend(self._fallbacks)

        if not candidates:
            raise RuntimeError(
                "No inference backend configured. Set either:\n"
                "  OG_COMPUTE_LOCAL_PROXY=http://localhost:3000  (run: 0g-compute-cli inference serve --provider <ADDR>)\n"
                "  or OG_COMPUTE_SERVICE_URL + OG_COMPUTE_API_KEY  (from: 0g-compute-cli inference get-secret --provider <ADDR>)\n"
                "  or OPENAI_API_KEY for fallback"
            )

        last_error = ""
        for candidate in candidates:
            try:
                return await self._call(candidate, messages, tools, tool_choice)
            except Exception as exc:
                last_error = f"{candidate.base_url}: {exc}"
                logger.warning("Inference fallback failed: %s", last_error)
                continue

        raise RuntimeError(f"All inference backends failed. Last error: {last_error}")

    async def _call(
        self,
        config: InferenceConfig,
        messages: list[dict],
        tools: list[dict],
        tool_choice: str,
    ) -> InferenceResult:
        """Make a single inference call to the given config's endpoint."""
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if config.api_key:
            headers["Authorization"] = f"Bearer {config.api_key}"

        payload: dict[str, Any] = {
            "model": config.model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 2048,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice

        async with httpx.AsyncClient(timeout=httpx.Timeout(config.timeout_seconds)) as client:
            url = f"{config.base_url.rstrip('/')}/chat/completions"
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        choice = data["choices"][0]
        finish_reason = choice.get("finish_reason", "stop")
        content = choice.get("message", {}).get("content", "") or ""

        tool_calls_raw = choice.get("message", {}).get("tool_calls", []) or []

        tool_calls = []
        for tc in tool_calls_raw:
            fn = tc.get("function", {})
            try:
                arguments = json.loads(fn.get("arguments", "{}"))
            except json.JSONDecodeError:
                arguments = {"raw": fn.get("arguments", "")}
            tool_calls.append({
                "name": fn.get("name", ""),
                "arguments": arguments,
            })

        return InferenceResult(
            content=content,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
        )

    def check_0g_status(self) -> dict[str, Any]:
        """
        Check if 0g Compute is configured and reachable.
        Returns a status dict for debugging/setup UI.
        """
        config = self._get_0g_config()
        if not config:
            return {
                "status": "not_configured",
                "message": (
                    "0g Compute not configured. Set one of:\n"
                    "  OG_COMPUTE_LOCAL_PROXY=http://localhost:3000\n"
                    "  OG_COMPUTE_SERVICE_URL + OG_COMPUTE_API_KEY\n"
                    "See: https://docs.0g.ai/developer-hub/building-on-0g/compute-network/inference"
                ),
                "how_to_setup": [
                    "1. Install: pnpm add @0glabs/0g-serving-broker -g",
                    "2. Fund: 0g-compute-cli deposit --amount 10",
                    "3. Transfer to provider: 0g-compute-cli transfer-fund --provider <ADDR> --amount 1",
                    "4a. Local proxy (easy): 0g-compute-cli inference serve --provider <ADDR> --port 3000",
                    "   → Set env: OG_COMPUTE_LOCAL_PROXY=http://localhost:3000",
                    "4b. Direct API: 0g-compute-cli inference get-secret --provider <ADDR>",
                    "   → Set env: OG_COMPUTE_SERVICE_URL=https://... OG_COMPUTE_API_KEY=app-sk-...",
                ],
            }

        # Try a minimal health check
        try:
            import socket
            if "localhost" in config.base_url:
                # Local proxy — check if port is open
                host = config.base_url.split("://")[1].split(":")[0]
                port = 3000
                if ":" in config.base_url:
                    port = int(config.base_url.split(":")[-1].split("/")[0])
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                result = sock.connect_ex((host, port))
                sock.close()
                if result == 0:
                    return {"status": "ready", "backend": "0g_compute", "endpoint": config.base_url}
                else:
                    return {
                        "status": "proxy_not_running",
                        "message": f"Local proxy not reachable at {config.base_url}",
                        "hint": "Run: 0g-compute-cli inference serve --provider <PROVIDER_ADDR> --port 3000",
                    }
            return {"status": "configured", "backend": "0g_compute", "endpoint": config.base_url}
        except Exception as exc:
            return {"status": "unknown", "error": str(exc)}


# ---------------------------------------------------------------------------
# DA Logger
# ---------------------------------------------------------------------------

class DALogger:
    """
    Posts session audit blobs to 0g DA via the existing DAClient in ogmem.
    Falls back to local logging if DA is unavailable.
    """

    def __init__(self, private_key: str):
        self._private_key = private_key
        self._da_client = None  # Lazily initialized

    def _get_da_client(self):
        if self._da_client is None:
            from ogmem.da import DAClient
            from ogmem.config import NETWORKS
            net = NETWORKS["0g-testnet"]
            self._da_client = DAClient(disperser_rpc=net.da_disperser_rpc)
        return self._da_client

    def log_session(self, audit_blob: p.SessionAuditBlob) -> str:
        """Submit the full session audit blob to 0g DA."""
        blob_bytes = audit_blob.to_json().encode()
        da_client = self._get_da_client()

        # Use local fallback if gRPC is not available
        da_tx_hash = da_client._submit({
            "type": "session_audit",
            "session_id": audit_blob.session_id,
            "user_id": audit_blob.user_id,
            "channel": audit_blob.channel,
            "agent_mode": audit_blob.agent_mode,
            "version": audit_blob.version,
            "merkle_root": audit_blob.merkle_root,
            "chain_tx_hash": audit_blob.chain_tx_hash,
            "actions": [a.to_dict() for a in audit_blob.actions],
            "started_at": audit_blob.started_at,
            "ended_at": audit_blob.ended_at,
            "memories_written": audit_blob.memories_written,
            "memories_retrieved": audit_blob.memories_retrieved,
            "tool_calls": audit_blob.tool_calls,
        })
        return da_tx_hash


# ---------------------------------------------------------------------------
# Memory WebSocket Client
# ---------------------------------------------------------------------------

class MemoryWSClient:
    """
    WebSocket client for communicating with the memory service WebSocket API.
    The agent runtime uses this to retrieve memories and queue writes.
    """

    def __init__(self, memory_ws_url: str, private_key: str):
        self.memory_ws_url = memory_ws_url.rstrip("/")
        self._private_key = private_key
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._pending_futures: dict[str, asyncio.Future] = {}

    async def connect(self) -> None:
        """Connect and authenticate via wallet signature."""
        import hashlib
        import time

        nonce = str(int(time.time()))
        msg = f"0g Mem session auth: {nonce}"
        from web3 import Web3
        w3 = Web3()
        account = w3.eth.account.from_key(self._private_key)
        signature = account.sign_message(message=msg).signature.hex()

        self._ws = await websockets.connect(
            f"{self.memory_ws_url}/memory/session/{account.address}",
            extra_headers={
                "X-Wallet-Address": account.address,
                "X-Nonce": nonce,
                "X-Signature": signature,
            ],
        )

    async def disconnect(self) -> None:
        if self._ws:
            await self._ws.close()
            self._ws = None

    async def session_start(self, user_id: str, session_id: str, channel: str) -> None:
        msg = p.MsgSessionStart(
            session_id=session_id,
            user_id=user_id,
            channel=p.Channel(channel),
        ).to_json()
        await self._ws.send(msg)

    async def retrieve_memories(
        self,
        user_id: str,
        session_id: str,
        query: str,
        top_k: int = 5,
    ) -> list[dict]:
        """Request relevant memories and wait for the response."""
        req = p.MemRetrieveRequest(
            user_id=user_id,
            session_id=session_id,
            query=query,
            top_k=top_k,
        )
        await self._ws.send(req.to_json())

        # Wait for response
        resp_raw = await self._ws.recv()
        resp = p.MemRetrieveResponse.from_json(resp_raw)
        return resp.memories

    async def queue_write(
        self,
        user_id: str,
        session_id: str,
        text: str,
        memory_type: str,
        metadata: Optional[dict] = None,
    ) -> None:
        req = p.MemQueueWrite(
            user_id=user_id,
            session_id=session_id,
            text=text,
            memory_type=p.MemoryType(memory_type),
            metadata=metadata,
        )
        await self._ws.send(req.to_json())

    async def session_end(self, user_id: str, session_id: str) -> p.MemSessionSummary:
        req = p.MemSessionEnd(user_id=user_id, session_id=session_id)
        await self._ws.send(req.to_json())
        resp_raw = await self._ws.recv()
        return p.MemSessionSummary.from_json(resp_raw)


# ---------------------------------------------------------------------------
# Agent Loop
# ---------------------------------------------------------------------------

@dataclass
class AgentConfig:
    """Configuration for the agent loop."""
    memory_ws_url: str = "ws://localhost:8000"
    max_tool_calls: int = 5
    max_reasoning_turns: int = 3
    default_top_k: int = 5


@dataclass
class AgentTurn:
    """A single agent turn — user message + agent response + tool calls."""
    user_message: str
    mode: str = "assistant"
    response_text: str = ""
    tool_results: list[ToolResult] = field(default_factory=list)
    memories_retrieved: int = 0
    memories_written: int = 0
    tool_call_count: int = 0
    error: str | None = None


class AgentLoop:
    """
    The main agent orchestration loop.

    For each incoming user message:
      1. Retrieve relevant memories from memory service (via WebSocket)
      2. Build system prompt with memory context
      3. Run ReAct loop: inference → tool calls → observe → repeat
      4. Queue memories for writing (memory team handles batching)
      5. Log full session trace to 0g DA (at session end)
    """

    def __init__(
        self,
        private_key: str,
        config: AgentConfig | None = None,
        tool_registry: ToolRegistry | None = None,
    ):
        self._private_key = private_key
        self.config = config or AgentConfig()
        self._tools = tool_registry or ToolRegistry()
        self._inference = InferenceClient()
        self._da_logger = DALogger(private_key)
        self._ws: Optional[MemoryWSClient] = None

        # Session state
        self._active_session_id: str | None = None
        self._active_user_id: str | None = None
        self._active_channel: str = "desktop"
        self._active_mode: str = "assistant"
        self._session_actions: list[p.SessionAction] = []
        self._session_started_at: int = 0
        self._turns: list[AgentTurn] = []

    # ---- Public API ----

    async def handle_message(
        self,
        user_id: str,
        session_id: str,
        text: str,
        channel: str = "desktop",
        mode: str = "assistant",
    ) -> AgentTurn:
        """
        Handle a single user message within a session.
        Returns an AgentTurn with the response and metadata.
        """
        turn = AgentTurn(user_message=text, mode=mode)

        # Lazy-connect to memory WebSocket
        if self._ws is None:
            from ogmem.config import NETWORKS
            net = NETWORKS["0g-testnet"]
            self._ws = MemoryWSClient(
                memory_ws_url=f"ws://localhost:8000",  # Will be overridden by memory team
                private_key=self._private_key,
            )
            try:
                await self._ws.connect()
            except Exception as exc:
                logger.warning("Could not connect to memory WS: %s — running without memory", exc)
                self._ws = None

        # Start session if needed
        if session_id != self._active_session_id:
            await self._start_session(user_id, session_id, channel, mode)
            self._active_session_id = session_id
            self._active_user_id = user_id

        self._active_mode = mode

        try:
            # Step 1: Retrieve memories
            memories = []
            if self._ws:
                try:
                    memories = await self._ws.retrieve_memories(
                        user_id=user_id,
                        session_id=session_id,
                        query=text,
                        top_k=self.config.default_top_k,
                    )
                except Exception as exc:
                    logger.warning("Memory retrieval failed: %s", exc)

            turn.memories_retrieved = len(memories)

            # Step 2: Build messages for inference
            messages = self._build_messages(text, memories, mode)

            # Step 3: ReAct loop
            response_text, tool_results = await self._react_loop(messages, turn)

            turn.response_text = response_text
            turn.tool_results = tool_results
            turn.tool_call_count = len(tool_results)

            # Step 4: Queue memories from this turn
            if self._ws:
                try:
                    await self._queue_turn_memories(user_id, session_id, text, response_text, memories)
                except Exception as exc:
                    logger.warning("Memory queue failed: %s", exc)

        except Exception as exc:
            logger.exception("Agent turn failed")
            turn.error = str(exc)
            turn.response_text = f"An error occurred: {exc}"

        self._turns.append(turn)
        return turn

    async def end_session(self, user_id: str, session_id: str) -> p.SessionAuditBlob | None:
        """End the session: tell memory service to commit, log to DA."""
        if self._ws and self._active_session_id == session_id:
            try:
                summary = await self._ws.session_end(user_id, session_id)
                # Log to DA
                audit = self._build_audit_blob(session_id, user_id, summary)
                da_tx = self._da_logger.log_session(audit)
                logger.info("Session %s logged to DA: %s", session_id, da_tx)
                await self._ws.disconnect()
                self._ws = None
                return audit
            except Exception as exc:
                logger.warning("Session end failed: %s", exc)
        self._reset_session()
        return None

    # ---- Internal methods ----

    async def _start_session(
        self, user_id: str, session_id: str, channel: str, mode: str
    ) -> None:
        self._reset_session()
        self._session_started_at = int(time.time())
        self._session_actions.append(p.SessionAction(
            action_type="session_start",
            details={"user_id": user_id, "channel": channel, "mode": mode},
        ))
        if self._ws:
            try:
                await self._ws.session_start(user_id, session_id, channel)
            except Exception as exc:
                logger.warning("Session start via WS failed: %s", exc)

    def _reset_session(self) -> None:
        self._session_actions = []
        self._turns = []
        self._session_started_at = 0

    def _build_audit_blob(
        self,
        session_id: str,
        user_id: str,
        summary: p.MemSessionSummary,
    ) -> p.SessionAuditBlob:
        total_tool_calls = sum(t.tool_call_count for t in self._turns)
        total_memories_retrieved = sum(t.memories_retrieved for t in self._turns)
        total_memories_written = sum(t.memories_written for t in self._turns)
        return p.SessionAuditBlob(
            session_id=session_id,
            user_id=user_id,
            channel=self._active_channel,
            agent_mode=self._active_mode,
            version=1,
            merkle_root=summary.merkle_root,
            da_tx_hash=summary.da_tx_hash,
            chain_tx_hash=summary.chain_tx_hash,
            actions=self._session_actions,
            started_at=self._session_started_at,
            ended_at=int(time.time()),
            memories_written=total_memories_written,
            memories_retrieved=total_memories_retrieved,
            tool_calls=total_tool_calls,
        )

    def _build_system_prompt(self, memories: list[dict], mode: str) -> str:
        """Build the system prompt with memory context."""
        mode_descriptions = {
            "assistant": "You are a helpful AI assistant with access to a long-term memory store.",
            "coding": (
                "You are an expert coding assistant. You have access to the user's codebase "
                "conventions, preferred stack, and current projects via memory."
            ),
            "research": (
                "You are a research assistant. You have access to the user's research history "
                "and can connect current questions to past sessions."
            ),
        }
        base = mode_descriptions.get(mode, mode_descriptions["assistant"])

        if memories:
            memory_lines = []
            for m in memories:
                mem_type = m.get("memory_type", "unknown")
                text = m.get("text", "")
                memory_lines.append(f"- [{mem_type}] {text}")
            memory_context = "\n".join(memory_lines)
            return (
                f"{base}\n\n"
                f"Relevant memories from this user's past:\n{memory_context}\n\n"
                f"When you reference a memory, mention it naturally in your response."
            )
        return base

    def _build_messages(
        self,
        user_text: str,
        memories: list[dict],
        mode: str,
    ) -> list[dict]:
        """Build the message list for inference."""
        messages = [
            {"role": "system", "content": self._build_system_prompt(memories, mode)},
            {"role": "user", "content": user_text},
        ]
        return messages

    async def _react_loop(
        self,
        messages: list[dict],
        turn: AgentTurn,
    ) -> tuple[str, list[ToolResult]]:
        """
        ReAct: Reason → Act → Observe, up to max_tool_calls.
        Returns (final_text, list_of_tool_results).
        """
        tool_results: list[ToolResult] = []
        tool_calls_made = 0

        for reasoning_turn in range(self.config.max_reasoning_turns):
            # Inference call
            result = await self._inference.chat(
                messages=messages,
                tools=self._tools.openai_schema(),
                tool_choice="auto",
                max_turns=self.config.max_tool_calls,
            )

            # Append assistant message
            assistant_msg: dict[str, Any] = {"role": "assistant", "content": result.content}
            if result.tool_calls:
                assistant_msg["tool_calls"] = [
                    {"id": f"call_{i}", "type": "function", "function": {"name": tc["name"], "arguments": json.dumps(tc["arguments"])}}
                    for i, tc in enumerate(result.tool_calls)
                ]
            messages.append(assistant_msg)

            # Log inference
            self._session_actions.append(p.SessionAction(
                action_type="inference",
                details={
                    "finish_reason": result.finish_reason,
                    "content_length": len(result.content),
                    "tool_calls_requested": len(result.tool_calls),
                },
            ))

            if not result.tool_calls:
                # Done — no more tools
                return result.content, tool_results

            # Execute each tool call
            for tc in result.tool_calls:
                if tool_calls_made >= self.config.max_tool_calls:
                    break

                tool_name = tc["name"]
                tool_input = tc["arguments"]

                # Log tool call
                self._session_actions.append(p.SessionAction(
                    action_type="tool_call",
                    details={"tool": tool_name, "input": tool_input},
                ))

                tool_result = await self._tools.execute(tool_name, tool_input)
                tool_results.append(tool_result)

                messages.append({
                    "role": "tool",
                    "content": tool_result.output or f"Error: {tool_result.error}",
                    "tool_call_id": f"call_{tool_calls_made}",
                })
                tool_calls_made += 1

            if tool_calls_made >= self.config.max_tool_calls:
                break

        # Final inference without tools to produce a coherent response
        result = await self._inference.chat(
            messages=messages,
            tools=[],  # No more tool calls
            tool_choice="none",
        )
        messages.append({"role": "assistant", "content": result.content})
        return result.content, tool_results

    async def _queue_turn_memories(
        self,
        user_id: str,
        session_id: str,
        user_text: str,
        response_text: str,
        retrieved_memories: list[dict],
    ) -> None:
        """Queue memories from this exchange for the memory team's session batch commit."""
        if not self._ws:
            return

        # Queue the user message as episodic
        await self._ws.queue_write(
            user_id=user_id,
            session_id=session_id,
            text=f"User: {user_text}",
            memory_type="episodic",
            metadata={"turn": len(self._turns)},
        )

        # Queue the agent response as episodic
        await self._ws.queue_write(
            user_id=user_id,
            session_id=session_id,
            text=f"Agent: {response_text}",
            memory_type="episodic",
            metadata={"turn": len(self._turns)},
        )

        # If the response revealed new semantic facts about the user, queue as semantic
        # (simplified: just queue the full exchange; memory team can evolve later)
        # Queue working memory for current task context if relevant
        if retrieved_memories:
            for mem in retrieved_memories[:2]:
                if mem.get("memory_type") == "working":
                    await self._ws.queue_write(
                        user_id=user_id,
                        session_id=session_id,
                        text=mem.get("text", ""),
                        memory_type="working",
                        metadata={"reused_from_session": session_id},
                    )
