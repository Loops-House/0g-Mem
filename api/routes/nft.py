"""MemoryNFT endpoints — mint, ownership."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Header

from api.dependencies import get_memory
from api.models import MintResponse

router = APIRouter(prefix="/nft", tags=["nft"])


@router.post("/mint", response_model=MintResponse)
def mint_nft(
    x_private_key: Optional[str] = Header(default=None),
):
    """Mint the caller's memory NFT on 0g Chain. One per wallet."""
    memory = get_memory("nft-mint", x_private_key)
    try:
        tx = memory.mint_memory_nft()
        token_id = memory.memory_token_id()
        return MintResponse(
            chain_tx_hash=tx,
            token_id=token_id,
            owner=memory._chain.agent_address,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
