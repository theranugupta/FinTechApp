# Encryption — TLS + application-layer payload encryption

Two independent layers protect the refund request data. **They solve different problems;
neither replaces the other.**

| Layer | Protects against | Mechanism |
|---|---|---|
| **TLS (HTTPS)** | Anyone sniffing the network wire | TLS 1.2/1.3 between browser and server |
| **App-layer payload encryption** | Body being read where TLS is terminated (proxies, logs, intermediaries); at-rest exposure of the raw body | Hybrid RSA-OAEP + AES-256-GCM on the request body |

---

## Why both, and the honest caveat

The network tab originally showed the refund body in plaintext because the app ran on
**`http://localhost`** — plain HTTP, no TLS. The correct, primary fix is **TLS**: it
encrypts everything on the wire with real key exchange, and it's what every payment API
relies on. A packet sniffer now sees only ciphertext.

We *also* added application-layer encryption as **defense-in-depth**. Be clear-eyed about
what it does and doesn't do:

- ✅ The request body is encrypted before it leaves the page, so anything that sees the
  HTTP body *after* TLS termination (a reverse proxy, an access log, an APM tool) sees
  ciphertext, not the amount/reason.
- ✅ AES-GCM authenticates the body — a tampered ciphertext is rejected (verified by test).
- ❌ It is **not** a substitute for TLS. The browser does the encryption, so the plaintext
  and the fetched public key are fully visible in *this* browser's own dev tools. You
  cannot hide data from the user's own browser with client-side crypto.
- ❌ It does not authenticate the *user* — that's the bearer token's job.

So: **TLS is the real protection; app-layer is a belt-and-suspenders extra.** Presenting
app-layer encryption alone as "the data is now secure" would be misleading.

---

## How the app-layer encryption works (hybrid RSA + AES-GCM)

RSA can only encrypt small blobs, so we use the standard hybrid pattern: encrypt the data
with a fast symmetric cipher (AES-GCM) and encrypt (wrap) that AES key with RSA.

```
Browser (src/lib/crypto.ts)                    Server (backend/crypto_utils.py)
──────────────────────────                     ────────────────────────────────
GET /api/crypto/public-key  ───────────────▶   returns RSA-2048 public key (PEM)
import public key (Web Crypto)

generate AES-256-GCM key + 12-byte IV
ciphertext = AES-GCM(body, key, iv)            (body = {amount, reason} JSON)
encryptedKey = RSA-OAEP(key, pubKey)

POST .../refunds
  { encryptedKey, iv, ciphertext }  ────────▶   RSA-OAEP decrypt encryptedKey -> AES key
                                                 AES-GCM decrypt ciphertext   -> body JSON
                                                 (auth tag verified -> tamper-proof)
                                                 validate as RefundRequest -> business rules
```

- **Algorithms:** RSA-2048 / RSA-OAEP with SHA-256; AES-256-GCM with a 96-bit IV.
- **Key lifetime:** the RSA keypair is generated fresh on server start (dev only). In
  production it would come from a KMS/secret manager and be rotated — never generated at boot.
- **Backward compatible:** the endpoint accepts *either* an encrypted envelope *or* plain
  JSON (`parse_refund_body` in `main.py`), so the existing test-suite (plain JSON) is
  unchanged and the browser always sends encrypted.

### Files
- `backend/crypto_utils.py` — RSA keypair, `public_key_pem()`, `decrypt_envelope()`.
- `backend/main.py` — `GET /api/crypto/public-key`; `parse_refund_body()` detects & decrypts.
- `frontend/src/lib/crypto.ts` — Web Crypto encryption (`encryptPayload`).
- `frontend/src/lib/api.ts` — `createRefund()` encrypts before POST.
- `backend/test_encryption.py` — round-trip + tamper-rejection + rule-enforcement tests.

---

## Running with HTTPS

A self-signed cert is generated at `backend/certs/` (via `openssl`). Because it isn't from
a trusted CA (no `mkcert` on this machine), **the browser shows a one-time warning you must
accept** for each origin.

```bash
# Backend over TLS
cd backend && . .venv/bin/activate
python -m uvicorn main:app --port 8100 \
  --ssl-keyfile certs/key.pem --ssl-certfile certs/cert.pem

# Frontend over TLS (reuses the same cert)
cd frontend
echo "NEXT_PUBLIC_API_URL=https://localhost:8100" > .env.local
npx next dev -p 3100 --experimental-https \
  --experimental-https-key ../backend/certs/key.pem \
  --experimental-https-cert ../backend/certs/cert.pem
```

**Accept the certs once (required):**
1. Open **https://localhost:8100/docs** → accept the "not secure" warning (trusts the API cert).
2. Open **https://localhost:3100** → accept the warning. The app now loads and can call the API.

Without step 1 the browser blocks the frontend→backend `fetch` with
`net::ERR_CERT_AUTHORITY_INVALID`. With `mkcert` installed you'd get a locally-trusted cert
and skip the warnings entirely.

### Regenerate the cert
```bash
cd backend && mkdir -p certs
openssl req -x509 -newkey rsa:2048 -nodes -keyout certs/key.pem -out certs/cert.pem \
  -days 365 -subj "/CN=localhost" -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
```

---

## Verification performed
- Backend serves over TLS (`openssl s_client` shows the localhost cert).
- Live round-trip: a client fetched the public key over HTTPS, encrypted `{amount, reason}`,
  and POSTed the envelope — the wire payload was ciphertext and the backend returned `201`
  with the correct decrypted amount.
- `pytest` (23 tests) includes: public-key endpoint, encrypted refund decrypts & processes,
  encrypted body still enforces rules (amount 0 → 422), tampered ciphertext → 400.

## Frontend vs backend, updated
Encryption is transport/representation, not a business rule. The backend still enforces
every money rule *after* decryption. Never trust the client: an "encrypted" body is still
validated and authorized exactly like a plain one.
