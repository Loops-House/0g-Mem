"""0g Storage client — upload/download blobs via the Node.js SDK bridge."""

import json
import math
import pathlib
import subprocess
from typing import Optional

import requests
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

from .encryption import encrypt, decrypt

# Path to the Node.js bridge script
_BRIDGE_SCRIPT = pathlib.Path(__file__).parent.parent / "scripts" / "zg_storage.js"

# 0g Storage protocol constants (from @0glabs/0g-ts-sdk constant.js)
CHUNK_SIZE = 256          # bytes per chunk
MAX_CHUNKS_PER_SEGMENT = 1024
SEGMENT_SIZE = CHUNK_SIZE * MAX_CHUNKS_PER_SEGMENT  # 256 KB

# FixedPriceFlow contract ABI — submit + market()
FLOW_ABI = [
    {
        "inputs": [
            {
                "components": [
                    {"internalType": "uint256", "name": "length", "type": "uint256"},
                    {"internalType": "bytes", "name": "tags", "type": "bytes"},
                    {
                        "components": [
                            {"internalType": "bytes32", "name": "root", "type": "bytes32"},
                            {"internalType": "uint256", "name": "height", "type": "uint256"},
                        ],
                        "internalType": "struct SubmissionNode[]",
                        "name": "nodes",
                        "type": "tuple[]",
                    },
                ],
                "internalType": "struct Submission",
                "name": "submission",
                "type": "tuple",
            }
        ],
        "name": "submit",
        "outputs": [
            {"internalType": "uint256", "name": "", "type": "uint256"},
            {"internalType": "bytes32", "name": "", "type": "bytes32"},
            {"internalType": "uint256", "name": "", "type": "uint256"},
            {"internalType": "uint256", "name": "", "type": "uint256"},
        ],
        "stateMutability": "payable",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "market",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    },
]

# FixedPrice market contract ABI — pricePerSector
MARKET_ABI = [
    {
        "inputs": [],
        "name": "pricePerSector",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    }
]


def _next_pow2(n: int) -> int:
    """Return next power of 2 >= n."""
    if n <= 1:
        return 1
    p = 1
    while p < n:
        p <<= 1
    return p


def _compute_padded_chunks(num_chunks: int) -> int:
    """
    Compute padded chunk count matching 0g SDK's computePaddedSize().
    Returns paddedChunks (what the contract expects to be reserved).
    """
    next_pow2 = _next_pow2(num_chunks)
    if next_pow2 == num_chunks:
        return next_pow2
    min_chunk = max(1, next_pow2 // 16)
    return math.ceil(num_chunks / min_chunk) * min_chunk


def _split_nodes(num_chunks: int) -> list[int]:
    """
    Split file into submission nodes matching 0g SDK's splitNodes().
    Returns list of chunk counts per node (each is a power of 2).
    """
    padded_chunks = _compute_padded_chunks(num_chunks)
    next_chunk_size = _next_pow2(num_chunks)
    nodes = []
    while padded_chunks > 0:
        if padded_chunks >= next_chunk_size:
            padded_chunks -= next_chunk_size
            nodes.append(next_chunk_size)
        next_chunk_size //= 2
    return nodes


def _keccak(data: bytes) -> bytes:
    """keccak256 of data, returns raw 32 bytes."""
    return Web3.keccak(primitive=data)


def _merkle_root_of_chunks(raw: bytes, num_chunks: int) -> bytes:
    """
    Compute keccak256 Merkle root over `num_chunks` chunks of CHUNK_SIZE each.
    Uses same algorithm as 0g SDK MerkleTree.build().
    """
    leaves = []
    for i in range(num_chunks):
        start = i * CHUNK_SIZE
        end = start + CHUNK_SIZE
        chunk = raw[start:end] if start < len(raw) else b''
        chunk = chunk.ljust(CHUNK_SIZE, b'\x00')
        leaves.append(_keccak(chunk))

    # Build tree — same as 0g SDK: process pairs, carry odd node up
    queue = list(leaves)
    while len(queue) > 1:
        next_queue = []
        i = 0
        while i < len(queue):
            if i + 1 < len(queue):
                combined = _keccak(queue[i] + queue[i + 1])
                next_queue.append(combined)
                i += 2
            else:
                next_queue.append(queue[i])
                i += 1
        queue = next_queue

    return queue[0]


def _build_submission_nodes(raw: bytes, file_size: int) -> list[dict]:
    """
    Build the nodes[] array for the Flow.submit() Submission struct.
    Matches 0g SDK's AbstractFile.createSubmission() logic.
    """
    num_chunks = max(1, math.ceil(file_size / CHUNK_SIZE))
    chunk_groups = _split_nodes(num_chunks)

    nodes = []
    offset = 0
    for group_chunks in chunk_groups:
        segment_raw = raw[offset * CHUNK_SIZE:]
        root = _merkle_root_of_chunks(segment_raw, group_chunks)
        height = int(math.log2(group_chunks)) if group_chunks > 1 else 0
        nodes.append({
            "root": root,
            "height": height,
        })
        offset += group_chunks

    return nodes


class StorageClient:
    """Uploads and downloads memory blobs via the 0g FixedPriceFlow protocol."""

    def __init__(
        self,
        indexer_rpc: str,
        flow_contract: str,
        private_key: str,
        chain_rpc: str,
    ):
        self.indexer_rpc = indexer_rpc.rstrip("/")
        self.flow_contract_address = flow_contract
        self.private_key = private_key
        self._chain_rpc = chain_rpc
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

        self.w3 = Web3(Web3.HTTPProvider(chain_rpc))
        self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
        self.account = self.w3.eth.account.from_key(private_key)
        self.flow = self.w3.eth.contract(
            address=Web3.to_checksum_address(flow_contract),
            abi=FLOW_ABI,
        )

        self._local_store: dict[str, bytes] = {}

    def upload(self, data: dict) -> str:
        """Upload a memory blob. Returns blob_id (Merkle root hex)."""
        serialized = json.dumps(data, sort_keys=True).encode()
        return self._upload_bytes(serialized)

    def download(self, blob_id: str) -> Optional[dict]:
        """Download a blob by its Merkle root. Returns deserialized dict or None."""
        raw = self._download_bytes(blob_id)
        if raw is None:
            return None
        try:
            return json.loads(raw.rstrip(b"\x00"))
        except Exception:
            return None

    def upload_encrypted(self, data: dict, encryption_key: bytes) -> str:
        """AES-256-GCM encrypt, then upload. Returns blob_id of the encrypted blob."""
        plaintext = json.dumps(data, sort_keys=True).encode()
        ciphertext = encrypt(plaintext, encryption_key)
        return self._upload_bytes(ciphertext)

    def download_encrypted(self, blob_id: str, encryption_key: bytes) -> Optional[dict]:
        """Download and decrypt a blob. Returns dict or None on failure."""
        raw = self._download_bytes(blob_id)
        if raw is None:
            return None
        try:
            decrypted = decrypt(raw, encryption_key)
            return json.loads(decrypted)
        except Exception:
            return None

    def exists(self, blob_id: str) -> bool:
        """Return True if the blob exists in 0g Storage."""
        try:
            resp = self.session.get(
                f"{self.indexer_rpc}/file",
                params={"root": blob_id},
                timeout=10,
            )
            data = resp.json()
            return data.get("code") == 0
        except Exception:
            return False

    def _get_price_per_sector(self) -> int:
        """Fetch pricePerSector from the market contract linked to the Flow contract."""
        try:
            market_addr = self.flow.functions.market().call()
            market = self.w3.eth.contract(
                address=Web3.to_checksum_address(market_addr),
                abi=MARKET_ABI,
            )
            return market.functions.pricePerSector().call()
        except Exception:
            return 0  # some testnet deployments have free storage

    def _upload_bytes(self, raw: bytes) -> str:
        """Upload via Node.js bridge; falls back to local Merkle root computation."""
        if len(raw) == 0:
            raise ValueError("Cannot upload empty blob")

        try:
            result = subprocess.run(
                ["node", str(_BRIDGE_SCRIPT), "upload",
                 self.private_key, self.indexer_rpc,
                 self._chain_rpc, raw.hex()],
                capture_output=True, text=True, timeout=120,
            )
            out = json.loads(result.stdout.strip())
            if out.get("ok"):
                return out["root_hash"].lstrip("0x")
        except Exception:
            pass

        file_size = len(raw)
        nodes = _build_submission_nodes(raw, file_size)
        if len(nodes) == 1:
            file_root = nodes[0]["root"]
        else:
            queue = [n["root"] for n in nodes]
            while len(queue) > 1:
                next_q = []
                for i in range(0, len(queue), 2):
                    if i + 1 < len(queue):
                        next_q.append(_keccak(queue[i] + queue[i + 1]))
                    else:
                        next_q.append(queue[i])
                queue = next_q
            file_root = queue[0]

        blob_id = file_root.hex() if isinstance(file_root, bytes) else file_root.lstrip("0x")
        self._local_store[blob_id] = raw
        return blob_id

    def _download_bytes(self, blob_id: str) -> Optional[bytes]:
        """Download raw bytes via Node.js bridge, falling back to local store."""
        clean_id = blob_id.lstrip("0x")
        if clean_id in self._local_store:
            return self._local_store[clean_id]

        try:
            result = subprocess.run(
                ["node", str(_BRIDGE_SCRIPT), "download",
                 self.private_key, self.indexer_rpc,
                 self._chain_rpc, clean_id],
                capture_output=True, text=True, timeout=60,
            )
            out = json.loads(result.stdout.strip())
            if out.get("ok"):
                return bytes.fromhex(out["data"])
        except Exception:
            pass

        return None
