"""
LORL-9.1 Identity Module — Ed25519 cryptographic identity for labs and agents.

Each lab or agent in the LORL network gets an Ed25519 keypair for signing
treaty agreements, ledger events, and audit records.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


@dataclass
class EdDSAKeyPair:
    """Ed25519 signing and verification key pair."""

    private_key: Ed25519PrivateKey
    public_key: Ed25519PublicKey

    @classmethod
    def generate(cls) -> "EdDSAKeyPair":
        """Generate a new Ed25519 key pair."""
        private_key = Ed25519PrivateKey.generate()
        return cls(
            private_key=private_key,
            public_key=private_key.public_key(),
        )

    def sign(self, data: bytes) -> bytes:
        """Sign data with the private key."""
        return self.private_key.sign(data)

    def verify(self, data: bytes, signature: bytes) -> bool:
        """Verify a signature against data. Returns True if valid."""
        try:
            self.public_key.verify(signature, data)
            return True
        except InvalidSignature:
            return False

    def public_key_bytes(self) -> bytes:
        """Return the public key as raw bytes (32 bytes for Ed25519)."""
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

    def to_dict(self) -> dict:
        """Serialize the key pair to a dict (private key PEM-encoded)."""
        private_pem = self.private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        public_pem = self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return {
            "private_key": private_pem.decode("utf-8"),
            "public_key": public_pem.decode("utf-8"),
        }


@dataclass
class Identity:
    """A cryptographic identity for a lab or agent in the LORL network."""

    lab_id: str
    key_pair: EdDSAKeyPair
    name: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    metadata: dict = field(default_factory=dict)

    @classmethod
    def create(cls, lab_id: str, name: str = "", metadata: Optional[dict] = None) -> "Identity":
        """Create a new identity with a fresh Ed25519 key pair."""
        return cls(
            lab_id=lab_id,
            key_pair=EdDSAKeyPair.generate(),
            name=name or lab_id,
            metadata=metadata or {},
        )

    @property
    def public_key_hex(self) -> str:
        """Return the public key as a hex string."""
        return self.key_pair.public_key_bytes().hex()

    @property
    def identity_hash(self) -> str:
        """Return a SHA-256 hash of the lab_id + public key for deduplication."""
        raw = f"{self.lab_id}:{self.public_key_hex}".encode()
        return hashlib.sha256(raw).hexdigest()

    def sign(self, data: bytes) -> bytes:
        """Sign arbitrary data."""
        return self.key_pair.sign(data)

    def verify(self, data: bytes, signature: bytes) -> bool:
        """Verify a signature."""
        return self.key_pair.verify(data, signature)

    def sign_json(self, data: dict) -> bytes:
        """Sign a dict by hashing its JSON representation."""
        import json
        payload = json.dumps(data, sort_keys=True).encode()
        return self.sign(payload)

    def to_dict(self) -> dict:
        """Serialize identity to dict (without private key for safety)."""
        return {
            "lab_id": self.lab_id,
            "name": self.name,
            "public_key": self.public_key_hex,
            "identity_hash": self.identity_hash,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }
