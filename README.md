# ReviewPulse AI

Agentic product intelligence from app-store reviews. Turns raw Google Play / App
Store reviews into structured, evidence-backed product intelligence: themes,
sentiment, verbatim quotes, cross-signal correlations, and prioritised
recommendations — with a confidence and volume signal on every insight.

- **Design:** [docs/problemstatement.md](docs/problemstatement.md)
- **Build roadmap:** [docs/phasewise-architecture.md](docs/phasewise-architecture.md)
- **Edge cases / pre-mortem:** [docs/edge-cases.md](docs/edge-cases.md)

> **Cost posture:** 100% free tiers and open-source — no paid subscriptions, no
> API keys behind billing, no credit card. The single synthesis call runs on the
> Gemini **free tier**; the agent's reasoning loop runs on the Groq **free tier**.
> Net cost: $0. (See architecture Appendix C.)

## Status: All 7 phases implemented (backend feature-complete)

- **Phase 0 — Foundation:** FastAPI backend, model-abstraction seam (Groq /
  Gemini / fastembed), DB schema, Qdrant bootstrap, `/health`, Next.js shell.
- **Phase 1 — Ingestion I:** Review Collector (Play / App Store) + a deterministic
  Data Cleaner (PII, Unicode, dates, dedup, spam) → `reviews`. Endpoint: `POST /ingest`.
- **Phase 2 — Ingestion II:** Embedder (fastembed → Qdrant), VADER sentiment,
  KMeans theme clustering, TF-IDF keywords → DB + vectors. Endpoint: `POST /enrich`.
- **Phase 3 — Query Tools:** Quote Retriever (filtered vector search → verbatim
  quotes, with relevance threshold + dedup) and Stats Engine (counts, sentiment
  split, theme distribution, suppressed-base trends, impact×frequency).
  Endpoints: `POST /query/quotes`, `POST /query/stats/overview`.
- **Phase 4 — Agentic Core:** the Analyst Agent (plan→act→observe→judge→decide
  loop on the Groq free tier, structured-scoring fallback) + the Critic (sample /
  quote-support gating, denominator-scaled confidence). Constrained action set,
  decision-path cache, honest no-signal state — zero premium budget.
  Endpoint: `POST /analyze`.
- **Phase 5 — Synthesis & Orchestration:** one Gemini free-tier call writes the
  narrative + recommendations over the verified findings (output post-validated so
  it can't invent claims); hard premium ceiling + graceful degradation (quantitative
  report always returns); 8-section Report Renderer; cache + cold-start routing +
  single-flight. Endpoint: `POST /report`.
- **Phase 6 — Dashboard:** Next.js + Tailwind segmented UI — KPI cards, Trend Alert
  (suppressed on weak base), PM Priority Radar, Themes + sentiment, User Voices
  (verbatim), Trending Keywords, Recommendations, Confidence & Volume. Abortable
  refilter, accessible sentiment (colour + label), custom-range validation, honest
  no-signal state. Each panel binds to a tool or the agent. `next build` passes.
- **Phase 7 — Hardening & Ops:** best-effort observability hook (never blocks a
  report), Deep Analysis mode (opt-in, bounded extra premium budget), **embedded
  Qdrant** (no-signup local vectors), and deploy artifacts (backend Dockerfile,
  `render.yaml`, keep-warm GitHub Action, `docker-compose.yml`).

All of the above is local/free and deterministic where it must be (the Critic and
the structured reasoner are temperature-0 by nature; the loop is bounded and cached;
exactly one premium call per report, enforced in code).
Tests: `cd backend && python -m pytest` — **70 passing**, including determinism
re-run gates (Cleaner, enrichment), Stats div-by-zero / trend-suppression guards,
the agent's no-signal / iteration-ceiling / cache-replay guards, Phase 5's
premium-ceiling / graceful-degradation / synthesis-validation guards, and Phase 7's
Deep-Analysis budget + observability-never-blocks guards.

**Live-verified** (no signup): Groq reasoning, Gemini synthesis, and the full vector
layer — fastembed (384-dim) → embedded Qdrant → semantic retrieval
(`python -m scripts.smoke_vectors`).

## Repository layout

```
backend/            FastAPI app (ingestion + query paths)
  app/
    config.py       typed settings (the one place env is read)
    main.py         FastAPI entrypoint + /health
    health.py       per-dependency health checks
    models/         model-abstraction layer (reason→Groq, synthesize→Gemini, embed→fastembed)
    db/             async Postgres engine + ping
    vector/         Qdrant client + ping
  migrations/       001_init.sql  (schema v1)
  scripts/          bootstrap_qdrant.py
frontend/           Next.js shell that calls /health (Tailwind/ShadCN land in Phase 6)
docs/               design, roadmap, edge cases
```

## Run the backend (Phase 0)

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # Windows;  source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
cp .env.example .env               # then fill in free-tier credentials (optional for Phase 0)
uvicorn app.main:app --reload
```

- `http://localhost:8000/health` — per-dependency status JSON
- `http://localhost:8000/docs` — OpenAPI UI

With no credentials filled in, `/health` returns `status: ok` with each external
dependency marked `not_configured` and each model adapter marked `stub` — the
skeleton is healthy and awaiting config. Fill `.env` to turn dependencies green.

### Provision the free tiers (when ready)

1. **Supabase** (free Postgres) → copy the connection URI into `DATABASE_URL`,
   then apply `backend/migrations/001_init.sql` in the SQL editor.
2. **Qdrant Cloud** (free 1GB cluster) → set `QDRANT_URL` / `QDRANT_API_KEY`,
   then `python -m scripts.bootstrap_qdrant` to create the collection + indexes.
3. **Groq** (free key) → `GROQ_API_KEY` (reasoning loop, Phase 4).
4. **Google AI Studio** (free key) → `GEMINI_API_KEY` (synthesis, Phase 5).

## Run the frontend (Phase 0)

```bash
cd frontend
npm install
cp .env.local.example .env.local   # NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev                         # http://localhost:3000
```

## Phase 0 exit criteria

- [x] Monorepo scaffold (`backend/`, `frontend/`, `docs/`)
- [x] Typed settings + `.env` contracts
- [x] Model-abstraction layer (Groq / Gemini / fastembed adapters behind one seam)
- [x] DB schema v1 + Qdrant bootstrap (payload indexes on `review_date`, `rating`)
- [x] `/health` checks DB, Qdrant, and all three model adapters
- [x] Frontend shell renders live `/health`

Remaining for a full cloud demo: add a Postgres connection (Supabase free or local
docker-compose) for the DB-backed live run, patch Next.js (security advisory), and
deploy (Render + Vercel). Progressive streaming is the one deferred enhancement.
