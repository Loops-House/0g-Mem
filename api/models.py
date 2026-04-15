"""Pydantic request / response models for the 0g Mem API."""

from typing import Optional
from pydantic import BaseModel


class AddRequest(BaseModel):
    text: str
    metadata: dict = {}

class AddResponse(BaseModel):
    agent_id: str
    blob_id: str
    merkle_root: str
    da_tx_hash: str
    chain_tx_hash: str
    timestamp: int
    encrypted: bool


class QueryRequest(BaseModel):
    text: str
    top_k: int = 3

class QueryResponse(BaseModel):
    results: list[str]
    proof: dict


class StateResponse(BaseModel):
    agent_id: str
    merkle_root: str
    block_number: int
    da_tx_hash: str
    timestamp: int
    memory_count: int
    nft_token_id: int


class VerifyRequest(BaseModel):
    proof: dict

class VerifyResponse(BaseModel):
    valid: bool
    message: str


class GrantRequest(BaseModel):
    agent_address: str
    shard_blob_ids: list[str] = []

class GrantResponse(BaseModel):
    chain_tx_hash: str
    agent_address: str
    access_type: str  # "full" or "shard"

class RevokeRequest(BaseModel):
    agent_address: str

class RevokeResponse(BaseModel):
    chain_tx_hash: str
    agent_address: str


class MintResponse(BaseModel):
    chain_tx_hash: str
    token_id: int
    owner: str
