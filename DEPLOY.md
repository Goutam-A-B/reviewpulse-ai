# Deploying ReviewPulse AI

Nothing is hosted by default — follow this to put it online. The deploy is a split
(this is deliberate, not a limitation of the build):

| Piece | Host | Why |
|---|---|---|
| Frontend (Next.js) | **Vercel** (free Hobby) | what Vercel is built for |
| Backend (FastAPI + ML) | **Render** (free web tier, Docker) | Vercel can't run a long-lived Python ML server + vector store |
| Database | **Supabase** (free) | already provisioned |
| Vectors | **Qdrant Cloud** (free) | embedded local mode does **not** persist on Render's ephemeral disk |
| Models | Groq + Gemini (free tiers) | reasoning + the one synthesis call |

> **Why not the whole thing on Vercel?** The backend runs fastembed (ONNX) and
> scikit-learn and holds a Qdrant store — that needs a persistent, long-running
> process. Vercel serverless functions are short-lived with an ephemeral filesystem,
> so the backend goes to Render and Vercel hosts only the frontend.

---

## 0. Push to GitHub (required first — both hosts deploy from git)

```bash
git remote add origin https://github.com/<you>/reviewpulse-ai.git
git push -u origin main
```
`backend/.env` is gitignored, so your secrets are **not** pushed.

## 1. Qdrant Cloud (free, ~2 min)

1. https://cloud.qdrant.io → sign up → **Create free cluster**.
2. Copy the **cluster URL** and an **API key**.
3. You'll set `QDRANT_URL` + `QDRANT_API_KEY` on the backend (step 2) and leave
   `QDRANT_LOCAL_PATH` blank. The collection is created automatically on first
   enrichment (or run `python -m scripts.bootstrap_qdrant`).

## 2. Backend → Render (free)

1. https://render.com → **New → Web Service** → connect your GitHub repo.
2. Render reads `render.yaml` (Docker, context `./backend`). Health check: `/health`.
3. Set environment variables (Dashboard → Environment):
   - `DATABASE_URL` — your Supabase **Session pooler** URI (URL-encode any `@` in the password as `%40`)
   - `QDRANT_URL`, `QDRANT_API_KEY` — from step 1
   - `GROQ_API_KEY`, `GEMINI_API_KEY`
   - `FRONTEND_ORIGIN` — your Vercel URL (fill after step 3, then redeploy)
4. Deploy. Note the backend URL, e.g. `https://reviewpulse-backend.onrender.com`.

> **Free-tier RAM (512 MB):** warm reports (stats + quotes + 1 Gemini call) fit fine.
> Cold-start *ingestion* of a brand-new app loads fastembed + scikit-learn and may be
> tight. For a smooth interview demo, pre-ingest a few candidate apps locally
> (`cd backend && python -m scripts.demo_live <store_app_id> <name>`) so the live
> request is a fast warm report. Heavy on-demand ingestion may need a paid instance.

## 3. Frontend → Vercel (free)

1. https://vercel.com → **Add New → Project** → import your repo.
2. **Root Directory: `frontend`** (important).
3. Framework preset: **Next.js** (auto-detected).
4. Environment variable: `NEXT_PUBLIC_API_URL = https://<your-render-backend>`.
5. Deploy. Your live link is the Vercel URL.
6. Back in Render, set `FRONTEND_ORIGIN` to this Vercel URL and redeploy (CORS).

## 4. Keep-warm (free, optional)

The Render free tier sleeps when idle. The included GitHub Action
(`.github/workflows/keep-warm.yml`) pings `/health` every 10 min — set repo secret
`BACKEND_HEALTH_URL = https://<your-render-backend>/health`.

## 5. Migrate the database (once)

Already applied during local testing. On a fresh DB:
`cd backend && python -m scripts.apply_migration`.

---

## Security before going public
- Rotate the secrets shared during setup: Supabase DB password, Groq key, Gemini key.
- Never commit `backend/.env` (it's gitignored).
