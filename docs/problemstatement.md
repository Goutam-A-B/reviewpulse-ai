# ReviewPulse AI
## Agentic Product Intelligence from App Store Reviews

**Product Requirements & System Design Document**

---

## 1. Problem Statement

Modern digital products receive hundreds or thousands of reviews across the Google Play Store and Apple App Store every week. These reviews contain valuable customer signals about bugs, onboarding friction, payments, performance, feature requests, and overall satisfaction. The insight is already there. The problem is that it is buried.

Product teams rarely have the time to read feedback at this scale. As review volume grows, the meaningful signals get lost inside large amounts of unstructured text, and teams fall back on intuition or a handful of loud complaints instead of understanding the actual voice of the customer.

This creates five recurring failures:

- **Product managers** cannot quickly see which issues affect the largest number of users, so prioritisation becomes guesswork.
- **Growth teams** cannot isolate the adoption barriers and friction points that block activation.
- **Founders and leadership** lack a single, trustworthy view of customer sentiment and product health.
- **Feedback** is fragmented across thousands of reviews with no structured prioritisation.
- **Emerging issues** often go unnoticed until they have already damaged ratings and retention.

ReviewPulse AI turns raw mobile app reviews into structured, decision-ready product intelligence. Instead of handing the user hundreds of reviews to read, the platform discovers recurring themes, surfaces real customer quotes, tracks sentiment over time, connects related signals, and recommends concrete product improvements.

The goal is simple to state: help product teams move from reading reviews to making decisions, and compress hours of manual analysis into minutes.

---

## 2. Design Philosophy: Where Agency Belongs

This system makes a deliberate distinction that defines its entire architecture, and it is the most important idea in this document.

**Not every step is an agent. Most are tools.** A tool is a deterministic operation with fixed behaviour: scraping reviews, stripping personal data, embedding text, clustering, retrieving quotes, computing statistics. Given the same input it returns the same output, every time. Naming these "agents" would be dishonest and would hide the one part of the system that genuinely reasons.

**An agent is reserved for a real decision a function cannot make.** An agent plans, acts, observes the result, judges whether it is good enough, decides what to do next, and repeats until satisfied. That plan-act-observe-judge-decide loop is the defining property. If the steps are fixed in advance, it is a pipeline. If a judgment determines the next action, it is an agent.

### 2.1 The Capability That Justifies an Agent: Cross-Signal Synthesis

The hard, valuable work in this product is not analysing one theme in isolation. It is connecting signals. The most useful insight is not "withdrawals: 92 complaints, negative." It is "withdrawal complaints spiked in the same window that support became unreachable, and that combination is what drives the churn language." A fixed pipeline analyses each theme alone and cannot produce that link. Connecting evidence across themes is a genuine multi-step reasoning task, and it is the reason this system contains a real agent rather than only tools.

### 2.2 One Agent, Not a Swarm

The mature architecture is not three, five, or seven agents. It is a **single autonomous Analyst Agent** disciplined by a **Critic**, reasoning over a set of honest, well-named tools. Current engineering guidance on agentic systems is consistent on this point: use the simplest architecture that solves the problem, and reach for multi-agent designs only when a single agent with good tools genuinely cannot cope. Multi-agent meshes multiply coordination failures and cost. Adding agents for the appearance of sophistication is the same error as calling a function an agent, only more expensive. Restraint is the senior signal.

Three principles follow and govern every decision below.

**Principle 1 — Correctness over speed of computation.** The system may take time to prepare data in the background. It may never return a fabricated, incomplete, or misleading result. A slower pipeline that is always right beats a fast one that occasionally invents a trend.

**Principle 2 — Evidence, never invention.** Every theme, quote, sentiment label, and recommendation traces back to real reviews. The product shows the denominator behind every claim and reports plainly when evidence is insufficient. A confident wrong answer is the worst possible outcome for a product-decision tool. This principle is not a disclaimer. It is enforced by the Critic (Section 5.2) and guaranteed at the data layer by the Quote Retriever.

**Principle 3 — Spend the premium model like it is scarce, because it is.** Gemini 2.5 Flash on the free tier tolerates only a handful of calls before rate-limiting. The architecture therefore separates cheap reasoning from expensive writing, runs the agent's reasoning loop on a free local model, and reserves the single premium call for final synthesis (Section 6).

---

## 3. The Tools (Deterministic Components)

These are functions. They are named honestly as tools, not agents, because they make no decisions. They are invoked by the Analyst Agent in Section 5.

| Tool | What it does | Why it is a tool, not an agent |
|---|---|---|
| **Review Collector** | Scrapes reviews (text, rating, date, title) from Play Store & App Store | Fixed operation, no judgment |
| **Data Cleaner** | Removes duplicates, spam, irrelevant content; strips PII; standardises text | Deterministic transformation |
| **Embedder** | Generates vector embeddings (BAAI bge-small-en-v1.5, local) | Same text always yields the same vector |
| **Sentiment Classifier** | Labels each review positive / neutral / negative (local model) | Reproducible classification |
| **Theme Clusterer** | Groups review embeddings into recurring topics | Mechanical clustering |
| **Keyword Extractor** | Surfaces trending terms across the corpus | Statistical extraction |
| **Quote Retriever** | Returns verbatim review excerpts from stored text | Pure retrieval, cannot hallucinate |
| **Stats Engine** | Computes counts, sentiment splits, distribution, impact-frequency scores, trend vs prior window | Plain arithmetic |
| **Report Renderer** | Assembles structured output into the final report and dashboard | Templating, no reasoning |

Reproducibility matters here. A local sentiment classifier returns the same label for the same review every time, which an LLM does not. For a tool whose pitch is "trust these numbers to make product decisions," determinism is not optional. The Quote Retriever in particular cannot invent a quote. It returns rows that exist or nothing, which is how Principle 2 is guaranteed at the data layer.

---

## 4. Why Not Just Use One LLM for Everything?

A fair challenge: a large model could technically attempt cleaning, sentiment, theme-finding, and writing all at once. The system deliberately refuses this, for four reasons.

- **Cost and rate limits.** Per-review LLM sentiment would exhaust the free tier on the first app. Local models keep classification free and unlimited.
- **Determinism.** "8 users complained" must mean 8 every time. An LLM gives different answers on re-runs. A classifier does not.
- **Hallucination is fatal here.** Letting the LLM select quotes or invent themes violates Principle 2. Vector search and text retrieval return only what exists.
- **Scale.** Embeddings and clustering handle thousands of reviews. An LLM context window cannot, and summarising-to-fit loses the long tail where emerging issues hide.

The premium model is therefore reserved for the one thing only it does well: turning structured, verified findings into readable language. Knowing when not to use an LLM is the mature signal.

---

## 5. The Agentic Core: Analyst Agent and Critic

The system contains exactly one agent and one discipline that holds it honest. Together they own all genuine reasoning in the product.

### 5.1 The Analyst Agent

**The goal it is given:** produce the strongest evidence-backed product intelligence for a given app, topic, and timeframe.

**What it is handed:** that goal, plus a toolbox (Embedder, vector search, Stats Engine, Theme Clusterer output, Quote Retriever). It is not handed a fixed script. It decides the investigation itself.

**The loop it runs:**

1. **Plan.** Decide what to investigate first given the user's request. For a custom topic such as "payment failures," decide whether existing discovered themes already cover it or a fresh search is needed.
2. **Act.** Call a tool. For example, embed the query and run a timeframe-filtered vector search, or ask the Stats Engine for the trend on a theme.
3. **Observe.** Read what came back. Four reviews, or four hundred? On-topic, or did "payment" return "refunds"? Does this theme co-occur with another in the same time window?
4. **Judge.** Is the evidence sufficient and coherent? Is this a real signal or noise? Does this connect to a signal already gathered (the cross-signal synthesis of Section 2.1)?
5. **Decide.** Broaden the query, narrow it, reformulate it, widen the timeframe, investigate a correlated theme, or stop because the picture is now solid.
6. **Repeat** until the evidence is strong or the agent concludes the signal genuinely is not there.

A function cannot do this. It runs one fixed query and returns whatever it gets. The agent decides what to search, what to connect, and when to stop. That is a true plan-act-observe loop, and it is what justifies the word "agent."

### 5.2 The Critic

Before any claim reaches the user, the Critic checks it against the retrieved evidence. Does this quote actually support this theme? Is this sample large enough to assert a trend? Is this correlation real or coincidental? If a claim fails, it is downgraded to low confidence with its denominator shown, or dropped entirely, or returned as an explicit "not enough signal" state.

The Critic is Principle 2 turned into an active adversary inside the system. A product built to distrust its own output is exactly the rigour a senior reviewer looks for, and it is the difference between a tool you can make decisions on and a dashboard you have to second-guess.

### 5.3 What the Agent Decides vs What the Tools Execute

The separation is strict and is the heart of honest agentic design. The agent never embeds text, clusters, or computes statistics itself. It decides *whether*, *what*, and *when*, and calls a tool to execute. Agents-as-reasoners, functions-as-tools. This is what distinguishes a real agentic system from a buzzword-driven one, and it is the thing you can defend box by box on a whiteboard.

---

## 6. The Model Budget Problem and Its Resolution

This is the most important engineering decision in the project, because it reconciles two things that look mutually exclusive.

### 6.1 The Tension

Genuine agentic loops cost many LLM calls. An autonomous agent that plans, searches, re-searches, and self-critiques could fire ten or fifteen reasoning calls on a single app. The premium budget is roughly one. So "be genuinely agentic" and "stay inside the free tier" appear to contradict each other directly.

### 6.2 The Resolution: Two-Tier Models

The resolution is to separate reasoning from writing and assign each to a different model tier.

**Tier 1 — Free reasoning for the loop.** Almost every step in the agent's loop is a *decision*, not prose: search again, broaden the query, is four reviews enough, does theme A connect to theme B. These decisions run on a **free reasoning tier** — the **Groq free API (Llama 3.x)** in deployment, or a local quantized model in development — behind a model-abstraction layer, with structured scoring logic for the simpler judgments and as a fallback. This tier is free; Groq's free limits are ample for a single report's loop, and a cached decision path keeps repeat usage near zero, so the agent can loop and the Critic can challenge claims as many times as a report needs at zero premium cost. This is the unlock: the agent's autonomy is no longer rationed by the premium budget.

**Tier 2 — One premium call for synthesis.** The single Gemini 2.5 Flash call is spent only at the very end, on the one task the strong model is uniquely good at: taking the verified, agent-approved findings and writing the narrative, the priority rationale, and the recommendations as one structured JSON response. This collapses what would naively be five or six premium calls into one.

| Task | Model Tier | Cost |
|---|---|---|
| Embeddings | Local (BAAI bge-small-en-v1.5) | Free, no limit |
| Sentiment classification | Local classifier | Free, no limit |
| Theme clustering, keyword extraction | Local | Free, no limit |
| Stats, impact-frequency, trend maths | Stats Engine (local) | Free, no limit |
| Quote selection | Quote Retriever (local) | Free, no limit |
| Agent reasoning loop (plan, judge, decide) | Groq free tier (Llama 3.x) | Free |
| Critic (evidence checks) | Groq free tier (Llama 3.x) | Free |
| Final narrative, priority rationale, recommendations | Gemini 2.5 Flash | 1 call per report |

### 6.3 Reproducibility Under Autonomy

Autonomous agents are by nature less reproducible than pipelines, which is in tension with a product whose pitch is "trust these numbers." Three safeguards keep the reasoning real while keeping the output stable:

- **Temperature zero** on the agent's decisions, so the same evidence yields the same judgment.
- **Structured decisions, not free text.** The agent chooses from constrained options (broaden, narrow, reformulate, investigate-correlated, stop) rather than emitting open-ended reasoning, which makes its behaviour predictable and auditable.
- **Cached decision path** per app, topic, and timeframe, so an identical request replays the identical investigation rather than re-reasoning from scratch.

### 6.4 Optional "Deep Analysis" Mode

For users who want a deeper pass, an explicit toggle spends a few additional premium calls on a multi-pass critique and richer synthesis. This turns the cost constraint into a visible product choice, which is itself a mature design decision: the user, not the system, decides when extra budget is worth spending.

### 6.5 Enforced Ceiling and Graceful Degradation

- **Hard ceiling.** A counter caps premium calls per report in code. If the synthesis call fails or rate-limits, the system still returns the full quantitative report (themes, counts, sentiment, distribution, quotes, trends, priority scores) and marks only the written narrative as temporarily unavailable. The user never sees an error screen.
- **Caching.** Identical requests are served from cache and consume zero premium calls, since reviews do not change minute to minute.
- **Swappable model.** A thin model-abstraction layer allows swapping the synthesis model if the free tier is exhausted, without touching the rest of the system.

---

## 7. System Architecture: The Two-Path Model

The system splits into two independent paths. This is what lets the product honour all three principles at once: heavy work is allowed to be slow because it runs in the background, and the user-facing path stays cheap and reproducible because almost all of its work is already done.

**Ingestion Path (background, asynchronous, slow-tolerant).** Triggered when an app is first requested or on a refresh schedule. It runs the tools, Collector, Cleaner, Embedder, Sentiment Classifier, Theme Clusterer, Keyword Extractor, and writes everything to the database and vector store. The user never waits on this path, so it is free to take as long as correctness requires.

**Query Path (user-facing, fast, premium-frugal).** Triggered when a user requests a report. Because reviews are already embedded, classified, and clustered, the Analyst Agent reasons over stored evidence on the free local tier, the Critic validates the claims, the Stats Engine assembles the numbers, and a single premium call writes the narrative.

| Ingestion Path (background tools) | Query Path (agent + critic + one premium call) |
|---|---|
| Scrape reviews from app stores | Orchestration layer checks cache, decides path |
| Clean, de-duplicate, strip PII | Analyst Agent plans and runs its investigation loop |
| Generate embeddings (local) | Agent calls tools: search, stats, retrieval |
| Classify sentiment (local) | Critic validates every claim against evidence |
| Cluster themes, extract keywords (local) | Stats Engine assembles counts, scores, trends |
| Store in DB + Qdrant | ONE premium call writes the narrative |
| Allowed to be slow | Responsive, reproducible, 1 premium call |

A note on orchestration: routing the request (cache hit versus cold app versus scraper failure) is control-flow logic, not a reasoning agent. It is named honestly as an orchestration layer rather than inflated into an "orchestrator agent."

### 7.1 Cold Start Handling (Cache Miss)

The database is a cache that makes repeat searches fast and free. It is not a precondition. Every app produces a result. Only timing differs.

On a **new app**, there is nothing stored, so the orchestration layer triggers the full ingestion pipeline live before answering: scrape, clean, embed, classify, cluster, then the agent reasons and the single premium call writes. The result is then stored, so the next search on that app is instant.

**The premium budget is unaffected by cache misses.** Embedding, sentiment, clustering, and the agent's reasoning loop all run on free local tiers whether it is the first search or the thousandth. The single premium call sits at the end in both cases, so a cold app costs the same one call as a warm one.

What the cold case affects is **wait time and scraper exposure**, not budget. Two measures keep it honest: **stream the report** as each piece finishes (volume and rating first, themes as clustering completes, quotes as retrieved, narrative last), and **bound the cold scrape** to the most recent few hundred reviews, backfilling the rest in the background so the next search is both instant and more complete.

The only case that cannot return a real result is an app with no reviews, or one the scrapers cannot reach at all. That is where the "no signal / data temporarily unavailable" state applies. The product says so plainly rather than inventing themes.

---

## 8. Product Experience

A user enters an app name or store URL and receives a structured intelligence report. No configuration, no manual tagging.

### 8.1 Multi-Timeframe Analysis
Last 2 weeks, last 5 weeks, last 10+ weeks, or a custom date range, so teams see both short-term incidents and long-term trends.

### 8.2 Custom Investigation Areas
Beyond discovered themes, a user can investigate any topic (login issues, onboarding, KYC, payments, crashes, performance, feature requests, subscriptions) or type any free-form query. The Analyst Agent then plans and runs an investigation specifically for that topic, deciding when it has enough evidence and which related signals to connect. It answers questions such as:

- "How many users complained about onboarding during the last five weeks?"
- "What are customers saying about payment failures?"
- "How has sentiment around app performance changed in the past two weeks?"

### 8.3 The Product Intelligence Report
Every analysis produces one concise report:

1. Top discussion themes
2. Theme-wise sentiment analysis
3. Real customer quotes (verbatim only)
4. Emerging trends and cross-signal correlations
5. Theme distribution
6. AI-generated product recommendations
7. Priority areas for product teams
8. A confidence and volume signal on every insight

---

## 9. The Dashboard: Interface and How It Maps to the Architecture

The product surfaces its intelligence through a dashboard organised into clear segments. Each segment binds to either an honest tool or the Analyst Agent, so the interface and the architecture are one thing. The layout below describes structure and behaviour; visual styling and palette are a separate design choice.

### 9.1 Navigation and Filters
A left sidebar separates views: Reviews (corpus overview and KPIs), Analytics, Themes, Weekly Pulse, and Delivery. A platform filter (All / Android / iOS) and a time-range selector (Today / 7 days / 30 days / 8 to 12 weeks / custom) scope which stored reviews are analysed. These are pure query parameters. No agency, just filters that set what the agent reasons over.

### 9.2 KPI Cards
A row of headline metrics: Reviews Analysed, Average Rating, Sentiment Score, and Theme Count, each with its movement versus the prior window. Every figure comes straight from the Stats Engine and is fully deterministic and reproducible. These are tools, not reasoning.

### 9.3 Trending Keywords
A set of clickable terms (for example brokerage, withdrawal, support, fees, crash, login) that highlight related themes when tapped. Produced by the Keyword Extractor through statistical extraction over the corpus. Mechanical, not agentic.

### 9.4 PM Priority Radar
The executive decision panel, organised into three columns: High Impact (fix first), High Frequency (volume drivers), and Monitor (watch closely), each item carrying a score. This is the clearest example of the tool-and-agent split. The impact-times-frequency score is computed by the Stats Engine, a function. The *placement judgment* and the *correlation rationale* beneath each item ("peak-hour crashes correlate with market open, retention risk") are the Analyst Agent's cross-signal reasoning, written by the single premium synthesis call. The Critic ensures each rationale is supported by the underlying reviews before it is shown.

### 9.5 Trend Alert
A banner that surfaces a significant movement, for example a sharp rise in withdrawal complaints week over week. The detection is a statistical trigger from the Stats Engine. The *explanation* of why the spike happened is the agent's root-cause investigation, connecting the spike to other signals in the same window. Detection is a tool. Diagnosis is the agent.

### 9.6 User Voices
A panel of real customer quotes with their ratings and source, each tied to the theme it illustrates. Quotes are returned verbatim by the Quote Retriever, ranked by how well each supports its claim, and validated by the Critic so that the quote genuinely backs the theme above it. This is the data-layer guarantee of Principle 2 made visible to the user.

---

## 10. Key Features

### 10.1 AI Theme Discovery
Groups reviews into the categories users actually discuss (onboarding, payments, performance, UI/UX, KYC, withdrawals, support) using local embeddings and clustering, never consuming the premium budget.

### 10.2 Custom Topic Investigation
The Analyst Agent plans and runs a real investigation for any user query, deciding when it has enough evidence and which related signals to connect.

### 10.3 Cross-Signal Correlation
The agent connects co-occurring signals (for example withdrawal complaints rising alongside support non-response) into a single explanatory insight, which a per-theme pipeline cannot do.

### 10.4 Real Customer Quotes
Only genuine excerpts, pulled directly by the Quote Retriever from stored text. Never paraphrased, summarised, or generated. A hard guarantee enforced by the Critic.

### 10.5 Confidence and Volume Signals
Every insight shows its denominator and a confidence level (high / medium / low) set by the Critic. "8 of 30 reviews" and "8 of 3,000" are presented very differently. This is the line between a dashboard and a decision tool.

### 10.6 Trend and Anomaly Detection
Increasing complaints, improving sentiment, emerging issues, and growing feature demand, computed statistically and explained by the agent.

### 10.7 Honest "No Signal" State
When evidence is insufficient, the Critic refuses to manufacture a theme and the product says so plainly. Not inventing a trend is treated as a feature.

### 10.8 Product Health Dashboard
The segmented interface of Section 9, giving leadership a single glance at product health and a prioritised view of what to fix.

---

## 11. Technology Stack

| Layer | Choice | Notes |
|---|---|---|
| Frontend | Next.js, TypeScript, Tailwind, ShadCN UI | Segmented dashboard, streams sections progressively |
| Backend | FastAPI | Hosts both ingestion and query paths |
| Agent framework | LangGraph | Implements the plan-act-observe-critique loop as a real graph with cycles |
| Reasoning model (agent + Critic) | Groq free tier — Llama 3.x (local model in dev) | Free; powers the loop and Critic behind the model-abstraction layer |
| Database | PostgreSQL (Supabase free tier) | Stores reviews, sentiment, themes, decision paths |
| Vector store | Qdrant (open source / free tier) | Payload-filtered search by date and rating |
| Embeddings | BAAI bge-small-en-v1.5 via fastembed (ONNX) | Local, free, high-quality retrieval; fits free-host RAM (no PyTorch) |
| Synthesis LLM | Gemini 2.5 Flash | Free tier, one call per report |
| Scraping | Google Play & App Store scrapers | Unofficial, needs retries and caching |
| Monitoring | LangSmith free tier | Traces agent reasoning, loop depth, and call counts |

### 11.1 Deployment and Reliability Notes

- **Hosting.** Frontend on Vercel free (Hobby), backend on Render free web tier (Railway's free tier has ended), vector store on Qdrant Cloud free tier, database on Supabase free tier. No paid tiers, no credit card.
- **Reasoning model hosting.** A free host (~512MB) cannot load a 3–8B model, so the deployed reasoning loop runs on the **Groq free API**; a local model (Ollama) is used in development. Where even that is unnecessary, structured scoring logic handles the judgment. The model-abstraction layer makes this swap a config change, not an architecture change.
- **Cold starts.** The Render free tier spins down when idle and takes 30 to 50 seconds to wake. A free external cron pinging the health endpoint keeps it warm and prevents a cold first impression. Since the product tolerates slow background work, this matters only for the first request after idle.
- **Scraper fragility.** The app-store scrapers are unofficial and can break or rate-limit when stores change markup. This is the largest reliability risk, mitigated by aggressive caching, retries with backoff, and a graceful "data temporarily unavailable" state.
- **Query filtering.** Vector searches filter by date and rating inside Qdrant using indexed payload fields, never by post-filtering in Python, so timeframe filtering stays fast even on large review sets.

---

## 12. Why This Is a Strong, Senior-Level Project

This project demonstrates the judgment senior product managers look for, specifically:

- **It uses the minimum sophistication the problem requires.** One genuine agent appears where genuine cross-signal reasoning lives. Everything else is an honestly-named tool. Restraint, not buzzwords.
- **It solves the hardest constraint cleanly.** Genuine agentic autonomy under a near-zero premium budget is reconciled by the two-tier model strategy: free local reasoning for the loop, one premium call for synthesis. This is a current, real problem in applied agentic AI, and the solution is defensible.
- **It can be defended line by line.** The agent maps to a real plan-act-observe-critique loop, every tool to a deterministic function, and every dashboard panel to one or the other. No component is unexplainable.
- **It encodes a product value into the architecture.** Principle 2 ("evidence, never invention") is enforced by the Critic and guaranteed by the Quote Retriever. The product knows when to stay silent.
- **It respects reproducibility and failure.** Temperature-zero structured decisions, cached decision paths, a hard premium ceiling, and graceful degradation under scraper and rate-limit failure are designed in, not patched on.

---

## 13. Expected Impact

ReviewPulse AI compresses hours of manual review analysis into minutes by transforming large volumes of app-store feedback into structured product intelligence. It tells a product team what customers are talking about, how they feel, which issues are emerging, how those issues connect, and what to fix next, grounded in real user feedback rather than assumptions.

It does this with a single genuine Analyst Agent reasoning over honest tools, a Critic that enforces evidence, a two-tier model strategy that keeps every report inside one premium call, and a segmented dashboard where every figure traces back to real, verified reviews carrying its own confidence. The result is a tool a product manager can actually make decisions on, and a system whose every design choice can be defended, which is precisely what distinguishes senior-level work.
