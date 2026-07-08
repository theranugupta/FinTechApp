// Client-side payload encryption using the browser's native Web Crypto API
// (no external library). Mirrors backend/crypto_utils.py:
//   - fetch the server RSA public key
//   - generate a one-time AES-256-GCM key + 12-byte IV
//   - AES-GCM encrypt the JSON body
//   - RSA-OAEP (SHA-256) wrap the AES key with the server public key
//   - send { encryptedKey, iv, ciphertext } (all base64)
//
// NOTE: this is defense-in-depth ON TOP of TLS, not a replacement. The plaintext and the
// fetched public key are visible in this browser's dev tools by design. See ENCRYPTION.md.

// Read the API base directly (not imported from api.ts) to avoid a circular import.
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Envelope = {
  encryptedKey: string;
  iv: string;
  ciphertext: string;
};

function bufToB64(buf: ArrayBuffer): string {
  const bytes = new Uint8Array(buf);
  let bin = "";
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
  return btoa(bin);
}

function pemToDer(pem: string): ArrayBuffer {
  const body = pem
    .replace(/-----BEGIN PUBLIC KEY-----/, "")
    .replace(/-----END PUBLIC KEY-----/, "")
    .replace(/\s+/g, "");
  const bin = atob(body);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return bytes.buffer;
}

// Cache the imported public key so we don't refetch on every request.
let cachedKey: Promise<CryptoKey> | null = null;

function getServerPublicKey(): Promise<CryptoKey> {
  if (cachedKey) return cachedKey;
  cachedKey = (async () => {
    const res = await fetch(`${API_BASE}/api/crypto/public-key`);
    if (!res.ok) throw new Error("Could not fetch server public key");
    const { public_key } = await res.json();
    return crypto.subtle.importKey(
      "spki",
      pemToDer(public_key),
      { name: "RSA-OAEP", hash: "SHA-256" },
      false,
      ["encrypt"]
    );
  })();
  return cachedKey;
}

/** Encrypt an arbitrary JSON-serialisable payload into an envelope for the backend. */
export async function encryptPayload(payload: unknown): Promise<Envelope> {
  const publicKey = await getServerPublicKey();

  // 1. One-time AES-256-GCM key + 12-byte IV (nonce).
  const aesKey = await crypto.subtle.generateKey(
    { name: "AES-GCM", length: 256 },
    true,
    ["encrypt"]
  );
  const iv = crypto.getRandomValues(new Uint8Array(12));

  // 2. AES-GCM encrypt the JSON body (output includes the 16-byte auth tag).
  const plaintext = new TextEncoder().encode(JSON.stringify(payload));
  const ciphertext = await crypto.subtle.encrypt(
    { name: "AES-GCM", iv },
    aesKey,
    plaintext
  );

  // 3. RSA-OAEP wrap the raw AES key with the server public key.
  const rawAesKey = await crypto.subtle.exportKey("raw", aesKey);
  const encryptedKey = await crypto.subtle.encrypt(
    { name: "RSA-OAEP" },
    publicKey,
    rawAesKey
  );

  return {
    encryptedKey: bufToB64(encryptedKey),
    iv: bufToB64(iv.buffer),
    ciphertext: bufToB64(ciphertext),
  };
}
