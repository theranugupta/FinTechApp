"""
Application-layer payload encryption (defense-in-depth ON TOP of TLS).

Scheme: hybrid RSA + AES-GCM (the standard way to encrypt arbitrary-length data
with a public key).

  1. The server holds an RSA-2048 keypair. The public key is served at
     GET /api/crypto/public-key. The private key never leaves the server.
  2. For each request the client generates a random AES-256-GCM key + 12-byte IV,
     encrypts the JSON body with AES-GCM, and encrypts (wraps) the AES key with the
     server's RSA public key (RSA-OAEP, SHA-256).
  3. The client sends an envelope { encryptedKey, iv, ciphertext } (all base64).
  4. The server unwraps the AES key with its RSA private key, then AES-GCM-decrypts
     the body. AES-GCM also authenticates the ciphertext (tamper-evident).

IMPORTANT (honest caveat): this is NOT a substitute for TLS. Because the browser
performs the encryption, the plaintext and the fetched public key are visible in the
browser's own dev tools. TLS is what actually protects the data on the wire. This
layer is defense-in-depth (e.g. protects the body from intermediaries that terminate
TLS, and makes at-rest logging of the raw body harder). See ENCRYPTION.md.

The keypair is generated fresh on process start (fine for dev). In production you would
load a managed key from a KMS/secret store and rotate it, never generate at boot.
"""

import base64
import json
from typing import Any, Dict

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# Generate the server RSA keypair once, at import time.
_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_public_key = _private_key.public_key()

_OAEP = padding.OAEP(
    mgf=padding.MGF1(algorithm=hashes.SHA256()),
    algorithm=hashes.SHA256(),
    label=None,
)


def public_key_pem() -> str:
    """Return the server's RSA public key in PEM (SPKI) form for the client to import."""
    return _public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()


def looks_like_envelope(body: Dict[str, Any]) -> bool:
    """True if a parsed JSON body is an encrypted envelope rather than a plain payload."""
    return isinstance(body, dict) and {"encryptedKey", "iv", "ciphertext"} <= set(body)


def decrypt_envelope(envelope: Dict[str, str]) -> Dict[str, Any]:
    """Decrypt an { encryptedKey, iv, ciphertext } envelope back into a plain dict.

    Raises ValueError on any failure (bad key, tampered ciphertext, malformed base64).
    The caller maps that to a 400 so we never leak crypto internals to the client.
    """
    try:
        enc_key = base64.b64decode(envelope["encryptedKey"])
        iv = base64.b64decode(envelope["iv"])
        ciphertext = base64.b64decode(envelope["ciphertext"])  # includes GCM auth tag
    except (KeyError, ValueError, TypeError) as e:
        raise ValueError(f"Malformed encrypted envelope: {e}")

    # 1. Unwrap the AES key with the RSA private key.
    aes_key = _private_key.decrypt(enc_key, _OAEP)

    # 2. AES-GCM decrypt (also verifies the auth tag -> rejects tampering).
    plaintext = AESGCM(aes_key).decrypt(iv, ciphertext, None)

    # 3. The plaintext is the original JSON body.
    return json.loads(plaintext.decode())
