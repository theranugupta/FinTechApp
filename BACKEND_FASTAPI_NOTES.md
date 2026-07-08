# FastAPI for Express / Node developers

A quick reference mapping the Express/Node patterns you know to their FastAPI equivalents,
with **verified line references** into this repo's backend. Useful if you're coming from
Node and learning FastAPI.

## Pattern mapping (all confirmed present in the code)

| Express / Node | FastAPI equivalent | Where in this repo |
|---|---|---|
| `router.post("/path", handler)` | `@app.post("/path")` (and `@app.get`) | [`main.py:137`](backend/main.py#L137), [`:90`](backend/main.py#L90), [`:108`](backend/main.py#L108) |
| middleware (`app.use`, per-route guards) | `Depends()` dependency injection | [`main.py:147-148`](backend/main.py#L147-L148) |
| `req.body` + manual validation | Pydantic model — auto-validates, auto-**422** | body: [`main.py:144`](backend/main.py#L144); model: [`schemas.py:15-20`](backend/schemas.py#L15-L20) |
| `req.headers["idempotency-key"]` | `idempotency_key: str = Header(...)` | [`main.py:146`](backend/main.py#L146) |
| `res.status(409).json(...)` | `raise HTTPException(409, detail=...)` | logic: [`refund_logic.py:111`](backend/refund_logic.py#L111) → HTTP: [`main.py:169`](backend/main.py#L169) |

## Side-by-side

**1. Route declaration**
```js
// Express
router.post("/api/admin/transactions/:transactionId/refunds", handler);
```
```python
# FastAPI  (main.py:137)
@app.post("/api/admin/transactions/{transaction_id}/refunds",
          response_model=RefundResponse, status_code=201)
def create_refund_endpoint(...): ...
```

**2. Middleware → dependency injection**
```js
// Express: an auth middleware runs before the handler
router.post("/...", requireAuth, requirePermission, handler);
```
```python
# FastAPI: dependencies are declared as parameters and run before the body (main.py:147-148)
user: User = Depends(get_current_user)     # raises 401 if the token is bad
session: Session = Depends(get_session)    # yields a DB session, closes it after
```
`get_current_user` lives in [`auth.py`](backend/auth.py) and raises `HTTPException(401)` for a
missing/invalid `Authorization: Bearer` header — the handler body never runs if it fails.

**3. Body validation**
```js
// Express: validate by hand, return 400 yourself
if (!req.body.amount || req.body.amount <= 0) return res.status(400).json({...});
```
```python
# FastAPI: declare a Pydantic model; invalid input is rejected with 422 before your code runs
class RefundRequest(BaseModel):                 # schemas.py:15
    amount: int = Field(gt=0)                   # gt=0 => zero/negative auto-rejected (422)
    reason: str = Field(min_length=1, max_length=500)
```
Note: we still **re-check** the business amount rules server-side in `refund_logic.py`
(> 0, ≤ original, over-refund) — the edge validation is a convenience, not the source of truth.

**4. Reading a header**
```js
const key = req.headers["idempotency-key"];
```
```python
# main.py:146
idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key")
```

**5. Error responses**
```js
return res.status(409).json({ error: "..." });
```
```python
raise HTTPException(status_code=409, detail="...")
```

## Two deliberate design choices (not accidental)

**A. Business layer raises a domain error, not `HTTPException`.**
`refund_logic.create_refund` raises `RefundError(status_code, message, outcome)` for every
rule failure (e.g. `RefundError(409, ...)` at [`refund_logic.py:111`](backend/refund_logic.py#L111)).
The endpoint catches it and converts to HTTP once at [`main.py:168-169`](backend/main.py#L168-L169):
```python
except refund_logic.RefundError as e:
    raise HTTPException(status_code=e.status_code, detail=e.message)
```
Why: the money logic stays framework-agnostic (easy to unit-test, no web imports). The client
still sees exactly `HTTPException(409)`. The three 409 sources are idempotency conflict
(line 111), non-SUCCESS eligibility (line 140), and the concurrent same-key race (line 251).

**B. `Idempotency-Key` is optional at the framework layer, enforced manually as 400.**
Rather than `Header(...)` (framework-required → generic **422**), we use
`Header(default=None)` and then:
```python
# main.py:151-153
if not idempotency_key:
    raise HTTPException(status_code=400, detail="Idempotency-Key header is required")
```
Why: a money endpoint deserves an explicit, human-readable **400** ("Idempotency-Key header
is required") instead of FastAPI's generic validation 422. The key is still effectively
mandatory. To match a strict framework-required header instead, change the parameter to
`idempotency_key: str = Header(alias="Idempotency-Key")` and drop the manual check — a
missing header then returns 422.

## Full request lifecycle for `POST .../refunds`

```
Request
  → Depends(get_current_user)      # 401 if unauthenticated            (auth.py)
  → Pydantic RefundRequest         # 422 if amount<=0 / bad body       (schemas.py)
  → Header Idempotency-Key         # 400 if missing                    (main.py:151)
  → has_refund_permission()        # 403 if no permission              (main.py:156)
  → refund_logic.create_refund()   # inside one DB transaction:        (refund_logic.py)
        idempotency replay / 409 conflict
        404 not found · 403 merchant scope · 409 not eligible
        422 currency · 422 amount · 422 over-refund
        create Refund + LedgerEntry + IdempotencyRecord + AuditLog
  → 201 Created + RefundResponse    (or replayed original response)
```
