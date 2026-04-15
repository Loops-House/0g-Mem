"""Memory read/write/audit/verify endpoints."""

import json
from typing import Optional

from fastapi import APIRouter, HTTPException, Header

from api.dependencies import get_memory
from api.models import (
    AddRequest, AddResponse,
    QueryRequest, QueryResponse,
    StateResponse,
    VerifyRequest, VerifyResponse,
    GrantRequest, GrantResponse,
    RevokeRequest, RevokeResponse,
)
from ogmem.proof import QueryProof

router = APIRouter(prefix="/memory", tags=["memory"])


@router.post("/{agent_id}/add", response_model=AddResponse)
def add_memory(
    agent_id: str,
    body: AddRequest,
    x_private_key: Optional[str] = Header(default=None),
):
    """Write a memory entry to 0g Storage and anchor its Merkle root on-chain."""
    memory = get_memory(agent_id, x_private_key)
    try:
        receipt = memory.add(body.text, body.metadata)
        return AddResponse(
            agent_id=receipt.agent_id,
            blob_id=receipt.blob_id,
            merkle_root=receipt.merkle_root,
            da_tx_hash=receipt.da_tx_hash,
            chain_tx_hash=receipt.chain_tx_hash,
            timestamp=receipt.timestamp,
            encrypted=memory._encrypted,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{agent_id}/query", response_model=QueryResponse)
def query_memory(
    agent_id: str,
    body: QueryRequest,
    x_private_key: Optional[str] = Header(default=None),
):
    """Semantic similarity search. Returns top-k results and a cryptographic proof."""
    memory = get_memory(agent_id, x_private_key)
    try:
        results, proof = memory.query(body.text, top_k=body.top_k)
        return QueryResponse(results=results, proof=proof.__dict__)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{agent_id}/state", response_model=StateResponse)
def get_state(
    agent_id: str,
    x_private_key: Optional[str] = Header(default=None),
):
    """Current Merkle root + chain state for an agent."""
    memory = get_memory(agent_id, x_private_key)
    try:
        chain_state = memory._chain.get_latest_root(memory._chain.agent_address)
        token_id = memory.memory_token_id()
        return StateResponse(
            agent_id=agent_id,
            merkle_root=chain_state.merkle_root if chain_state else "",
            block_number=chain_state.block_number if chain_state else 0,
            da_tx_hash=chain_state.da_tx_hash if chain_state else "",
            timestamp=chain_state.timestamp if chain_state else 0,
            memory_count=len(memory._entries),
            nft_token_id=token_id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{agent_id}/audit")
def get_audit(
    agent_id: str,
    from_block: int = 0,
    to_block: int = -1,
    x_private_key: Optional[str] = Header(default=None),
):
    """Full EU AI Act Article 12 compliant audit report (JSON)."""
    memory = get_memory(agent_id, x_private_key)
    try:
        report = memory.export_audit(from_block=from_block, to_block=to_block)
        return json.loads(report.to_json())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{agent_id}/verify", response_model=VerifyResponse)
def verify_proof(
    agent_id: str,
    body: VerifyRequest,
    x_private_key: Optional[str] = Header(default=None),
):
    """Verify a QueryProof. Stateless — callable by any third party."""
    memory = get_memory(agent_id, x_private_key)
    try:
        proof = QueryProof(**body.proof)
        valid = memory.verify_proof(proof)
        return VerifyResponse(
            valid=valid,
            message="Proof is valid — retrieval verified on 0g Chain." if valid
                    else "Proof is invalid — data may have been tampered with.",
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid proof format: {e}")


@router.post("/{agent_id}/grant", response_model=GrantResponse)
def grant_access(
    agent_id: str,
    body: GrantRequest,
    x_private_key: Optional[str] = Header(default=None),
):
    """Grant an agent full or shard-level access to memory (on-chain)."""
    memory = get_memory(agent_id, x_private_key)
    try:
        tx = memory.grant_access(
            body.agent_address,
            shard_blob_ids=body.shard_blob_ids or None,
        )
        return GrantResponse(
            chain_tx_hash=tx,
            agent_address=body.agent_address,
            access_type="shard" if body.shard_blob_ids else "full",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{agent_id}/revoke", response_model=RevokeResponse)
def revoke_access(
    agent_id: str,
    body: RevokeRequest,
    x_private_key: Optional[str] = Header(default=None),
):
    """Revoke all access for an agent — effective immediately on-chain."""
    memory = get_memory(agent_id, x_private_key)
    try:
        tx = memory.revoke_access(body.agent_address)
        return RevokeResponse(chain_tx_hash=tx, agent_address=body.agent_address)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
