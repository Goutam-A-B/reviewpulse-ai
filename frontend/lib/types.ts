export type Trend = {
  current: number;
  prior: number;
  delta_pct: number | null;
  base_sufficient: boolean;
};

export type ThemeStat = {
  theme_id: string;
  label: string | null;
  count: number;
  share: number | null;
};

export type ThemeSentiment = {
  theme_id: string;
  label: string | null;
  positive: number;
  neutral: number;
  negative: number;
  total: number;
};

export type Quote = {
  text: string;
  rating: number | null;
  review_date: string | null;
  source_review_id: string;
  platform: string | null;
  theme_id?: string;
  theme_label?: string | null;
};

export type PriorityArea = {
  theme_id: string;
  label: string | null;
  count: number;
  impact: number;
  frequency: number;
  score: number;
  rationale: string | null;
};

export type Recommendation = { text: string; theme_id: string | null };

export type ConfidenceVolume = {
  theme_id: string;
  label: string | null;
  count: number;
  denominator: number;
  confidence: string;
};

export type Report = {
  app_id: string;
  app: string | null;
  window: { start: string | null; end: string | null };
  kpis: {
    reviews_analysed: number;
    avg_rating: number | null;
    sentiment_score: number | null;
    theme_count: number;
  };
  sections: {
    top_themes: ThemeStat[];
    theme_sentiment: ThemeSentiment[];
    customer_quotes: Quote[];
    trends_and_correlations: { reviews_trend: Trend };
    theme_distribution: ThemeStat[];
    recommendations: Recommendation[];
    priority_areas: PriorityArea[];
    confidence_volume: ConfidenceVolume[];
  };
  narrative: string | null;
  narrative_status: string;
  premium_calls_used: number;
};

export type Unavailable = { status: string; detail?: string };
export type ReportResponse = Report | Unavailable;

export function isReport(r: ReportResponse): r is Report {
  return (r as Report).kpis !== undefined;
}

export type Keyword = { term: string; frequency: number };
