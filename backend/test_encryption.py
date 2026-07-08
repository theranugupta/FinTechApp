"""
Tests for app-layer payload encryption. We simulate the browser client: fetch the
server public key, build an { encryptedKey, iv, ciphertext } envelope with RSA-OAEP +
AES-GCM, POST it, and assert the server decrypts and processes it like a plain body.
"""

import base64
import json
import os

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from conftest import headers

URL = "/api/admin/transactions/TXN-10001/refunds"

_OAEP = padding.OAEP(
    mgf=padding.MGF1(algorithm=hashes.SHA256()),
    algorithm=hashes.SHA256(),
    label=None,
)


def _encrypt_envelope(public_key_pem: str, payload: dict) -> dict:
    """Client-side encryption, mirroring what the frontend Web Crypto code does."""
    public_key = serialization.load_pem_public_key(public_key_pem.encode())
    aes_key = os.urandom(32)  # AES-256
    iv = os.urandom(12)       # GCM nonce
    plaintext = json.dumps(payload).encode()
    ciphertext = AESGCM(aes_key).encrypt(iv, plaintext, None)  # ciphertext || tag
    enc_key = public_key.encrypt(aes_key, _OAEP)
    return {
        "encryptedKey": base64.b64encode(enc_key).decode(),
        "iv": base64.b64encode(iv).decode(),
        "ciphertext": base64.b64encode(ciphertext).decode(),
    }


def test_public_key_endpoint_returns_pem(client):
    r = client.get("/api/crypto/public-key")
    assert r.status_code == 200
    assert "BEGIN PUBLIC KEY" in r.json()["public_key"]


def test_encrypted_refund_is_decrypted_and_processed(client):
    pub = client.get("/api/crypto/public-key").json()["public_key"]
    envelope = _encrypt_envelope(pub, {"amount": 1200, "reason": "encrypted refund"})
    r = client.post(URL, json=envelope, headers=headers("admin-token", "enc-1"))
    assert r.status_code == 201
    assert r.json()["amount"] == 1200
    assert r.json()["status"] == "PENDING"


def test_encrypted_refund_still_enforces_rules(client):
    # An encrypted body must be validated just like a plain one: amount 0 -> 422.
    pub = client.get("/api/crypto/public-key").json()["public_key"]
    envelope = _encrypt_envelope(pub, {"amount": 0, "reason": "bad"})
    r = client.post(URL, json=envelope, headers=headers("admin-token", "enc-2"))
    assert r.status_code == 422


def test_tampered_ciphertext_is_rejected(client):
    pub = client.get("/api/crypto/public-key").json()["public_key"]
    envelope = _encrypt_envelope(pub, {"amount": 500, "reason": "tamper"})
    # Flip a byte in the ciphertext -> AES-GCM auth tag check must fail -> 400.
    bad = bytearray(base64.b64decode(envelope["ciphertext"]))
    bad[0] ^= 0x01
    envelope["ciphertext"] = base64.b64encode(bytes(bad)).decode()
    r = client.post(URL, json=envelope, headers=headers("admin-token", "enc-3"))
    assert r.status_code == 400
