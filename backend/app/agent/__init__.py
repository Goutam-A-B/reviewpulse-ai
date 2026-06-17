"""Phase 4 — The Agentic Core: one Analyst Agent + a Critic that holds it honest.

The agent runs a real plan-act-observe-judge-decide loop over the Phase 3 tools on
the free reasoning tier (Groq, with deterministic structured-scoring fallback). It
never embeds/clusters/computes itself — it decides whether/what/when and calls a
tool. Output is verified, structured findings (prose is Phase 5). Zero premium budget.

Shared thresholds live here so the reasoner and Critic never drift.
"""

MIN_SUPPORT = 3  # below this, evidence is insufficient to assert anything
SUFFICIENT_SUPPORT = 8  # at/above this, the agent may stop confident
HIGH_CONFIDENCE_RATIO = 0.05  # support/denominator for 'high'
MED_CONFIDENCE_RATIO = 0.02  # support/denominator for 'medium'
MIN_CORRELATION_OVERLAP = 3  # co-occurring reviews needed to assert a correlation
MAX_ITERATIONS = 6  # hard ceiling on the loop (EC-P4-01)
