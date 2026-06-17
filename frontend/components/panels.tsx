import type { ReactNode } from "react";
import type {
  ConfidenceVolume,
  Keyword,
  PriorityArea,
  Quote,
  Recommendation,
  Report,
  ThemeSentiment,
  ThemeStat,
  Trend,
} from "@/lib/types";

const TREND_ALERT_THRESHOLD = 15; // percent

function Card({ title, source, children }: { title: string; source: string; children: ReactNode }) {
  return (
    <section className="rounded-xl border border-slate-800 bg-slate-900/50 p-5">
      <div className="mb-3 flex items-baseline justify-between">
        <h2 className="text-sm font-semibold tracking-wide text-slate-200">{title}</h2>
        <span className="text-[10px] uppercase tracking-wider text-slate-500">{source}</span>
      </div>
      {children}
    </section>
  );
}

function ConfidenceBadge({ confidence }: { confidence: string }) {
  // Default to a cautious label if confidence is missing (EC-P6-06).
  const c = confidence || "unverified";
  const color =
    c === "high"
      ? "bg-emerald-500/15 text-emerald-300"
      : c === "medium"
        ? "bg-amber-500/15 text-amber-300"
        : "bg-slate-600/30 text-slate-300";
  return <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${color}`}>{c}</span>;
}

export function EmptyState({ label }: { label: string }) {
  return <p className="text-sm text-slate-500">{label}</p>;
}

export function Kpis({ kpis, trend }: { kpis: Report["kpis"]; trend: Trend }) {
  const cards = [
    { label: "Reviews Analysed", value: kpis.reviews_analysed.toLocaleString() },
    { label: "Average Rating", value: kpis.avg_rating ?? "n/a" },
    { label: "Sentiment Score", value: kpis.sentiment_score ?? "n/a" },
    { label: "Themes", value: kpis.theme_count },
  ];
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
      {cards.map((c) => (
        <div key={c.label} className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
          <div className="text-2xl font-semibold">{c.value}</div>
          <div className="mt-1 text-xs text-slate-400">{c.label}</div>
        </div>
      ))}
    </div>
  );
}

export function TrendAlert({ trend }: { trend: Trend }) {
  // Suppress alerts on insufficient base or sub-threshold movement (EC-P6-08 / EC-X-03).
  if (!trend.base_sufficient || trend.delta_pct === null) return null;
  if (Math.abs(trend.delta_pct) < TREND_ALERT_THRESHOLD) return null;
  const up = trend.delta_pct > 0;
  return (
    <div
      className={`rounded-xl border p-4 text-sm ${
        up ? "border-rose-800 bg-rose-950/40 text-rose-200" : "border-emerald-800 bg-emerald-950/40 text-emerald-200"
      }`}
    >
      <strong>Trend alert:</strong> review volume {up ? "rose" : "fell"} {Math.abs(trend.delta_pct)}% vs the
      prior window ({trend.prior} → {trend.current}).
    </div>
  );
}

export function Narrative({ narrative, status }: { narrative: string | null; status: string }) {
  return (
    <Card title="Summary" source="Analyst Agent · 1 synthesis call">
      {status === "ok" && narrative ? (
        <p className="text-sm leading-relaxed text-slate-300">{narrative}</p>
      ) : (
        <p className="text-sm text-slate-500">
          Narrative temporarily unavailable — the quantitative report below is complete and verified.
        </p>
      )}
    </Card>
  );
}

function priorityBucket(a: PriorityArea): "impact" | "frequency" | "monitor" {
  if (a.impact >= 0.5 && a.score > 0) return "impact";
  if (a.frequency >= 0.2) return "frequency";
  return "monitor";
}

export function PriorityRadar({ areas }: { areas: PriorityArea[] }) {
  const buckets = {
    impact: { title: "High Impact (fix first)", items: [] as PriorityArea[] },
    frequency: { title: "High Frequency (volume)", items: [] as PriorityArea[] },
    monitor: { title: "Monitor", items: [] as PriorityArea[] },
  };
  for (const a of areas) buckets[priorityBucket(a)].items.push(a);

  return (
    <Card title="PM Priority Radar" source="Stats Engine score · agent rationale">
      {areas.length === 0 ? (
        <EmptyState label="No themes to prioritise yet." />
      ) : (
        <div className="grid gap-4 md:grid-cols-3">
          {Object.values(buckets).map((b) => (
            <div key={b.title}>
              <h3 className="mb-2 text-xs font-semibold text-slate-400">{b.title}</h3>
              <ul className="space-y-2">
                {b.items.length === 0 && <li className="text-xs text-slate-600">—</li>}
                {b.items.map((a) => (
                  <li key={a.theme_id} className="rounded-lg border border-slate-800 p-2">
                    <div className="flex items-center justify-between">
                      <span className="text-sm">{a.label ?? "Unlabelled"}</span>
                      <span className="text-xs text-slate-400">score {a.score}</span>
                    </div>
                    <div className="text-[11px] text-slate-500">{a.count} reviews</div>
                    {a.rationale && <p className="mt-1 text-[11px] text-slate-400">{a.rationale}</p>}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

function SentimentBar({ s }: { s: ThemeSentiment }) {
  const total = s.total || 1;
  const seg = (n: number) => `${(n / total) * 100}%`;
  return (
    <div className="mt-1">
      <div className="flex h-2 overflow-hidden rounded bg-slate-800">
        <div className="bg-emerald-500" style={{ width: seg(s.positive) }} />
        <div className="bg-slate-500" style={{ width: seg(s.neutral) }} />
        <div className="bg-rose-500" style={{ width: seg(s.negative) }} />
      </div>
      <div className="mt-1 flex gap-3 text-[10px] text-slate-400">
        <span>+{s.positive} positive</span>
        <span>{s.neutral} neutral</span>
        <span>-{s.negative} negative</span>
      </div>
    </div>
  );
}

export function Themes({
  distribution,
  sentiment,
  highlight,
}: {
  distribution: ThemeStat[];
  sentiment: ThemeSentiment[];
  highlight: string | null;
}) {
  const sentByTheme = new Map(sentiment.map((s) => [s.theme_id, s]));
  return (
    <Card title="Top Themes" source="Theme Clusterer + Sentiment">
      {distribution.length === 0 ? (
        <EmptyState label="Not enough data to separate themes." />
      ) : (
        <ul className="space-y-3">
          {distribution.map((t) => {
            const isHit = highlight && (t.label ?? "").toLowerCase().includes(highlight.toLowerCase());
            const s = sentByTheme.get(t.theme_id);
            return (
              <li
                key={t.theme_id}
                className={`rounded-lg border p-3 ${isHit ? "border-sky-600 bg-sky-950/30" : "border-slate-800"}`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">{t.label ?? "Unlabelled"}</span>
                  <span className="text-xs text-slate-400">
                    {t.count} {t.share !== null ? `· ${Math.round(t.share * 100)}%` : ""}
                  </span>
                </div>
                {s && <SentimentBar s={s} />}
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}

function Stars({ rating }: { rating: number | null }) {
  if (rating === null) return <span className="text-xs text-slate-500">no rating</span>;
  return (
    <span className="text-xs text-amber-400" aria-label={`${rating} of 5 stars`}>
      {"★".repeat(rating)}
      <span className="text-slate-700">{"★".repeat(5 - rating)}</span>
    </span>
  );
}

export function UserVoices({ quotes }: { quotes: Quote[] }) {
  return (
    <Card title="User Voices" source="Quote Retriever · verbatim, Critic-validated">
      {quotes.length === 0 ? (
        <EmptyState label="No representative quotes for this scope." />
      ) : (
        <ul className="space-y-3">
          {quotes.slice(0, 12).map((q) => (
            <li key={q.source_review_id} className="rounded-lg border border-slate-800 p-3">
              <p dir="auto" className="line-clamp-4 text-sm text-slate-300">
                “{q.text}”
              </p>
              <div className="mt-2 flex items-center gap-3">
                <Stars rating={q.rating} />
                {q.theme_label && <span className="text-[11px] text-slate-500">{q.theme_label}</span>}
                {q.platform && <span className="text-[11px] text-slate-600">{q.platform}</span>}
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

export function Keywords({
  keywords,
  selected,
  onSelect,
}: {
  keywords: Keyword[];
  selected: string | null;
  onSelect: (term: string | null) => void;
}) {
  return (
    <Card title="Trending Keywords" source="Keyword Extractor">
      {keywords.length === 0 ? (
        <EmptyState label="No trending keywords yet." />
      ) : (
        <div className="flex flex-wrap gap-2">
          {keywords.map((k) => {
            const active = selected === k.term;
            return (
              <button
                key={k.term}
                onClick={() => onSelect(active ? null : k.term)}
                className={`rounded-full px-2.5 py-1 text-xs ${
                  active ? "bg-sky-600 text-white" : "bg-slate-800 text-slate-300 hover:bg-slate-700"
                }`}
              >
                {k.term} <span className="text-slate-400">{k.frequency}</span>
              </button>
            );
          })}
        </div>
      )}
    </Card>
  );
}

export function Recommendations({ recs }: { recs: Recommendation[] }) {
  return (
    <Card title="Recommendations" source="Analyst Agent · synthesis">
      {recs.length === 0 ? (
        <EmptyState label="No recommendations available (synthesis not run)." />
      ) : (
        <ul className="list-disc space-y-1.5 pl-5 text-sm text-slate-300">
          {recs.map((r, i) => (
            <li key={i}>{r.text}</li>
          ))}
        </ul>
      )}
    </Card>
  );
}

export function ConfidenceVolumePanel({ items }: { items: ConfidenceVolume[] }) {
  return (
    <Card title="Confidence & Volume" source="every insight shows its denominator">
      {items.length === 0 ? (
        <EmptyState label="No themes to report." />
      ) : (
        <ul className="space-y-2">
          {items.map((it) => (
            <li key={it.theme_id} className="flex items-center justify-between text-sm">
              <span className="text-slate-300">{it.label ?? "Unlabelled"}</span>
              <span className="flex items-center gap-2 text-slate-400">
                <span className="text-xs">
                  {it.count} of {it.denominator}
                </span>
                <ConfidenceBadge confidence={it.confidence} />
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
