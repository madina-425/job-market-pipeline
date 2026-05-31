# AWS setup (RDS + S3)

## What goes where

| Data | Where | Why |
|------|--------|-----|
| **Jobs for dashboards** | **RDS PostgreSQL** | SQL, fast filters, Streamlit/Metabase connect here |
| Raw JSON + Parquet | **S3** | Cheap archive, re-runs, data lake |
| **Pipeline logs** | **S3** (`logs/…`) | Large files; use lifecycle rules, not RDS |
| Local `logs/` | Your laptop / CI artifact | Dev only; rotated automatically |

**Rule of thumb:** develop locally with Docker Postgres; run daily ETL against **the same schema on RDS** in AWS.

---

## 1. S3 bucket

1. Create a bucket, e.g. `jobmarket-pipeline-data` (region `eu-west-1`).
2. Block public access (default).
3. Optional **lifecycle** on prefix `logs/`:
   - Transition to S3 Glacier after 30 days
   - Expire after 365 days

Layout after runs:

```text
s3://YOUR_BUCKET/
  raw/headhunter/YYYY/MM/DD/jobs_HH-MM-SS.json
  processed/YYYY/MM/DD/jobs_clean.parquet
  reports/YYYY-MM-DD/summary.json
  logs/YYYY/MM/DD/pipeline_HH-MM-SS.log
```

---

## 2. RDS PostgreSQL

1. **RDS** → Create database → **PostgreSQL 15**.
2. DB identifier: e.g. `jobmarket-db`.
3. Master username / password (save for GitHub Secrets).
4. **Public access**: Yes *only if* you run ETL from GitHub Actions without a VPN (portfolio setup). Prefer strong password + security group limited if possible.
5. Security group: inbound **5432** from your IP (dev) and/or `0.0.0.0/0` for GitHub (less secure; acceptable for learning projects).
6. Initial database name: `jobmarket`.

### Apply schema

From your machine (with `psql` or DBeaver), connect to RDS and run:

```bash
psql "postgresql://USER:PASSWORD@ENDPOINT.rds.amazonaws.com:5432/jobmarket" -f scripts/init_db.sql
```

If `init_db.sql` fails on `CREATE DATABASE`, connect to `jobmarket` and run only the `CREATE TABLE` section.

---

## 3. IAM user for the pipeline

Create IAM user `jobmarket-pipeline` with programmatic access. Attach inline policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:GetObject", "s3:ListBucket"],
      "Resource": [
        "arn:aws:s3:::YOUR_BUCKET_NAME",
        "arn:aws:s3:::YOUR_BUCKET_NAME/*"
      ]
    }
  ]
}
```

RDS does not need IAM — only host, user, password in secrets.

---

## 4. GitHub Actions secrets

Repository → **Settings** → **Secrets and variables** → **Actions**:

| Secret | Value |
|--------|--------|
| `AWS_ACCESS_KEY_ID` | IAM access key |
| `AWS_SECRET_ACCESS_KEY` | IAM secret |
| `AWS_REGION` | `eu-west-1` |
| `S3_BUCKET_NAME` | bucket name |
| `DB_HOST` | RDS endpoint `xxx.region.rds.amazonaws.com` |
| `DB_PORT` | `5432` |
| `DB_NAME` | `jobmarket` |
| `DB_USER` | RDS master user |
| `DB_PASSWORD` | RDS password |
| `HH_USER_AGENT` | Your app name + email (HH requirement) |

Optional: `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `EXCHANGE_RATE_API_KEY`.

Workflow **Daily ETL Pipeline** will run on schedule or **Run workflow**.

---

## 5. Verify data exists

After a successful run:

```bash
export $(grep -v '^#' .env | xargs)   # or set vars manually
python -m scripts.verify_data
```

You should see job counts from RDS and recent S3 keys under `raw/`, `processed/`, `reports/`, `logs/`.

---

## 6. Dashboards later

Connect **Streamlit / Metabase / Grafana** to RDS:

- Host: same as `DB_HOST`
- Database: `jobmarket`
- Table: `jobs`

Use `RDSLoader.load_for_analytics()` or SQL directly. S3 Parquet is optional for heavy historical analysis.
