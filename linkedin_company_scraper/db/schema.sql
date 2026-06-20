-- LinkedIn Company Scraper — PostgreSQL schema
-- Run once:  psql -f schema.sql <your_db>

CREATE TABLE IF NOT EXISTS industry (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS location (
    id          SERIAL PRIMARY KEY,
    city        TEXT,
    state       TEXT,
    country     TEXT,
    UNIQUE (city, state, country)
);

CREATE TABLE IF NOT EXISTS company (
    id              SERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    overview        TEXT,
    industry_id     INTEGER REFERENCES industry(id),
    hq_location_id  INTEGER REFERENCES location(id),
    logo            TEXT,
    website         TEXT,
    platform        TEXT,           -- e.g. LinkedIn profile URL
    source          TEXT NOT NULL,   -- e.g. 'linkedin'
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- De-dup key: same source + same platform identifier = same record.
    UNIQUE (source, platform)
);

-- Indexes for common lookups.
CREATE INDEX IF NOT EXISTS idx_company_name        ON company (name);
CREATE INDEX IF NOT EXISTS idx_company_source       ON company (source);
CREATE INDEX IF NOT EXISTS idx_company_industry     ON company (industry_id);
CREATE INDEX IF NOT EXISTS idx_company_hq_location  ON company (hq_location_id);
CREATE INDEX IF NOT EXISTS idx_location_city        ON location (city);
CREATE INDEX IF NOT EXISTS idx_industry_name        ON industry (name);
