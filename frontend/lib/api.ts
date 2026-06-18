import type { Keyword, ReportResponse } from "./types";

// Defaults to the deployed backend so the hosted dashboard works without any
// build-time env var. Set NEXT_PUBLIC_API_URL to override (e.g. localhost for dev).
const API = process.env.NEXT_PUBLIC_API_URL ?? "https://reviewpulse-ai-oavt.onrender.com";

export type ReportQuery = {
  app_id?: string;
  platform?: string;
  name?: string;
  start?: string;
  end?: string;
};

export async function fetchReport(q: ReportQuery, signal?: AbortSignal): Promise<ReportResponse> {
  const res = await fetch(`${API}/report`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(q),
    signal,
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`Report request failed (${res.status}). ${detail}`);
  }
  return res.json();
}

export async function fetchKeywords(appId: string, signal?: AbortSignal): Promise<Keyword[]> {
  try {
    const res = await fetch(`${API}/query/keywords?app_id=${encodeURIComponent(appId)}`, { signal });
    if (!res.ok) return [];
    const data = await res.json();
    return data.keywords ?? [];
  } catch {
    return [];
  }
}
