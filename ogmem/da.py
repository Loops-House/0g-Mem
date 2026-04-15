"""0g DA client — posts read/write commitments via gRPC."""

import hashlib
import json
import time
from typing import Optional


def _try_import_grpc():
    """Try to import gRPC stubs — returns (grpc, pb2, pb2_grpc) or None."""
    try:
        import grpc
        from proto import disperser_pb2, disperser_pb2_grpc
        return grpc, disperser_pb2, disperser_pb2_grpc
    except ImportError:
        return None


class DAClient:
    """
    Client for 0g DA — the immutable audit log layer.

    Every write commitment: {agent_id, blob_id, merkle_root, timestamp}
    Every read commitment:  {agent_id, query_hash, blob_ids, scores, merkle_root, timestamp}

    Submission priority:
      1. Local DA node via gRPC (localhost:51001) — real 0g DA
      2. Local mode — deterministic SHA-256 hash (no network needed)
    """

    def __init__(self, disperser_rpc: str):
        """
        Args:
            disperser_rpc: gRPC address of the DA disperser, e.g. "localhost:51001".
                           Pass "" to use local mode only.
        """
        self.disperser_rpc = disperser_rpc
        self._submitted: list[dict] = []  # in-process store for fetch_commitment / fetch_agent_history
        self._grpc_available: Optional[bool] = None  # lazily detected

    def post_write_commitment(
        self,
        agent_id: str,
        blob_id: str,
        merkle_root: str,
        timestamp: Optional[int] = None,
    ) -> str:
        """
        Post a write commitment to 0g DA.

        Returns da_tx_hash — unique identifier for this commitment.
        """
        commitment = {
            "type": "memory_write",
            "agent_id": agent_id,
            "blob_id": blob_id,
            "merkle_root": merkle_root,
            "timestamp": timestamp or int(time.time()),
            "version": "1.0",
        }
        return self._submit(commitment)

    def post_read_commitment(
        self,
        agent_id: str,
        query_hash: str,
        blob_ids: list[str],
        scores: list[float],
        merkle_root: str,
        timestamp: Optional[int] = None,
    ) -> str:
        """
        Post a read commitment to 0g DA.

        This is the immutable proof that a retrieval happened.
        Returns da_tx_hash.
        """
        commitment = {
            "type": "memory_read",
            "agent_id": agent_id,
            "query_hash": query_hash,
            "blob_ids": blob_ids,
            "scores": scores,
            "merkle_root": merkle_root,
            "timestamp": timestamp or int(time.time()),
            "version": "1.0",
        }
        return self._submit(commitment)

    def fetch_commitment(self, da_tx_hash: str) -> Optional[dict]:
        """
        Fetch a specific commitment by its DA transaction hash.
        Used during audit report generation.
        """
        # Check local store first
        for entry in self._submitted:
            if entry.get("da_tx_hash") == da_tx_hash:
                return entry.get("commitment")

        # Try live gRPC retrieval if it's a grpc: hash
        if da_tx_hash.startswith("grpc:") and self.disperser_rpc:
            raw = self._grpc_retrieve(da_tx_hash)
            if raw:
                try:
                    return json.loads(raw)
                except Exception:
                    pass

        return None

    def fetch_agent_history(self, agent_id: str) -> list[dict]:
        """
        Fetch all commitments for a given agent_id from 0g DA.
        Used to reconstruct the full audit timeline.
        """
        history = [
            e for e in self._submitted if e.get("commitment", {}).get("agent_id") == agent_id
        ]
        return [
            {"da_tx_hash": e["da_tx_hash"], **e["commitment"]}
            for e in history
        ]

    def _submit(self, commitment: dict) -> str:
        """Try gRPC DA node first, fall back to local hash. Returns da_tx_hash."""
        serialized = json.dumps(commitment, sort_keys=True).encode()

        if self.disperser_rpc and self._is_grpc_available():
            da_tx_hash = self._grpc_disperse(serialized)
            if da_tx_hash:
                self._submitted.append({
                    "da_tx_hash": da_tx_hash,
                    "commitment": commitment,
                    "submitted_at": int(time.time()),
                })
                return da_tx_hash

        da_tx_hash = "local:" + hashlib.sha256(serialized).hexdigest()
        self._submitted.append({
            "da_tx_hash": da_tx_hash,
            "commitment": commitment,
            "submitted_at": int(time.time()),
        })
        return da_tx_hash

    def _is_grpc_available(self) -> bool:
        if self._grpc_available is None:
            self._grpc_available = _try_import_grpc() is not None
        return self._grpc_available

    def _grpc_disperse(self, data: bytes) -> Optional[str]:
        """Submit bytes via gRPC DisperseBlob. Returns "grpc:<request_id_hex>" or None."""
        imports = _try_import_grpc()
        if not imports:
            return None
        grpc, pb2, pb2_grpc = imports
        try:
            channel = grpc.insecure_channel(self.disperser_rpc)
            stub = pb2_grpc.DisperserStub(channel)
            response = stub.DisperseBlob(
                pb2.DisperseBlobRequest(data=data),
                timeout=30,
            )
            request_id_hex = response.request_id.hex()
            channel.close()
            return f"grpc:{request_id_hex}"
        except Exception:
            return None

    def _grpc_retrieve(self, da_tx_hash: str) -> Optional[bytes]:
        """Poll GetBlobStatus then call RetrieveBlob. Returns raw bytes or None."""
        imports = _try_import_grpc()
        if not imports:
            return None
        grpc, pb2, pb2_grpc = imports
        try:
            request_id_hex = da_tx_hash.removeprefix("grpc:")
            request_id = bytes.fromhex(request_id_hex)

            channel = grpc.insecure_channel(self.disperser_rpc)
            stub = pb2_grpc.DisperserStub(channel)

            status_resp = stub.GetBlobStatus(
                pb2.BlobStatusRequest(request_id=request_id),
                timeout=15,
            )
            if status_resp.status not in (pb2.BlobStatus.CONFIRMED, pb2.BlobStatus.FINALIZED):
                channel.close()
                return None

            header = status_resp.info.blob_header
            retrieve_resp = stub.RetrieveBlob(
                pb2.RetrieveBlobRequest(
                    storage_root=header.storage_root,
                    epoch=header.epoch,
                    quorum_id=header.quorum_id,
                ),
                timeout=15,
            )
            channel.close()
            return retrieve_resp.data
        except Exception:
            return None
