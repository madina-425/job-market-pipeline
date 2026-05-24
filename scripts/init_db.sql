-- scripts/init_db.sql
-- Run once to initialise the job market database.
-- Compatible with PostgreSQL 14+

CREATE DATABASE jobmarket;
\c jobmarket;

-- ── Core tables ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS jobs (
    id              SERIAL PRIMARY KEY,
    external_id     TEXT NOT NULL,
    fingerprint     TEXT NOT NULL UNIQUE,
    source          TEXT NOT NULL,          -- hh, telegram
    title           TEXT,
    company         TEXT,
    location        TEXT,
    country         TEXT,
    salary_from     NUMERIC,
    salary_to       NUMERIC,
    salary_currency TEXT,
    salary_usd_from NUMERIC,
    salary_usd_to   NUMERIC,
    salary_usd_mid  NUMERIC,
    remote_type     TEXT,                         -- remote | hybrid | on-site | unknown
    seniority       TEXT,                         -- junior | mid | senior | unknown
    role_category   TEXT,                         -- Data Analyst | Data Engineer | ML Engineer | Other
    skills          TEXT[],
    url             TEXT,
    published_at    TIMESTAMPTZ,
    collected_at    TIMESTAMPTZ DEFAULT now(),
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_jobs_source          ON jobs(source);
CREATE INDEX IF NOT EXISTS idx_jobs_role_category   ON jobs(role_category);
CREATE INDEX IF NOT EXISTS idx_jobs_published_at    ON jobs(published_at);
CREATE INDEX IF NOT EXISTS idx_jobs_remote_type     ON jobs(remote_type);
CREATE INDEX IF NOT EXISTS idx_jobs_location        ON jobs(location);

-- ── Read-only application user ────────────────────────────────────────────────
-- Run as superuser: 
-- хочу оставить для аус рдс

-- CREATE ROLE pipeline_user LOGIN PASSWORD 'change_me';
-- GRANT CONNECT ON DATABASE jobmarket TO pipeline_user;
-- GRANT USAGE ON SCHEMA public TO pipeline_user;
-- GRANT SELECT, INSERT, UPDATE ON jobs TO pipeline_user;
-- GRANT SELECT ON mv_skill_demand, mv_salary_summary, mv_remote_trends, mv_city_hiring TO pipeline_user;
-- GRANT USAGE, SELECT ON SEQUENCE jobs_id_seq TO pipeline_user;
