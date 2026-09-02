"""
Tests for LORL-9.1 Identity Module — Ed25519 cryptographic identity.
"""

from lorl.core.identity import EdDSAKeyPair, Identity


class TestEdDSAKeyPair:
    def test_generate_creates_keypair(self):
        kp = EdDSAKeyPair.generate()
        assert kp.private_key is not None
        assert kp.public_key is not None

    def test_sign_and_verify_roundtrip(self):
        kp = EdDSAKeyPair.generate()
        data = b"treaty agreement between lab-001 and lab-002"
        signature = kp.sign(data)
        assert isinstance(signature, bytes)
        assert len(signature) == 64  # Ed25519 signatures are 64 bytes
        assert kp.verify(data, signature) is True

    def test_verify_rejects_tampered_data(self):
        kp = EdDSAKeyPair.generate()
        data = b"original data"
        signature = kp.sign(data)
        assert kp.verify(b"tampered data", signature) is False

    def test_verify_rejects_wrong_signature(self):
        kp = EdDSAKeyPair.generate()
        data = b"some data"
        fake_sig = b"\x00" * 64
        assert kp.verify(data, fake_sig) is False

    def test_public_key_bytes_length(self):
        kp = EdDSAKeyPair.generate()
        pk_bytes = kp.public_key_bytes()
        assert len(pk_bytes) == 32  # Ed25519 public keys are 32 bytes


class TestIdentity:
    def test_create_generates_keypair(self):
        identity = Identity.create("lab-001")
        assert identity.lab_id == "lab-001"
        assert identity.key_pair is not None

    def test_identity_has_unique_public_keys(self):
        id1 = Identity.create("lab-001")
        id2 = Identity.create("lab-002")
        assert id1.public_key_hex != id2.public_key_hex

    def test_identity_hash_is_deterministic(self):
        identity = Identity.create("lab-001")
        assert identity.identity_hash == identity.identity_hash

    def test_identity_hash_differs_per_lab(self):
        id1 = Identity.create("lab-001")
        id2 = Identity.create("lab-002")
        assert id1.identity_hash != id2.identity_hash

    def test_sign_json_roundtrip(self):
        identity = Identity.create("lab-001")
        data = {"treaty": "collaboration", "terms": {"revenue_share": 0.3}}
        signature = identity.sign_json(data)
        import json
        payload = json.dumps(data, sort_keys=True).encode()
        assert identity.verify(payload, signature) is True

    def test_to_dict_excludes_private_key(self):
        identity = Identity.create("lab-001", name="Lab Alpha")
        d = identity.to_dict()
        assert "private_key" not in d
        assert "public_key" in d
        assert d["lab_id"] == "lab-001"
        assert d["name"] == "Lab Alpha"
        assert len(d["public_key"]) == 64  # 32 bytes as hex
