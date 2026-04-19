"""WebSocket session API — real-time memory operations for the agent runtime.

WebSocket endpoint: ws://host/memory/session/{user_id}
Auth: wallet signature nonce challenge on connection.

Protocol messages (from protocol.py):
  Inbound:
    - MemSessionStart  → session_start()
    - MemRetrieveRequest → recall()
    - MemQueueWrite   → store() (queued, committed at session_end)
    - MemSessionEnd   → session_end()

  Outbound:
    - MemRetrieveResponse
    - MemWriteQueued
    - MemSessionSummary
    - Error
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Optional

import websockets
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, HTTPException
from websockets.exceptions import ConnectionClosed

import protocol as p
from ogmem.session import SessionMemory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/memory", tags=["session-ws"])


# ---------------------------------------------------------------------------
# Wallet auth for WebSocket
# ---------------------------------------------------------------------------

def _verify_signature(wallet_address: str, signature: str, nonce: str) -> bool:
    """Verify a wallet signature for WebSocket auth."""
    try:
        from web3 import Web3

        msg = f"0g Mem session auth: {nonce}"
        w3 = Web3()
        recovered = w3.eth.account.recover_message(message=msg, signature=signature)
        return recovered.lower() == wallet_address.lower()
    except Exception as exc:
        logger.warning("WS signature verify failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Session manager — tracks active sessions per user
# ---------------------------------------------------------------------------

class SessionManager:
    """
    Manages active SessionMemory instances per user.
    One SessionMemory per wallet address.
    """

    def __init__(self):
        self._sessions: dict[str, SessionMemory] = {}
        self._nonces: dict[str, int] = {}  # wallet → nonce timestamp

    def generate_nonce(self, wallet_address: str) -> str:
        """Generate and store a nonce for a wallet."""
        nonce = str(int(time.time()))
        self._nonces[wallet_address.lower()] = int(nonce)
        return nonce

    def verify_nonce(self, wallet_address: str, nonce: str) -> bool:
        """Verify the nonce is recent (within 5 minutes)."""
        try:
            stored = self._nonces.get(wallet_address.lower(), 0)
            provided = int(nonce)
            # Nonce must be within 5 minutes
            return abs(stored - provided) < 300
        except (ValueError, TypeError):
            return False

    def get_or_create_session(
        self,
        wallet_address: str,
        private_key: Optional[str] = None,
    ) -> SessionMemory:
        """Get or create a SessionMemory for a wallet."""
        key = wallet_address.lower()
        if key not in self._sessions:
            pkey = private_key or os.environ.get("AGENT_KEY", "")
            registry = os.environ.get(
                "MEMORY_REGISTRY_ADDRESS",
                "0xEDF95D9CFb157F5F38C1125B7DFB3968E05d2c4b",
            )
            nft = os.environ.get(
                "MEMORY_NFT_ADDRESS",
                "0x70ad85300f522A41689954a4153744BF6E57E488",
            )
            self._sessions[key] = SessionMemory(
                agent_id=wallet_address,
                private_key=pkey,
                registry_contract_address=registry,
                nft_contract_address=nft,
            )
        return self._sessions[key]

    def close_session(self, wallet_address: str) -> None:
        key = wallet_address.lower()
        self._sessions.pop(key, None)


# Global session manager
_session_manager = SessionManager()


# ---------------------------------------------------------------------------
# WebSocket route handler
# ---------------------------------------------------------------------------

@router.websocket("/session/{wallet_address}")
async def memory_session_websocket(
    websocket: WebSocket,
    wallet_address: str,
    mode: str = Query(default="assistant"),
    channel: str = Query(default="desktop"),
):
    """
    WebSocket endpoint for real-time memory operations.

    Auth: requires X-Wallet-Address, X-Nonce, X-Signature headers.
    On connection, send a MemSessionStart message to begin.
    """
    wallet_address = wallet_address.lower()

    # ── Auth handshake ──────────────────────────────────────────────────────
    sig = websocket.headers.get("x-signature", "")
    nonce = websocket.headers.get("x-nonce", "")

    if not sig or not nonce:
        await websocket.close(code=4001, reason="Missing auth headers")
        return

    if not _session_manager.verify_nonce(wallet_address, nonce):
        # Try verifying with the nonce anyway (may be a reconnect)
        is_valid = _verify_signature(wallet_address, sig, nonce)
        if not is_valid:
            await websocket.close(code=4002, reason="Invalid signature")
            return

    # Accept connection
    await websocket.accept()

    # Get or create session
    pkey = os.environ.get("AGENT_KEY", "")
    try:
        session = _session_manager.get_or_create_session(wallet_address, pkey)
    except Exception as exc:
        await websocket.send_json({"type": "error", "message": str(exc)})
        await websocket.close()
        return

    # ── Message loop ────────────────────────────────────────────────────────
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON",
                    "code": "parse_error",
                })
                continue

            msg_type = msg.get("type", "")

            try:
                if msg_type == "mem_session_start":
                    await _handle_session_start(websocket, session, msg)

                elif msg_type == "mem_retrieve":
                    await _handle_retrieve(websocket, session, msg)

                elif msg_type == "mem_queue_write":
                    await _handle_queue_write(websocket, session, msg)

                elif msg_type == "mem_session_end":
                    await _handle_session_end(websocket, session, msg)

                else:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Unknown message type: {msg_type}",
                        "code": "unknown_type",
                    })

            except Exception as exc:
                logger.exception("Error handling message %s", msg_type)
                await websocket.send_json({
                    "type": "error",
                    "message": str(exc),
                    "code": "internal_error",
                })

    except WebSocketDisconnect:
        logger.info("WS disconnected: %s", wallet_address)
    except ConnectionClosed:
        logger.info("WS connection closed: %s", wallet_address)


# ---------------------------------------------------------------------------
# Message handlers
# ---------------------------------------------------------------------------

async def _handle_session_start(
    ws: WebSocket,
    session: SessionMemory,
    msg: dict,
) -> None:
    """Handle mem_session_start — initialize session from persisted index."""
    session_id = msg.get("session_id", "")
    if not session_id:
        await ws.send_json({
            "type": "error",
            "message": "session_id is required",
            "code": "missing_field",
        })
        return

    start = time.time()
    index = session.session_start(session_id)

    await ws.send_json({
        "type": "mem_session_start_response",
        "session_id": session_id,
        "version": index.version,
        "memory_count": len(index.entries),
        "last_updated": index.last_updated,
        "latency_ms": int((time.time() - start) * 1000),
    })


async def _handle_retrieve(
    ws: WebSocket,
    session: SessionMemory,
    msg: dict,
) -> None:
    """Handle mem_retrieve — search memory and return top-K blobs."""
    query_text = msg.get("query", "")
    top_k = msg.get("top_k", 5)
    memory_types_raw = msg.get("memory_types")
    memory_types = None

    if memory_types_raw:
        try:
            memory_types = [p.MemoryType(t) for t in memory_types_raw]
        except (ValueError, TypeError):
            pass

    if not query_text:
        await ws.send_json({
            "type": "error",
            "message": "query is required",
            "code": "missing_field",
        })
        return

    start = time.time()
    results = session.recall(query_text, top_k=top_k, memory_types=memory_types)

    await ws.send_json({
        "type": "mem_retrieve_response",
        "memories": results,
        "count": len(results),
        "latency_ms": int((time.time() - start) * 1000),
    })


async def _handle_queue_write(
    ws: WebSocket,
    session: SessionMemory,
    msg: dict,
) -> None:
    """Handle mem_queue_write — queue a write for session_end commit."""
    text = msg.get("text", "")
    memory_type_raw = msg.get("memory_type", "episodic")
    metadata = msg.get("metadata")

    if not text:
        await ws.send_json({
            "type": "error",
            "message": "text is required",
            "code": "missing_field",
        })
        return

    try:
        mem_type = p.MemoryType(memory_type_raw)
    except (ValueError, TypeError):
        mem_type = p.MemoryType.EPISODIC

    start = time.time()
    write_id = session.store(text, mem_type, metadata)

    await ws.send_json({
        "type": "mem_write_queued",
        "write_id": write_id,
        "memory_type": mem_type.value,
        "queued_at": int(time.time()),
        "latency_ms": int((time.time() - start) * 1000),
    })


async def _handle_session_end(
    ws: WebSocket,
    session: SessionMemory,
    msg: dict,
) -> None:
    """Handle mem_session_end — commit all queued writes to 0g Storage + chain."""
    session_id = msg.get("session_id", "")

    start = time.time()
    version = session.session_end()

    await ws.send_json({
        "type": "mem_session_summary",
        "session_id": session_id or session._session_id or "",
        "writes_committed": len(session._write_queue) if hasattr(session, "_write_queue") else 0,
        "merkle_root": version.memory_root,
        "chain_tx_hash": "",  # filled by session_end
        "da_tx_hash": "",
        "index_cid": version.index_cid,
        "version": version.version,
        "latency_ms": int((time.time() - start) * 1000),
    })
