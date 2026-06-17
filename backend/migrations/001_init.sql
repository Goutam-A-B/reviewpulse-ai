-- ReviewPulse AI — schema v1 (Phase 0).
-- Mirrors docs/phasewise-architecture.md Appendix A. Apply to Supabase/Postgres.

create extension if not exists "uuid-ossp";

create table if not exists apps (
    id                uuid primary key default uuid_generate_v4(),
    name              text not null,
    store_app_id      text not null,                     -- package name (Play) / numeric id (App Store)
    store_url         text,
    platform          text not null check (platform in ('android', 'ios', 'both')),
    first_ingested_at timestamptz,
    last_refreshed_at timestamptz,
    created_at        timestamptz not null default now(),
    unique (platform, store_app_id)                      -- idempotent app upsert (Phase 1)
);

create table if not exists reviews (
    id               uuid primary key default uuid_generate_v4(),
    app_id           uuid not null references apps(id) on delete cascade,
    platform         text not null check (platform in ('android', 'ios')),
    source_review_id text not null,
    title            text,
    text_raw         text,
    text_clean       text,
    rating           int check (rating between 1 and 5),
    review_date      timestamptz,                       -- normalised to UTC (EC-X-01)
    ingested_at      timestamptz not null default now(),
    is_spam          boolean not null default false,
    is_duplicate     boolean not null default false,
    is_analysable    boolean not null default true,     -- false if empty after clean (EC-P2-03)
    -- idempotent ingest: never two rows for the same source review (EC-X-23)
    unique (app_id, platform, source_review_id)
);
create index if not exists idx_reviews_app_date   on reviews (app_id, review_date);
create index if not exists idx_reviews_app_rating on reviews (app_id, rating);

create table if not exists sentiment (
    review_id     uuid primary key references reviews(id) on delete cascade,
    label         text not null check (label in ('positive', 'neutral', 'negative')),
    model_version text not null
);

create table if not exists themes (
    id            uuid primary key default uuid_generate_v4(),
    app_id        uuid not null references apps(id) on delete cascade,
    label         text not null,
    description   text,
    size          int not null default 0,
    model_version text not null
);

create table if not exists review_themes (
    review_id uuid not null references reviews(id) on delete cascade,
    theme_id  uuid not null references themes(id) on delete cascade,
    distance  double precision,
    primary key (review_id, theme_id)
);

create table if not exists keywords (
    id           uuid primary key default uuid_generate_v4(),
    app_id       uuid not null references apps(id) on delete cascade,
    term         text not null,
    frequency    int not null default 0,
    window_start timestamptz,
    window_end   timestamptz
);

-- Agent replay cache: identical request replays the identical investigation.
-- data_version invalidates the replay when new reviews are ingested (EC-P4-09).
create table if not exists decision_paths (
    id              uuid primary key default uuid_generate_v4(),
    app_id          uuid not null references apps(id) on delete cascade,
    topic           text not null,
    timeframe_hash  text not null,
    data_version    text not null,
    graph_trace_json jsonb not null,
    findings_json    jsonb not null,
    created_at      timestamptz not null default now(),
    unique (app_id, topic, timeframe_hash, data_version)
);

-- Query-path report cache. narrative_status records graceful degradation so a
-- report missing its narrative is never served as if complete (EC-P5-07).
create table if not exists reports (
    id                 uuid primary key default uuid_generate_v4(),
    app_id             uuid not null references apps(id) on delete cascade,
    topic              text,
    timeframe          text,
    data_version       text,
    report_json        jsonb not null,
    narrative_status   text not null default 'ok' check (narrative_status in ('ok', 'unavailable')),
    premium_calls_used int not null default 0,
    created_at         timestamptz not null default now()
);
