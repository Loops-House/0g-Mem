"""Shared dependencies — memory instance cache, auth."""

import os
from typing import Optional

from fastapi import HTTPException

from ogmem.memory import VerifiableMemory
from ogmem.config import NETWORKS

_memory_instances: dict[str, VerifiableMemory] = {}


def get_memory(agent_id: str, private_key: Optional[str] = None) -> VerifiableMemory:
    """
    Get or create a VerifiableMemory instance for the given agent_id.
    Uses X-Private-Key header, falling back to AGENT_KEY env var.
    """
    key = private_key or os.environ.get("AGENT_KEY")
    if not key:
        raise HTTPException(
            status_code=401,
            detail="Private key required. Pass X-Private-Key header or set AGENT_KEY env var.",
        )

    cache_key = f"{agent_id}:{key[:8]}"
    if cache_key not in _memory_instances:
        net = NETWORKS["0g-testnet"]
        _memory_instances[cache_key] = VerifiableMemory(
            agent_id=agent_id,
            private_key=key,
            network="0g-testnet",
            registry_contract_address=os.environ.get(
                "MEMORY_REGISTRY_ADDRESS", net.memory_registry_address
            ),
            nft_contract_address=os.environ.get(
                "MEMORY_NFT_ADDRESS", net.memory_nft_address
            ),
            encrypted=True,
        )
    return _memory_instances[cache_key]
