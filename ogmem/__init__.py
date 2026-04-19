"""0g Mem — Verifiable, Private, Owned Agent Memory on 0g Labs."""

from .memory import VerifiableMemory
from .proof import AuditReport, QueryProof, WriteReceipt, MemoryType
from .encryption import derive_encryption_key
from .inference import ZeroGInferenceClient, ChatMessage

__all__ = [
    "VerifiableMemory",
    "WriteReceipt",
    "QueryProof",
    "AuditReport",
    "MemoryType",
    "derive_encryption_key",
    "ZeroGInferenceClient",
    "ChatMessage",
]
__version__ = "0.2.0"
