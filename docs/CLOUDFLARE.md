
---

## 18.7 `docs/CLOUDFLARE.md`

```markdown
# Marcbantu Africa — Cloudflare Setup

Complete guide to Cloudflare D1, R2, KV, Workers, Queues.

---

## Why Cloudflare?

- **Global edge** — 300+ cities, low latency worldwide
- **Serverless** — no servers to manage
- **Cheap** — free tier covers 1,000+ farmers
- **Integrated** — Workers + D1 + R2 + KV in one platform
- **Python support** — via Pyodide (WASM)
- **No egress fees** on R2 — critical for photos/videos

---

## Prerequisites

- Cloudflare account (free): https://dash.cloudflare.com/sign-up
- Wrangler CLI: `npm install -g wrangler`
- Domain added to Cloudflare (for custom domains)

---

## Account Login

```bash
wrangler login