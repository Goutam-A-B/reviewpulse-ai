"""Phase 5 — Synthesis & Orchestration.

Assembles the verified quantitative report (Phases 2-4, free) and spends exactly
one Gemini free-tier call to write the narrative + recommendations. A hard premium
ceiling and graceful degradation guarantee the user always gets the full
quantitative report, even if synthesis fails. Routing/caching are control-flow,
not an agent.
"""
