"use client";

import { useRef, useState } from "react";
import { ReportControls } from "@/components/controls";
import {
  ConfidenceVolumePanel,
  Keywords,
  Kpis,
  Narrative,
  PriorityRadar,
  Recommendations,
  Themes,
  TrendAlert,
  UserVoices,
} from "@/components/panels";
import { fetchKeywords, fetchReport, type ReportQuery } from "@/lib/api";
import { isReport, type Keyword, type Report } from "@/lib/types";

export default function Page() {
  const [report, setReport] = useState<Report | null>(null);
  const [keywords, setKeywords] = useState<Keyword[]>([]);
  const [selectedKeyword, setSelectedKeyword] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [noSignal, setNoSignal] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  async function run(q: ReportQuery) {
    // Cancel any in-flight request so a refilter never mixes two reports (EC-P6-02).
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setError(null);
    setNoSignal(null);
    setReport(null);
    setKeywords([]);
    setSelectedKeyword(null);

    try {
      const res = await fetchReport(q, controller.signal);
      if (!isReport(res)) {
        setNoSignal(res.detail ?? `No report available (${res.status}).`);
        return;
      }
      setReport(res);
      setKeywords(await fetchKeywords(res.app_id, controller.signal));
    } catch (e) {
      if ((e as Error).name === "AbortError") return;
      setError((e as Error).message);
    } finally {
      if (abortRef.current === controller) setLoading(false);
    }
  }

  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
      <header className="mb-6">
        <h1 className="text-2xl font-semibold">ReviewPulse AI</h1>
        <p className="text-sm text-slate-400">
          Agentic product intelligence from app-store reviews — every figure traces to a verified review.
        </p>
      </header>

      <ReportControls onRun={run} loading={loading} />

      {loading && (
        <p className="mt-8 text-sm text-slate-400">
          Building report… a cold (never-seen) app self-ingests first and may take up to a minute.
        </p>
      )}
      {error && <p className="mt-8 text-sm text-rose-400">{error}</p>}
      {noSignal && (
        <div className="mt-8 rounded-xl border border-slate-800 bg-slate-900/50 p-6">
          <h2 className="text-sm font-semibold">No signal</h2>
          <p className="mt-1 text-sm text-slate-400">{noSignal}</p>
          <p className="mt-2 text-xs text-slate-600">
            The product says so plainly rather than inventing a trend.
          </p>
        </div>
      )}

      {report && (
        <div className="mt-6 space-y-4">
          <Kpis kpis={report.kpis} trend={report.sections.trends_and_correlations.reviews_trend} />
          <TrendAlert trend={report.sections.trends_and_correlations.reviews_trend} />
          <Narrative narrative={report.narrative} status={report.narrative_status} />
          <PriorityRadar areas={report.sections.priority_areas} />
          <div className="grid gap-4 md:grid-cols-2">
            <Themes
              distribution={report.sections.top_themes}
              sentiment={report.sections.theme_sentiment}
              highlight={selectedKeyword}
            />
            <UserVoices quotes={report.sections.customer_quotes} />
          </div>
          <Keywords keywords={keywords} selected={selectedKeyword} onSelect={setSelectedKeyword} />
          <div className="grid gap-4 md:grid-cols-2">
            <Recommendations recs={report.sections.recommendations} />
            <ConfidenceVolumePanel items={report.sections.confidence_volume} />
          </div>
          <p className="pt-2 text-center text-[11px] text-slate-600">
            Premium calls used: {report.premium_calls_used} · narrative: {report.narrative_status}
          </p>
        </div>
      )}
    </main>
  );
}
