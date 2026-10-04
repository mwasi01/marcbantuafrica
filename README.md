# Marcbantu Africa

Smart farm management platform for African farmers. Helps small to medium-scale farmers plan, record, track, and grow profitable farm businesses.

## What's Inside

- **Frontend** — 20 HTML pages, PWA-installable, offline-first
- **Backend** — Python API on Cloudflare Workers
- **Database** — Cloudflare D1 (SQLite)
- **Files** — Cloudflare R2
- **Cache** — Cloudflare KV
- **Jobs** — Cloudflare Queues + Cron
- **SMS/USSD** — Africa's Talking
- **AI** — Cloudflare Workers AI

## Quick Start

### Prerequisites

- Node.js 18+
- Python 3.11+
- Wrangler CLI: `npm install -g wrangler`
- Cloudflare account

### Install

```bash
git clone https://github.com/your-org/marcbantu.git
cd marcbantu
npm install
wrangler login