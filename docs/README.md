# Marcbantu Africa — Documentation

Complete documentation for the Marcbantu Africa platform.

---

## 📚 Contents

| Document | Purpose | Audience |
| :--- | :--- | :--- |
| [API.md](./API.md) | Full API reference — every endpoint, request, response | Backend devs, integrators |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | System design, data flow, tech stack | All engineers |
| [DATABASE.md](./DATABASE.md) | Schema reference — all 40+ tables | Backend devs, DBAs |
| [DEPLOYMENT.md](./DEPLOYMENT.md) | Deploy to production | DevOps, leads |
| [AFRICAS_TALKING.md](./AFRICAS_TALKING.md) | SMS/USSD/Voice setup | Backend devs |
| [CLOUDFLARE.md](./CLOUDFLARE.md) | D1, R2, KV, Queues setup | DevOps |
| [FRONTEND.md](./FRONTEND.md) | Frontend architecture & patterns | Frontend devs |
| [CONTRIBUTING.md](./CONTRIBUTING.md) | How to contribute | Contributors |
| [SECURITY.md](./SECURITY.md) | Security model & best practices | All engineers |

---

## 🚀 Quick Start

```bash
git clone https://github.com/your-org/marcbantu.git
cd marcbantu
npm install
wrangler login
make setup
make dev