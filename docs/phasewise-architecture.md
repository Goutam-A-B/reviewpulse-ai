# ReviewPulse AI — Phase-Wise Architecture

**Companion to:** [problemstatement.md](problemstatement.md)
**Purpose:** Translate the ReviewPulse AI system design into a dependency-ordered build roadmap. Each phase is a self-contained slice that compiles, runs, and demonstrates a real capability, while honouring the three principles and the two-tier model budget defined in the PRD.

> This document does not re-argue *why* the architecture is shaped this way — the PRD does that. It defines *in what order it gets built*, what each phase owns, and how you know a phase is done.

---

## 0. How To Read This Document

- **Phases are dependency-ordered, not calendar-ordered.** A phase begins only when its predecessors' exit criteria are met. Durations are deliberately omitted; the gates are what matter.
- **Every phase ends with a demonstrable milestone** — something you can show on a screen or a CLI, not just "code merged."
- **The agent/tool split from the PRD is preserved at the phase level too.** Tool phases (1–3) are deterministic and testable with fixtures. The agent phase (4) is where reasoning enters. They are built in that order on purpose: the agent is only as trustworthy as the tools it reasons over.
- **Premium-cost discipline is tracked per phase.** Most phases consume zero premium calls. Only Phase 5 introduces the single Gemini 2.5 Flash call.

---

## 1. Architectural North Star (recap)

The build never violates these, regardless of phase:

| Principle (PRD §2.2) | Build-time consequence |
|---|---|
| **Correctness over speed** | The ingestion path may be slow; it is built and tested for correctness first, optimised later. |
| **Evidence, never invention** | The Quote Retriever (Phase 3) and Critic (Phase 4) are non-negotiable gates, not stretch goals. |
| **Spend the premium model like it is scarce** | The single Gemini call (Phase 5) is the *last* reasoning capability added, never the first reflex. |

**Two structural commitments that shape every phase:**

- **Two-Path Model (PRD §7).** *Ingestion* (background, slow-tolerant, free/local) is built before *Query* (user-facing, fast, one premium call). You cannot reason over evidence that hasn't been ingested.
- **Two-Tier Model Budget (PRD §6).** A free reasoning tier (Groq free API in deployment, local model in dev) + deterministic tools do all the looping; Gemini 2.5 Flash (free tier) writes the final narrative exactly once per report.

---

## 2. Canonical Component Map

Every component the system will ever contain, tagged by the layer it lives in and the phase that introduces it. Nothing outside this table gets built without amending it.

| Component | Layer | Kind | Premium cost | Introduced in |
|---|---|---|---|---|
| Repo / monorepo scaffold, config, model-abstraction layer | Foundation | Infra | none | Phase 0 |
| DB schema (PostgreSQL/Supabase) + Qdrant collections | Foundation | Infra | none | Phase 0 |
| Review Collector (scrapers) | Ingestion | Tool | none | Phase 1 |
| Data Cleaner (dedup, spam, PII strip, normalise) | Ingestion | Tool | none | Phase 1 |
| Embedder (BAAI bge-small-en-v1.5) | Ingestion | Tool | none | Phase 2 |
| Sentiment Classifier (local) | Ingestion | Tool | none | Phase 2 |
| Theme Clusterer | Ingestion | Tool | none | Phase 2 |
| Keyword Extractor | Ingestion | Tool | none | Phase 2 |
| Quote Retriever (payload-filtered vector search) | Query | Tool | none | Phase 3 |
| Stats Engine (counts, splits, impact×frequency, trend) | Query | Tool | none | Phase 3 |
| Analyst Agent (LangGraph plan-act-observe-judge-decide) | Query | **Agent** | none (Groq free) | Phase 4 |
| Critic (evidence validation) | Query | **Agent discipline** | none (Groq free) | Phase 4 |
| Decision-path cache | Query | Infra | none | Phase 4 |
| Synthesis call (Gemini 2.5 Flash) | Query | LLM | **1 / report** | Phase 5 |
| Orchestration layer (cache/cold-start/route) | Query | Control-flow | none | Phase 5 |
| Premium ceiling + graceful degradation | Query | Control-flow | none | Phase 5 |
| Report Renderer | Query | Tool | none | Phase 5 |
| Dashboard (Next.js segmented UI, streaming) | Frontend | UI | none | Phase 6 |
| LangSmith tracing, deploy, keep-warm, Deep Analysis | Cross-cutting | Ops | optional premium | Phase 7 |

---

## 3. High-Level Architecture (target state)

```
                        ┌───────────────────────────────────────────────┐
                        │                  FRONTEND                       │
                        │   Next.js · TS · Tailwind · ShadCN (Phase 6)    │
                        │   Segmented dashboard, progressive streaming    │
                        └───────────────────────┬───────────────────────┘
                                                 │ HTTP (report request)
                        ┌────────────────────────▼───────────────────────┐
                        │             ORCHESTRATION LAYER (Phase 5)        │
                        │   cache hit? · cold app? · scraper failure?      │
                        │   control-flow only — NOT an agent               │
                        └───────┬───────────────────────────────┬─────────┘
                  cache miss /  │                                │  cache hit / warm
                  cold start    │                                │
        ┌─────────────────────▼─────────────┐      ┌────────────▼──────────────────────┐
        │   INGESTION PATH (background)      │      │   QUERY PATH (user-facing)         │
        │   slow-tolerant · free/local       │      │   fast · ≤1 premium call           │
        │                                    │      │                                    │
        │  Review Collector   (P1)           │      │  Analyst Agent  (P4) ── Groq free  │
        │  Data Cleaner       (P1)           │      │     plan→act→observe→judge→decide  │
        │  Embedder           (P2)           │      │        │ calls tools               │
        │  Sentiment Classifier (P2)         │      │        ▼                           │
        │  Theme Clusterer    (P2)           │      │  Quote Retriever (P3) ─┐           │
        │  Keyword Extractor  (P2)           │      │  Stats Engine    (P3) ─┤ evidence  │
        │                                    │      │        │               │           │
        └───────────────┬────────────────────┘      │  Critic (P4) ◄─────────┘ validates │
                        │ writes                     │        │                           │
                        ▼                            │        ▼  approved findings        │
        ┌───────────────────────────────────┐       │  Gemini 2.5 Flash (P5) ── 1 call   │
        │  PostgreSQL (Supabase)  +  Qdrant  │◄──────┤  Report Renderer (P5)              │
        │  reviews · sentiment · themes ·    │ reads └────────────────────────────────────┘
        │  keywords · decision paths · cache │
        │  vectors (payload: date, rating)   │      Observability: LangSmith (P7)
        └───────────────────────────────────┘
```

---

## 4. Phase Overview

| Phase | Name | One-line outcome | Premium calls | Gate to next |
|---|---|---|---|---|
| **0** | Foundation & Scaffolding | Repo, infra, schema, model abstraction exist and connect | 0 | Health check green end-to-end |
| **1** | Ingestion I — Acquisition | Raw, cleaned, PII-free reviews land in Postgres | 0 | A real app's reviews stored & queryable |
| **2** | Ingestion II — Enrichment | Reviews embedded, classified, clustered, keyworded | 0 | Vectors in Qdrant; themes/sentiment in DB |
| **3** | Query Tools — Evidence Layer | Deterministic retrieval + stats over stored evidence | 0 | Verbatim quotes + correct numbers via API |
| **4** | Agentic Core | Analyst Agent + Critic reason over tools (local) | 0 | Agent investigates a topic, Critic gates claims |
| **5** | Synthesis & Orchestration | One premium call writes the report; routing + ceiling | **1 / report** | Full report JSON from a single request |
| **6** | Dashboard | Segmented UI, every panel bound to tool or agent | 0 | End-user gets a streamed, sourced report |
| **7** | Hardening & Operations | Tracing, deploy, resilience, Deep Analysis mode | optional | Live, observable, degrades gracefully |

**Dependency graph:**

```
P0 ──► P1 ──► P2 ──► P3 ──► P4 ──► P5 ──► P6
                       └──────────────► P6 (UI can stub agent/synthesis early)
P5 ──► P7   P6 ──► P7
```

P6 (Dashboard) can begin against P3/P5 stubbed contracts in parallel once API shapes are frozen, but it is *not done* until it renders real P5 output.

---

## 5. Phase Details

### Phase 0 — Foundation & Scaffolding

**Goal.** Stand up the skeleton so every later phase has a place to live and a way to run. No product logic yet.

**Scope.**
- Monorepo layout: `backend/` (FastAPI), `frontend/` (Next.js), `shared/` (types/contracts), `infra/`, `docs/`.
- Provision free-tier infra: Supabase (Postgres), Qdrant Cloud, Vercel (frontend), Render free web tier (backend). See Appendix C — no paid tiers anywhere.
- **Database schema v1** (see Appendix A) and **Qdrant collections** with payload indexes on `date` and `rating`.
- **Model-abstraction layer** — a thin interface (`reason()`→Groq free, `synthesize()`→Gemini free, `embed()`→fastembed) so every model sits behind a swappable adapter (PRD §6.5). This is built *now* so no later phase hard-codes a vendor.
- Config & secrets management; `.env` contracts; health-check endpoint that pings DB + Qdrant + model adapters.

**Key decisions.**
- Contracts-first: shared request/response schemas defined before either side implements them.
- The model-abstraction layer ships before any model is actually called, so swapping Gemini later touches one file.

**Tech.** FastAPI, Next.js + TS, Supabase, Qdrant, Pydantic models for contracts.

**Exit criteria.** `GET /health` returns green for DB, vector store, and both model adapters (adapters may be stubs). Frontend renders an empty shell that calls `/health`.

**Risks.** Free-tier cold starts (deferred to P7); credential sprawl — mitigate with a single typed settings module.

---

### Phase 1 — Ingestion I: Acquisition (Collector + Cleaner)

**Goal.** Get real reviews into Postgres, clean and PII-free. This is the foundation of "evidence, never invention" — there is no evidence without this.

**Scope.**
- **Review Collector** — Google Play & App Store scrapers capturing `text, rating, date, title, platform, source_id`. Retries with backoff; raw payloads stored before transformation.
- **Data Cleaner** — dedup, spam/irrelevant filtering, **PII stripping**, text normalisation. Deterministic: same input → same output.
- Ingestion job runner (async/background) writing to `reviews`.

**Key decisions.**
- Store raw + cleaned separately so cleaning is auditable and re-runnable.
- PII stripping happens before anything is embedded or surfaced — it cannot be retrofitted after vectors exist.
- Bound the cold scrape to the most recent few hundred reviews, backfill rest in background (PRD §7.1).

**Tech.** Play/App Store scraper libs, FastAPI background tasks, Postgres.

**Exit criteria.** For a chosen real app, running ingestion populates `reviews` with cleaned, de-duplicated, PII-free rows; a re-run produces identical cleaned output (determinism check passes).

**Risks.** Scraper fragility / markup changes (largest reliability risk per PRD §11.1) — mitigate with retries, caching of raw payloads, and the "data temporarily unavailable" state stub.

---

### Phase 2 — Ingestion II: Enrichment (Embed · Classify · Cluster · Keywords)

**Goal.** Turn cleaned text into the structured, searchable evidence the agent will reason over. Completes the ingestion path. **Entirely local and free.**

**Scope.**
- **Embedder** — BAAI bge-small-en-v1.5 served via **`fastembed`** (ONNX, no PyTorch) so it fits free-host RAM; write vectors to Qdrant with `{date, rating, platform, review_id}` payload.
- **Sentiment Classifier** — local model, labels positive/neutral/negative; reproducible (same review → same label, always).
- **Theme Clusterer** — cluster embeddings into recurring topics; persist theme assignments + theme metadata.
- **Keyword Extractor** — statistical trending-term extraction across the corpus.

**Key decisions.**
- Determinism is contractually tested: re-running enrichment on the same corpus yields identical labels, clusters, and vectors. This is what lets "8 users complained" mean 8 every time (PRD §4).
- Everything writes to DB/Qdrant; nothing is computed on the user's request path.

**Tech.** `bge-small-en-v1.5` via `fastembed` (ONNX, local), a lightweight/ONNX sentiment classifier, clustering (e.g. HDBSCAN/k-means over embeddings), keyword stats, Qdrant upserts.

**Exit criteria.** After ingestion of a real app: Qdrant returns nearest-neighbour reviews for a query vector with correct date/rating payloads; `themes`, `sentiment`, and `keywords` tables populated; full determinism re-run check passes.

**Risks.** Clustering quality on small corpora — surfaced honestly via volume signals later, not hidden. Local model footprint on free tier — quantize or swap to scoring logic (PRD §11.1).

---

### Phase 3 — Query Tools: The Evidence Layer (Quote Retriever + Stats Engine)

**Goal.** Build the deterministic tools the agent will *call*. No reasoning yet — these are pure functions, testable with fixtures, and they are the data-layer guarantee of Principle 2.

**Scope.**
- **Quote Retriever** — payload-filtered vector search returning **verbatim** review excerpts (text, rating, source). Filtering by date/rating happens *inside Qdrant* via indexed payload fields, never post-filtered in Python (PRD §11.1). Returns rows that exist or nothing — cannot hallucinate.
- **Stats Engine** — counts, sentiment splits, theme distribution, **impact×frequency** scores, **trend vs prior window**. Plain arithmetic, fully reproducible.
- Tool-call contracts (typed inputs/outputs) that the agent in Phase 4 will bind to.

**Key decisions.**
- These tools are exposed behind a stable internal tool interface so Phase 4's agent calls them without knowing implementation details.
- Quote ranking (how well a quote supports a claim) is computed here as a deterministic score; the *judgment* of sufficiency stays with the Critic.

**Tech.** Qdrant filtered search, Postgres aggregate queries, Pydantic tool schemas.

**Exit criteria.** Via API/CLI: a timeframe-filtered query returns only verbatim quotes within that window; Stats Engine reproduces identical counts/splits/trends across runs; impact×frequency scores computed for every theme.

**Risks.** Slow filtering on large sets — mitigated by indexed payloads (designed in P0). Quote relevance vs recency trade-off — handled by ranking, validated by Critic in P4.

---

### Phase 4 — The Agentic Core (Analyst Agent + Critic)

**Goal.** Introduce the system's *one genuine agent* and the discipline that holds it honest. Runs entirely on the **free local reasoning model** — no premium calls.

**Scope.**
- **Analyst Agent** as a **LangGraph graph with real cycles**, running the loop (PRD §5.1):
  `Plan → Act (call a tool) → Observe → Judge → Decide → Repeat / Stop`.
- **Structured decisions only** — the agent chooses from a constrained action set: `{broaden, narrow, reformulate, investigate-correlated, stop}` (PRD §6.3). No open-ended free text drives control flow.
- **Cross-signal synthesis** — the agent can decide to investigate a *correlated* theme (the capability that justifies an agent, PRD §2.1).
- **Critic** — before any claim is eligible for the report, validates: does this quote support this theme? Is the sample large enough? Is this correlation real? Failing claims are downgraded (low confidence + denominator), dropped, or returned as explicit "not enough signal."
- **Decision-path cache** keyed by `(app, topic, timeframe)` so identical requests replay the identical investigation (PRD §6.3).
- **Temperature zero** on all agent/critic decisions.

**Key decisions.**
- The agent **never** embeds, clusters, or computes stats itself — it decides *whether/what/when* and calls a Phase-3 tool (PRD §5.3). This separation is enforced in code, not by convention.
- The agent's output at end of this phase is **verified, structured findings** — not prose. Prose is Phase 5's job.

**Tech.** LangGraph; **Groq free tier (Llama 3.x) as the deployed reasoning model** behind the P0 model-abstraction layer (locked 2026-06-16); **structured scoring logic** for the frequent cheap judgments and as the fallback if Groq rate-limits or is down (EC-P4-11). A local Ollama model may be used in dev only.

**Exit criteria.** Given a topic (e.g. "payment failures") and timeframe, the agent autonomously loops over tools, the Critic gates each claim, and the system emits structured findings with denominators and confidence — with **zero premium calls**. Same request replays from decision-path cache.

**Risks.** Reproducibility under autonomy — mitigated by temperature zero + structured decisions + decision-path cache. Local model capability limits — fall back to structured scoring for the simpler judgments.

---

### Phase 5 — Synthesis & Orchestration (the single premium call)

**Goal.** Spend the one premium call, and wire the control-flow that routes every request correctly. This completes the Query Path.

**Scope.**
- **Synthesis call** — exactly one Gemini 2.5 Flash call takes the agent-approved findings and writes the narrative, priority rationale, and recommendations as **one structured JSON response** (PRD §6.2). Collapses what would be 5–6 naive premium calls into one.
- **Orchestration layer** — control-flow that, per request, checks cache → decides path: cache hit (free), warm app (query path), cold app (trigger live ingestion then query), scraper failure (degrade). Explicitly **not** an agent (PRD §7).
- **Premium ceiling** — a hard, in-code counter caps premium calls per report. If synthesis fails/rate-limits, the **full quantitative report still returns** (themes, counts, sentiment, distribution, quotes, trends, priority scores); only the narrative is marked temporarily unavailable. No error screen (PRD §6.5).
- **Report Renderer** — assembles verified findings + narrative into the final report structure (PRD §8.3 — eight sections).
- **Caching** of identical requests at zero premium cost.

**Key decisions.**
- The premium call is the *last* thing in the pipeline and the *first* thing to be made optional under failure.
- Cold start costs the **same one premium call** as a warm app — only wait time differs (PRD §7.1).

**Tech.** Gemini 2.5 Flash via the P0 model-abstraction layer, FastAPI orchestration, structured JSON schema for synthesis output.

**Exit criteria.** A single API request for a warm app returns a complete report JSON (all 8 sections) using exactly **one** premium call; a forced synthesis failure still returns the full quantitative report with narrative flagged unavailable; a cold app self-ingests then reports.

**Risks.** Rate limits / free-tier exhaustion — ceiling + caching + swappable synthesis model (P0 abstraction) absorb this.

---

### Phase 6 — The Dashboard

**Goal.** Surface the intelligence through the segmented interface where **every panel binds to an honest tool or the agent** (PRD §9), and the report streams progressively.

**Scope (panel → source binding).**
- **Navigation & filters** (platform All/Android/iOS; time-range) — pure query params, no agency.
- **KPI cards** (Reviews Analysed, Avg Rating, Sentiment Score, Theme Count + deltas) — Stats Engine, deterministic.
- **Trending keywords** (clickable) — Keyword Extractor.
- **PM Priority Radar** (High Impact / High Frequency / Monitor) — score from Stats Engine; *placement + correlation rationale* from the Analyst Agent via the synthesis call; Critic-validated.
- **Trend Alert** — detection from Stats Engine (tool); *explanation* from the agent (diagnosis).
- **User Voices** — verbatim quotes from Quote Retriever, Critic-validated to back their theme.
- **Progressive streaming** — volume & rating first, themes as clustering completes, quotes as retrieved, narrative last (PRD §7.1).
- **Confidence & volume signals** on every insight ("8 of 30" vs "8 of 3,000").
- **Honest "No Signal" state** rendered plainly when the Critic refuses to manufacture a theme.

**Key decisions.**
- The UI never computes intelligence; it renders what the backend already verified. Each component is traceable to its source box on the architecture diagram.

**Tech.** Next.js, TypeScript, Tailwind, ShadCN UI, streaming responses.

**Exit criteria.** A user enters an app name/URL and receives a streamed, segmented report; every figure traces to Stats Engine, every quote is verbatim from Quote Retriever, every rationale carries Critic-validated confidence; "No Signal" renders correctly for an app with insufficient evidence.

**Risks.** Streaming complexity — sequence sections by readiness; degrade to non-streamed if needed.

---

### Phase 7 — Hardening & Operations

**Goal.** Make it observable, resilient, deployable, and optionally deeper.

**Scope.**
- **LangSmith tracing** — agent reasoning, loop depth, tool-call counts, premium-call counts.
- **Deployment** — frontend on Vercel (Hobby), backend on Render (free web tier), Qdrant Cloud (free), Supabase (free). All free tiers; see Appendix C.
- **Keep-warm** via a free external cron (GitHub Actions / cron-job.org) pinging `/health` to avoid the 30–50s cold-start first impression. No paid always-on instance (PRD §11.1).
- **Scraper resilience** — backoff, aggressive caching, graceful "data temporarily unavailable."
- **Deep Analysis mode** — explicit user toggle that spends a few additional premium calls on multi-pass critique and richer synthesis (PRD §6.4). The user, not the system, chooses to spend extra budget.
- **Backfill scheduling** — complete the long tail of reviews bounded at cold start.

**Key decisions.**
- Observability proves the budget claim: traces show premium-call count ≤ 1 (or the Deep Analysis ceiling) per report.
- Deep Analysis turns a cost constraint into a visible product choice — never an automatic spend.

**Tech.** LangSmith (free tier), Vercel + Render (free tiers), free external cron for keep-warm pings.

**Exit criteria.** Live deployment serves real reports; LangSmith confirms ≤1 premium call on standard reports; killing the scraper yields the graceful state, not an error; Deep Analysis visibly increases depth and (bounded) spend only when toggled.

**Risks.** Free-tier limits across services — caching, ceilings, and keep-warm keep it inside the envelope.

---

## 6. Cross-Cutting Concerns (apply to every phase)

| Concern | Standing rule |
|---|---|
| **PII / privacy** | Stripped at ingestion (P1) *before* embedding or storage of surfaced text. Never retrofitted. |
| **Determinism** | Tools (P1–P3) produce identical output on identical input — contractually tested. Agent (P4) is made reproducible via temperature 0 + structured decisions + decision-path cache. |
| **Evidence guarantee** | Quote Retriever returns only stored rows; Critic gates every claim. No phase introduces a path that can fabricate a quote or theme. |
| **Premium budget** | Tracked per phase in §2's table. Hard in-code ceiling lives in P5. Only P5 (and optional P7 Deep Analysis) spend premium. |
| **Graceful degradation** | From P5 onward, any premium/scraper failure returns the quantitative report or an honest "unavailable," never an error screen. |
| **Swappability** | The P0 model-abstraction layer is the single seam for replacing the synthesis or local model. No phase hard-codes a vendor elsewhere. |
| **Observability** | Instrumented for real in P7, but tool/agent boundaries are logged from P4 so traces are meaningful when LangSmith attaches. |

---

## 7. Appendix A — Data Model Sketch (v1, established Phase 0)

```
apps(id, name, store_app_id, store_url, platform, first_ingested_at, last_refreshed_at)
     -- unique(platform, store_app_id) for idempotent app upsert

reviews(id, app_id → apps, platform, source_review_id, title, text_raw,
        text_clean, rating, review_date, ingested_at, is_spam, is_duplicate)

sentiment(review_id → reviews, label{pos|neu|neg}, model_version)

themes(id, app_id → apps, label, description, size, model_version)
review_themes(review_id → reviews, theme_id → themes, distance)

keywords(id, app_id → apps, term, frequency, window_start, window_end)

decision_paths(id, app_id, topic, timeframe_hash, graph_trace_json,
               findings_json, created_at)   -- the agent replay cache (P4)

reports(id, app_id, topic, timeframe, report_json, narrative_status,
        premium_calls_used, created_at)      -- query-path cache (P5)
```

**Qdrant collection `review_vectors`:** vector = bge-small-en-v1.5 embedding; payload = `{review_id, app_id, review_date, rating, platform, theme_id}` with **indexed** `review_date` and `rating` for in-store filtering.

---

## 8. Appendix B — Per-Phase Premium-Call Ledger

| Phase | Premium calls introduced | Cumulative capability without premium |
|---|---|---|
| 0–4 | **0** | Full ingestion, retrieval, stats, autonomous agent reasoning, Critic validation — all free/local |
| 5 | **1 / report** | Adds the written narrative; quantitative report already complete without it |
| 6 | 0 | Renders P5 output |
| 7 | optional (Deep Analysis, user-toggled, bounded) | Adds depth only when the user chooses to spend |

This ledger is the architecture's central claim made checkable: **everything that reasons is free; only the writing costs.**

---

## 9. Build Sequencing Summary

1. **P0** — skeleton, schema, model seam.
2. **P1 → P2** — ingestion path end-to-end (acquire, then enrich). *Now there is evidence.*
3. **P3** — deterministic query tools over that evidence. *Now there are honest numbers and verbatim quotes.*
4. **P4** — the one agent + Critic, reasoning over P3 tools on the free local tier. *Now there is judgment, still free.*
5. **P5** — one premium call + orchestration + ceiling. *Now there is a complete, frugal report.*
6. **P6** — dashboard binds each panel to its tool or the agent. *Now a PM can use it.*
7. **P7** — observability, deploy, resilience, optional Deep Analysis. *Now it is live and defensible.*

Each arrow is a hard gate: do not start the next phase until the prior phase's exit criteria pass.

---

## 10. Appendix C — Free-Tier / No-Subscription Compliance (binding)

**Hard constraint:** the entire system runs on **free tiers and open-source software only**. No paid subscriptions, no paid API keys, no credit-card-required services. This appendix is binding and supersedes any host name mentioned earlier.

| Component | Free choice | Card / subscription? | Free-tier ceiling | Notes |
|---|---|---|---|---|
| Frontend host | Vercel **Hobby** | No | Generous | Hobby is non-commercial — fine for a portfolio/demo. |
| Backend host | **Render** free web service | No | Spins down when idle (30–50s cold start) | **Not Railway** — its free tier ended (now trial-then-paid). HF Spaces or Fly.io are free fallbacks. |
| Database | **Supabase** free / Postgres | No | 500MB, pauses after ~1wk idle | Neon free is an alternative. |
| Vector store | **Qdrant Cloud** free | No | 1GB cluster | Or self-host the open-source image locally. |
| Embeddings | **bge-small-en-v1.5** (local, open weights) | No | Unlimited (your CPU) | ~130MB, 384-dim, runs on CPU. |
| Sentiment / clustering / keywords / stats | Local open-source libs | No | Unlimited | scikit-learn / HDBSCAN / a small local classifier. |
| Synthesis LLM | **Gemini 2.5 Flash — free tier** (Google AI Studio key) | No (free API key) | Rate-limited per minute/day | 1 call/report + caching keeps us far inside the daily cap. |
| Agent reasoning loop | **Groq free tier (Llama 3.x)** + structured-scoring fallback | No (free API key) | Per-minute / per-day rate limits | Locked 2026-06-16. Plenty for single reports; cache decision paths. |
| Monitoring | **LangSmith** free Developer tier | No | ~5k traces/mo | Optional; failure never blocks a report (EC-P7-01). |
| Scrapers | `google-play-scraper`, `app-store-scraper` (OSS) | No | Unlimited (subject to store throttling) | Free libraries, not paid APIs. |

### The one real gotcha: where the reasoning model runs

The PRD's budget argument rests on "local reasoning = free **and unlimited**," which justifies unlimited agent/Critic loops. The catch: **free cloud hosts (~512MB RAM) cannot run a 3–8B model.** So "free" and "deployed in the cloud" pull against each other for the *reasoning tier only*. Three free resolutions, all zero-cost:

1. **Structured scoring logic (no LLM) for most judgments** — the PRD's own sanctioned fallback (§6.2, §11.1). Deterministic, deployable anywhere, truly unlimited. Default for the frequent/cheap decisions (is 4 reviews enough, broaden vs. narrow).
2. **Local model via Ollama for the genuinely hard reasoning** — runs free and unlimited on your own Windows machine during dev; not hostable on a free cloud tier, so it's a dev/demo-time tier.
3. **Free hosted inference tier (Groq / Gemini free) for hard reasoning when deployed** — free API key, deployable, but rate-limited, so it slightly dents the "unlimited loop" ideal; mitigated by caching the decision path.

**Decision (locked 2026-06-16):** the deployed reasoning loop runs on the **Groq free tier (Llama 3.x)** — a real LLM, so the agent loop stays genuinely agentic and defensible — with **structured scoring logic** handling the frequent cheap judgments and serving as the fallback if Groq rate-limits or is unavailable (EC-P4-11). A local Ollama model is dev-only. The single synthesis call stays on the Gemini free tier throughout. Net cost remains $0.

### Other free-tier consequences

- **Keep-warm without paying.** The PRD mentions a "small always-on instance" — that is the *paid* option and we do **not** use it. Use a **free external cron** (GitHub Actions / cron-job.org) to ping `/health` and keep Render warm.
- **No credit card anywhere.** Every service above offers its free tier without a card. If any provider later demands one, swap via the noted free fallback rather than entering billing.
- **Budget claim still holds end-to-end:** everything that *reasons* is free (local/structured/free-tier); only the single synthesis call touches an LLM, on its free tier. Cost stays literally $0.
