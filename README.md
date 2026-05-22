# Job Market Analytics Pipeline 🇰🇿

> End-to-end data engineering pipeline that tracks **Data Analyst**, **Data Engineer**, and **ML Engineer** job openings across Kazakhstan — built with Python, Docker, and AWS.

---

## Architecture

```
Job APIs / Web Scrapers
        ↓
  Docker Container
  (Python ETL Pipeline)
     ├─ Extract   → HeadHunter API, Djinni, RemoteOK scraper
     ├─ Transform → pandas: clean, normalise, deduplicate
     └─ Load      → AWS S3 (raw) + RDS PostgreSQL (processed)
        ↓
  Analytics Processing
  (SQL aggregations + pandas reports)
        ↓
  Streamlit Dashboard
  (charts, maps, filters)
        ↓
  Automation
  (GitHub Actions cron + Airflow DAG)
```

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11 |
| Data collection | `requests`, `BeautifulSoup4`, `Scrapy` |
| Transformation | `pandas`, `pycountry` |
| ORM / DB | `SQLAlchemy`, PostgreSQL (AWS RDS) |
| Cloud storage | AWS S3 (`boto3`) |
| Monitoring | AWS CloudWatch, Python `logging` |
| Containerisation | Docker, docker-compose |
| Dashboard | Streamlit |
| Automation | GitHub Actions, Apache Airflow, AWS EventBridge |
| Testing | `pytest` |
| CI/CD | GitHub Actions |

## Quick Start

```bash
# 1. Clone
git clone https://github.com/yourusername/job-market-pipeline.git
cd job-market-pipeline

# 2. Copy and fill environment variables
cp .env.example .env

# 3. Run the full pipeline in Docker
docker-compose up --build

# 4. View the dashboard
open http://localhost:8501
```

## Project Structure

```
job-market-pipeline/
├── src/
│   ├── collectors/          # API + scraper modules
│   │   ├── hh_collector.py  # HeadHunter API
│   │   ├── djinni_collector.py
│   │   └── remoteok_collector.py
│   ├── transformers/
│   │   └── job_transformer.py  # All cleaning & normalisation
│   ├── loaders/
│   │   ├── s3_loader.py        # Raw JSON → S3
│   │   └── rds_loader.py       # Processed → PostgreSQL
│   ├── analytics/
│   │   └── analytics.py        # Aggregation queries
│   └── utils/
│       ├── logger.py
│       └── currency.py
├── pipelines/
│   └── etl_pipeline.py         # Orchestrates E→T→L
├── configs/
│   └── settings.py             # All config via env vars
├── dashboard/
│   └── app.py                  # Streamlit app
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── tests/
│   ├── test_transformer.py
│   └── test_loaders.py
├── scripts/
│   └── init_db.sql             # Database schema
├── .github/workflows/
│   ├── pipeline.yml            # Daily ETL run
│   └── ci.yml                  # Tests + linting
├── .env.example
├── requirements.txt
└── README.md
```

## Data Model

```
jobs              — one row per unique job posting
job_skills        — many-to-many: jobs ↔ skills
skills            — normalised skill catalogue
companies         — hiring companies
analytics_daily   — pre-aggregated daily snapshots
```

## Dashboard Screens

- **Overview** — total jobs, salary distribution, remote %
- **Skills** — bar chart of top 30 skills by role
- **Salaries** — box plots by role, city, seniority
- **Companies** — top hiring companies
- **Geography** — city-level map (Kazakhstan)
- **Trends** — 30-day posting volume time series

## Resume Bullets

- Designed and implemented an end-to-end data engineering pipeline ingesting 500+ daily job postings from 3 sources (HeadHunter API, Djinni, RemoteOK) using Python, Docker, and AWS (S3 + RDS PostgreSQL)
- Engineered a modular ETL system with pandas-based transformations: salary normalisation, skill extraction, deduplication, and currency conversion
- Automated daily pipeline execution using GitHub Actions and AWS EventBridge; pipeline failures send alerts via CloudWatch
- Built an interactive Streamlit dashboard visualising salary trends, skill demand, and hiring geography for the Kazakhstani job market
- Containerised the entire pipeline with Docker and docker-compose; enforced data quality via pytest test suite with 85%+ coverage

---

*Built as a portfolio project to demonstrate real-world data engineering skills.*
