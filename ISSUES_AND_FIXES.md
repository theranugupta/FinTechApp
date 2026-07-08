# Issues & Fixes Log

A running record of problems hit while building the FinPay refund module and exactly how
each was resolved. Format for every entry: **Symptom → Root cause → Fix → Prevention.**

---

## 1. CORS: browser blocked all API calls from the frontend

**Symptom**
Browser console flooded with:
`Access to fetch at 'http://localhost:8100/api/...' from origin 'http://localhost:3100'
has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header is present`,
and every request showed `net::ERR_FAILED`. The page rendered but no data loaded.

**Root cause**
The FastAPI `CORSMiddleware` had a hardcoded allow-list of exactly `http://localhost:3000`.
Because ports 3000/8000 were busy on this machine, the frontend was moved to **3100** and the
backend to **8100**. The browser's origin (`:3100`) was no longer in the allow-list, so the
backend didn't send an `Access-Control-Allow-Origin` header and the browser blocked the
cross-origin response.

**Fix**
Switched to an origin **regex** that allows any localhost/127.0.0.1 port in development
([`backend/main.py`](backend/main.py)):
```python
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```
Then restarted the backend so the new middleware took effect. Verified with:
`curl -i .../TXN-10001 -H "Origin: http://localhost:3100"` → response now includes
`access-control-allow-origin: http://localhost:3100`.

**Prevention**
Keep the dev origin flexible (regex) and, in production, drive the exact allow-list from an
env var. Never hardcode a single dev port. Remember CORS is enforced by the **browser** —
`curl` succeeds even when the browser is blocked, so test from the browser too.

---

## 2. Build "failing": all JS/CSS chunks 404 in the browser

**Symptom**
`localhost` document loaded 200, but `layout.css`, `main-app.js`, `page.js`, `layout.js`,
and `app-pages-internals.js` were all **404**, and `favicon.ico` was **500**. The page had
no styling or interactivity.

**Root cause**
`npm run build` (a **production** build) was run several times **while the `next dev` server
was still running**. `next build` overwrites the `.next/` directory with production
artifacts, but the live dev server keeps serving its in-memory manifest that references the
old **dev** chunk URLs. Those dev chunks no longer exist on disk → 404. The dev server and
the on-disk `.next` were out of sync.

**Fix**
```bash
pkill -f "next dev -p 3100"     # stop the dev server
rm -rf .next                     # delete the corrupted/mixed build cache
npx next dev -p 3100             # start dev fresh (regenerates dev chunks)
```
Verified every `/_next/static/*.js|css` now returns 200 and favicon is 200.

**Prevention**
Don't run `next build` and `next dev` against the same project simultaneously. Use `next dev`
for local work; run `next build` only in a separate, non-serving context (CI, or after
stopping the dev server). If the dev server ever gets into a weird state, `rm -rf .next` and
restart is the reliable reset.

---

## 3. Port already in use (8000 and 3000)

**Symptom**
Backend startup log: `[Errno 98] error while attempting to bind on address
('127.0.0.1', 8000): address already in use`. Frontend default port 3000 was also occupied.

**Root cause**
Other services on the machine were already listening on the conventional dev ports.

**Fix**
Moved the app to free ports — backend **8100**, frontend **3100** — checked first with
`ss -ltn`. Pointed the frontend at the backend via `frontend/.env.local`:
`NEXT_PUBLIC_API_URL=http://localhost:8100`.
(This port change is what later exposed the CORS issue in #1.)

**Prevention**
Probe ports before starting (`ss -ltn | grep :PORT`). Keep the API base URL configurable via
`NEXT_PUBLIC_API_URL` and the backend port via a CLI flag, so ports are never hardcoded.

---

## 4. shadcn CLI generated the wrong toolchain (Base UI + Tailwind v4)

**Symptom**
Frontend build errors: `The 'border-border' class does not exist`, unknown `@import
"shadcn/tailwind.css"`, and TypeScript errors like `Property 'asChild' does not exist` on
`DialogTrigger`.

**Root cause**
`npx shadcn@latest init` defaulted to its newest style, generating components based on
**Base UI** (`@base-ui/react`, which uses a `render` prop, not `asChild`) and **Tailwind v4**
CSS (`@import`, `oklch()` colors, `data-open:` variants). But the project was scaffolded with
`create-next-app@14`, which uses **Tailwind v3**. The generated components and stylesheet
didn't match the installed Tailwind/primitives.

**Fix**
Replaced the generated primitives with the **classic Radix-based shadcn v3** components
(`button`, `dialog`, `input`, `label`, `card`, `badge`, later `dropdown-menu`), installed
`@radix-ui/react-dialog`, `@radix-ui/react-label`, `@radix-ui/react-slot`,
`@radix-ui/react-dropdown-menu`, and rewrote `globals.css` + `tailwind.config.ts` in the
standard Tailwind v3 shadcn format (HSL CSS variables + full color mapping + `tailwindcss-animate`).

**Prevention**
Pin the toolchain versions and match the shadcn style to the installed Tailwind major
version. When mixing scaffolds, verify Tailwind v3 vs v4 up front — their stylesheet syntax
and shadcn component variants are incompatible.

---

## 5. Next.js `next/font` error: "Unknown font `Geist`"

**Symptom**
`next build` failed with `next/font error: Unknown font 'Geist'` from `layout.tsx`.

**Root cause**
The shadcn init injected `import { Geist } from "next/font/google"`. `Geist` as a Google font
isn't available in Next **14.2**'s font list (and there's no network to fetch it), while the
local Geist `.woff` files were already present from the scaffold.

**Fix**
Removed the `next/font/google` `Geist` import and kept only the existing `localFont` setup
pointing at `./fonts/GeistVF.woff` and `GeistMonoVF.woff` ([`layout.tsx`](frontend/src/app/layout.tsx)).

**Prevention**
Prefer the local font files that `create-next-app` already ships; only use `next/font/google`
for fonts confirmed supported by the installed Next version, and only when online.

---

## 6. Python 3.8: `tuple[int, dict]` type hint crashed on import

**Symptom**
Importing the backend on Python 3.8 would raise `TypeError: 'type' object is not
subscriptable` from the `create_refund` return annotation.

**Root cause**
Subscripting built-in generics (`tuple[...]`, `list[...]`) in annotations is only valid at
runtime from **Python 3.9+**. This machine runs **Python 3.8**, which evaluates the
annotation eagerly and fails.

**Fix**
Added `from __future__ import annotations` at the top of
[`backend/refund_logic.py`](backend/refund_logic.py), which makes all annotations lazy
strings — so `tuple[int, dict]` is never evaluated at runtime.

**Prevention**
On 3.8/3.9 codebases, add `from __future__ import annotations` to any module that uses
built-in generic subscripting, or use `typing.Tuple`/`typing.List`. Pin the Python version in
the project docs so contributors know the floor.

---

## Quick reference — how to run cleanly

```bash
# Backend (port 8100)
cd backend && . .venv/bin/activate && python -m uvicorn main:app --port 8100

# Frontend (port 3100) — set the API URL once
cd frontend
echo "NEXT_PUBLIC_API_URL=http://localhost:8100" > .env.local
npx next dev -p 3100

# If the dev server ever serves 404 chunks:
pkill -f "next dev" && rm -rf .next && npx next dev -p 3100
```
Do **not** run `npm run build` while `next dev` is running against the same project.
