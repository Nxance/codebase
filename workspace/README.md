# Nxance workspace — **phase closed**

See **[CLOSEOUT.md](CLOSEOUT.md)** for final sign-off, what’s shipped, and what’s next phase.

---

## Run (quick)

```bash
# 1) API
cd product/mbp && ./run.sh          # http://127.0.0.1:8000

# 2) Web portal
cd product/web-portal && python3 -m http.server 5500   # http://127.0.0.1:5500

# 3) Android
cd product/mobile && flutter run    # API host 10.0.2.2:8000 on emulator
```

Unlock: `DEMO-UNLOCK`

---

## Map

```
Nxance/
├── CLOSEOUT.md           ← phase closed — read this
├── README.md             ← you are here
├── INDEX.md              ← searchable file catalog
├── product/
│   ├── mbp/              ← intelligence API + training
│   ├── mobile/           ← Flutter Android (navy)
│   ├── web-portal/       ← marketing + web app (navy)
│   └── shared/           ← navy palette
├── docs/                 ← product / tech / roadmap / fundraising
├── prototypes/           ← old experiments
└── archive/              ← duplicates
```

| If you want… | Go to |
|--------------|--------|
| Phase status / deferred work | [CLOSEOUT.md](CLOSEOUT.md) |
| Search all docs | [INDEX.md](INDEX.md) |
| Architecture (quant→ML→DL) | [docs/03-technical/intelligence-architecture-rethink.md](docs/03-technical/intelligence-architecture-rethink.md) |
| India data + training | [product/mbp/data/INDIA_DATA_PLATFORM.md](product/mbp/data/INDIA_DATA_PLATFORM.md) |
| Investor one-pagers | [docs/06-fundraising/](docs/06-fundraising/) |

---

**One line:** Demo-ready MBP + navy Flutter + web portal + India training stack are **shipped for this phase**. Production CAS/payments/store = **next phase**.
