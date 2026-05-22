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
    source          TEXT NOT NULL,                -- headhunter | djinni | remoteok
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

-- ── Analytics materialised views ─────────────────────────────────────────────

-- Top skills per role (unnest the array, count occurrences)
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_skill_demand AS
    SELECT
        role_category,
        skill,
        COUNT(*)::INT AS frequency
    FROM jobs,
         UNNEST(skills) AS skill
    WHERE published_at >= now() - INTERVAL '90 days'
    GROUP BY role_category, skill
    ORDER BY frequency DESC;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_skill_demand ON mv_skill_demand(role_category, skill);

-- Salary summary by role + seniority
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_salary_summary AS
    SELECT
        role_category,
        seniority,
        COUNT(*)                            AS job_count,
        ROUND(AVG(salary_usd_mid)::NUMERIC, 0) AS avg_salary_usd,
        ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY salary_usd_mid)::NUMERIC, 0) AS median_salary_usd,
        ROUND(MIN(salary_usd_mid)::NUMERIC, 0) AS min_salary_usd,
        ROUND(MAX(salary_usd_mid)::NUMERIC, 0) AS max_salary_usd
    FROM jobs
    WHERE salary_usd_mid IS NOT NULL
      AND published_at >= now() - INTERVAL '90 days'
    GROUP BY role_category, seniority;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_salary_summary ON mv_salary_summary(role_category, seniority);

-- Remote work distribution
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_remote_trends AS
    SELECT
        DATE_TRUNC('week', published_at) AS week,
        remote_type,
        COUNT(*)::INT                    AS job_count
    FROM jobs
    WHERE published_at >= now() - INTERVAL '90 days'
    GROUP BY week, remote_type
    ORDER BY week;

-- City-level hiring
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_city_hiring AS
    SELECT
        location,
        role_category,
        COUNT(*)::INT AS job_count
    FROM jobs
    WHERE location IS NOT NULL
      AND published_at >= now() - INTERVAL '90 days'
    GROUP BY location, role_category
    ORDER BY job_count DESC;

-- ── Refresh helper (call after each pipeline run) ─────────────────────────────

-- REFRESH MATERIALIZED VIEW CONCURRENTLY mv_skill_demand;
-- REFRESH MATERIALIZED VIEW CONCURRENTLY mv_salary_summary;
-- REFRESH MATERIALIZED VIEW CONCURRENTLY mv_remote_trends;
-- REFRESH MATERIALIZED VIEW CONCURRENTLY mv_city_hiring;

-- ── Read-only application user ────────────────────────────────────────────────
-- Run as superuser:

-- CREATE ROLE pipeline_user LOGIN PASSWORD 'change_me';
-- GRANT CONNECT ON DATABASE jobmarket TO pipeline_user;
-- GRANT USAGE ON SCHEMA public TO pipeline_user;
-- GRANT SELECT, INSERT, UPDATE ON jobs TO pipeline_user;
-- GRANT SELECT ON mv_skill_demand, mv_salary_summary, mv_remote_trends, mv_city_hiring TO pipeline_user;
-- GRANT USAGE, SELECT ON SEQUENCE jobs_id_seq TO pipeline_user;
