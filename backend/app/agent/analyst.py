"""The Analyst Agent loop — plan, act, observe, judge, decide, repeat (PRD §5.1).

The agent never touches data directly: it ACTs by calling the Quote Retriever
tool, OBSERVEs the result, the Critic JUDGEs whether it is assertable, and the
reasoner DECIDEs the next constrained action. Guards keep it honest and bounded:
a hard iteration ceiling (EC-P4-01), cycle detection (EC-P4-02), and an explicit
no-signal outcome when evidence never materialises (EC-P4-08). Output is verified,
structured findings — never prose, never premium budget (Phase 5 writes the words).
"""
from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from datetime import datetime

from app.agent import MAX_ITERATIONS
from app.agent.cache import DecisionPathCache
from app.agent.critic import Critic, Finding
from app.agent.decisions import Action
from app.agent.reasoner import Reasoner, StructuredReasoner
from app.query import quotes as quotes_tool


@dataclass
class AnalysisResult:
    status: str  # ok | no_signal | cached
    topic: str
    findings: list[dict]
    iterations: int
    decisions: list[dict]
    note: str = ""
    premium_calls: int = 0  # always 0 in Phase 4 — reasoning is free


def _dedup_findings(findings: list[Finding]) -> list[Finding]:
    best: dict[str, Finding] = {}
    for f in findings:
        cur = best.get(f.claim)
        if cur is None or f.support > cur.support:
            best[f.claim] = f
    out = list(best.values())
    out.sort(key=lambda f: (-f.support, f.claim))
    return out


async def run_analysis(
    *,
    app_id: str,
    topic: str,
    embedder,
    vector_store,
    reasoner: Reasoner | None = None,
    critic: Critic | None = None,
    cache: DecisionPathCache | None = None,
    data_version: str = "v0",
    start: datetime | None = None,
    end: datetime | None = None,
) -> AnalysisResult:
    reasoner = reasoner or StructuredReasoner()
    critic = critic or Critic()

    cache_key = None
    if cache is not None:
        cache_key = cache.key(app_id, topic, start, end, data_version)
        hit = cache.get(cache_key)
        if hit is not None:
            return AnalysisResult(status="cached", **hit)

    query = topic
    rating_max: int | None = None
    history: list[int] = []
    decisions: list[dict] = []
    findings: list[Finding] = []
    seen_states: set[tuple] = set()
    note = ""
    iteration = 0

    while iteration < MAX_ITERATIONS:
        # ACT — call the Quote Retriever tool for the current scope.
        qres = await quotes_tool.retrieve(
            app_id=app_id,
            embedder=embedder,
            vector_store=vector_store,
            query_text=query,
            start=start,
            end=end,
            rating_max=rating_max,
            limit=50,
        )
        # OBSERVE
        support = len(qres.quotes)
        denominator = qres.total_in_scope
        negatives = [q for q in qres.quotes if q.rating is not None and q.rating <= 2]
        neg_share = round(len(negatives) / support, 3) if support else None
        sample = [asdict(q) for q in qres.quotes[:5]]
        history.append(support)

        # JUDGE — the Critic gates the claim.
        finding = critic.assess(
            claim=f"reviews about '{query}'",
            support=support,
            denominator=denominator,
            negative_share=neg_share,
            sample_quotes=sample,
        )
        if finding.accepted:
            findings.append(finding)

        # Cycle detection — never re-investigate an identical scope (EC-P4-02).
        sig = (query, rating_max)
        if sig in seen_states:
            note = "stopped: repeated state (cycle)"
            iteration += 1
            break
        seen_states.add(sig)

        # DECIDE — reasoner picks the next constrained action (free tier).
        context = {
            "topic": topic,
            "query": query,
            "support": support,
            "denominator": denominator,
            "iteration": iteration,
            "history": history,
            "sample_quotes": sample,
        }
        decision = await asyncio.to_thread(reasoner.next_action, context)
        decisions.append(
            {
                "iteration": iteration,
                "action": decision.action.value,
                "query": decision.query,
                "reason": decision.reason,
                "support": support,
            }
        )
        iteration += 1

        if decision.action == Action.STOP:
            break
        if decision.action == Action.BROADEN:
            rating_max = None
            query = decision.query or topic
        elif decision.action == Action.NARROW:
            rating_max = decision.rating_max or 2
            query = decision.query or query
        elif decision.action in (Action.REFORMULATE, Action.INVESTIGATE_CORRELATED):
            query = decision.query or topic

    final = _dedup_findings(findings)
    if final:
        result = AnalysisResult("ok", topic, [asdict(f) for f in final], iteration, decisions, note=note)
    else:
        result = AnalysisResult(
            "no_signal", topic, [], iteration, decisions,
            note=note or f"no sufficient evidence for '{topic}'",
        )

    if cache is not None and cache_key is not None:
        payload = asdict(result)
        payload.pop("status")
        cache.put(cache_key, payload)
    return result
