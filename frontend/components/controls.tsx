"use client";

import { useState } from "react";
import type { ReportQuery } from "@/lib/api";

type Mode = "app_id" | "name";
type Preset = "all" | "2w" | "5w" | "10w" | "custom";

function weeksAgoIso(weeks: number): string {
  const d = new Date();
  d.setUTCDate(d.getUTCDate() - weeks * 7);
  return d.toISOString();
}

export function ReportControls({
  onRun,
  loading,
}: {
  onRun: (q: ReportQuery) => void;
  loading: boolean;
}) {
  const [mode, setMode] = useState<Mode>("name");
  const [appId, setAppId] = useState("");
  const [name, setName] = useState("");
  const [platform, setPlatform] = useState("android");
  const [preset, setPreset] = useState<Preset>("all");
  const [customStart, setCustomStart] = useState("");
  const [customEnd, setCustomEnd] = useState("");
  const [error, setError] = useState<string | null>(null);

  function window(): { start?: string; end?: string } | null {
    const now = new Date().toISOString();
    if (preset === "all") return {};
    if (preset === "2w") return { start: weeksAgoIso(2), end: now };
    if (preset === "5w") return { start: weeksAgoIso(5), end: now };
    if (preset === "10w") return { start: weeksAgoIso(10), end: now };
    // custom — validate (EC-P6-12)
    if (!customStart || !customEnd) {
      setError("Pick both start and end dates for a custom range.");
      return null;
    }
    const s = new Date(`${customStart}T00:00:00Z`);
    const e = new Date(`${customEnd}T23:59:59Z`);
    if (s > e) {
      setError("Start date must be on or before the end date.");
      return null;
    }
    if (s > new Date()) {
      setError("Start date cannot be in the future.");
      return null;
    }
    return { start: s.toISOString(), end: e.toISOString() };
  }

  function submit() {
    setError(null);
    const w = window();
    if (w === null) return;
    if (mode === "app_id") {
      if (!appId.trim()) return setError("Enter an app_id.");
      onRun({ app_id: appId.trim(), ...w });
    } else {
      if (!name.trim()) return setError("Enter an app name.");
      onRun({ platform, name: name.trim(), ...w });
    }
  }

  const inputCls = "rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm";

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1">
          <label className="text-[11px] text-slate-400">Look up by</label>
          <select className={inputCls} value={mode} onChange={(e) => setMode(e.target.value as Mode)}>
            <option value="name">App name (cold start ok)</option>
            <option value="app_id">app_id (already ingested)</option>
          </select>
        </div>

        {mode === "name" ? (
          <>
            <div className="flex flex-col gap-1">
              <label className="text-[11px] text-slate-400">App name</label>
              <input className={inputCls} value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. WhatsApp" />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-[11px] text-slate-400">Platform</label>
              <select className={inputCls} value={platform} onChange={(e) => setPlatform(e.target.value)}>
                <option value="android">Android</option>
                <option value="ios">iOS</option>
              </select>
            </div>
          </>
        ) : (
          <div className="flex flex-col gap-1">
            <label className="text-[11px] text-slate-400">app_id</label>
            <input className={inputCls} value={appId} onChange={(e) => setAppId(e.target.value)} placeholder="uuid" />
          </div>
        )}

        <div className="flex flex-col gap-1">
          <label className="text-[11px] text-slate-400">Timeframe</label>
          <select className={inputCls} value={preset} onChange={(e) => setPreset(e.target.value as Preset)}>
            <option value="all">All time</option>
            <option value="2w">Last 2 weeks</option>
            <option value="5w">Last 5 weeks</option>
            <option value="10w">Last 10 weeks</option>
            <option value="custom">Custom range</option>
          </select>
        </div>

        {preset === "custom" && (
          <>
            <div className="flex flex-col gap-1">
              <label className="text-[11px] text-slate-400">Start</label>
              <input type="date" className={inputCls} value={customStart} onChange={(e) => setCustomStart(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-[11px] text-slate-400">End</label>
              <input type="date" className={inputCls} value={customEnd} onChange={(e) => setCustomEnd(e.target.value)} />
            </div>
          </>
        )}

        <button
          onClick={submit}
          disabled={loading}
          className="rounded-md bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-500 disabled:opacity-50"
        >
          {loading ? "Analysing…" : "Analyse"}
        </button>
      </div>
      {error && <p className="mt-2 text-xs text-rose-400">{error}</p>}
    </div>
  );
}
