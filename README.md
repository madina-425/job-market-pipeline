# Job Market Pipeline

An ETL pipeline that collects job listings from multiple sources, transforms them, and loads into PostgreSQL with backups to AWS S3.

## Overview

This project automates the collection and processing of job market data:

- **Extract**: Collects job listings from HeadHunter API and Telegram channels
- **Transform**: Cleans, normalizes, and enriches job data with exchange rates and role classification
- **Load**: Stores processed data in PostgreSQL and persists raw/processed records to S3

## Features

-  Multi-source job collection (HeadHunter, Telegram)
-  PostgreSQL database with automatic schema management
-  S3 integration for raw and processed data archival
-  Intelligent job role classification with multilingual support
-  Real-time exchange rate integration
-  Docker support for reproducible deployments
-  Automated runs via GitHub Actions
-  Comprehensive test coverage

## Quick Start

### Prerequisites

- Python 3.10+
- PostgreSQL 12+
- AWS account (for S3 access)
- Docker (optional, for containerized deployment)

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/madina-425/job-market-pipeline.git
   cd job-market-pipeline
   ```

2. **Create virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

   Required environment variables:
   - `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` — PostgreSQL connection
   - `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `S3_BUCKET_NAME` — AWS S3
   - `HH_API_BASE_URL`, `HH_USER_AGENT` — HeadHunter API settings
   - `TELEGRAM_API_ID`, `TELEGRAM_API_HASH` (optional) — Telegram collector
   - `EXCHANGE_RATE_API_KEY` (optional) — Exchange rate service

5. **Initialize database**
   ```bash
   python scripts/verify_data.py
   ```

## Usage

### Run the Pipeline

```bash
python -m pipelines.etl_pipeline
```

Pipeline stages:
- Extracts job data from configured sources
- Validates database connection
- Transforms and normalizes records
- Upserts jobs into PostgreSQL
- Archives raw and processed data to S3

### Run Tests

```bash
pytest tests/
pytest --cov=src tests/  # With coverage
```

## Project Structure

```
job-market-pipeline/
├── configs/              # Configuration and environment loading
├── docker/
│   ├── docker-compose.yml
│   └── Dockerfile
├── docs/                 # Documentation
├── pipelines/            # ETL pipeline orchestration
├── scripts/              # Utility scripts (verification, setup)
├── src/
│   ├── collectors/       # Data collection from external sources
│   ├── loaders/          # Database and S3 operations
│   ├── transformers/     # Data cleaning and transformation
│   └── utils/            # Common utilities and logging
├── tests/                # Test suite
├── .github/workflows/    # GitHub Actions automation
└── requirements.txt      # Python dependencies
```

## Deployment

### Local Development with Docker

```bash
docker-compose -f docker/docker-compose.yml up
```

Includes PostgreSQL, ETL pipeline, and Grafana.

### GitHub Actions

The pipeline runs automatically on schedule (see `.github/workflows/pipeline.yml`). Manually trigger via:
```bash
gh workflow run pipeline.yml
```

## API Documentation

### HeadHunter Collector

Fetches job vacancies from HeadHunter API with:
- Pagination support
- Rate limiting
- Error resilience
- Automatic retry logic

### Telegram Collector

Monitors specified Telegram channels for job postings.

### Job Transformer

- Normalizes job titles and locations
- Classifies roles based on keywords (supports multilingual detection)
- Handles exchange rate conversions
- Deduplicates records

## Architecture

```
External Sources (HH, Telegram)
         ↓
    Collectors (Extract)
         ↓
    Transformer (Transform)
         ↓
    ┌────┴────┐
    ↓         ↓
   RDS      S3 Loader
 (Primary)  (Archive)
```

## Development

### Code Style

Project uses `ruff` for linting:
```bash
ruff check src/ pipelines/
ruff format src/ pipelines/
```

### Adding New Data Sources

1. Create collector class in `src/collectors/`
2. Implement `collect()` method returning list of dictionaries
3. Add to pipeline in `pipelines/etl_pipeline.py`

### Testing

Tests use `pytest`. Add new tests to `tests/` directory.

```bash
pytest tests/test_rds_connection.py -v
```

## Troubleshooting

**Database connection fails**
- Verify PostgreSQL is running
- Check credentials in `.env`
- Ensure `DB_SSLMODE` is correctly set

**S3 upload errors**
- Verify AWS credentials and permissions
- Check S3 bucket exists in correct region
- Ensure bucket policy allows programmatic access

**Pipeline stops early**
- Check logs for failed collection stages
- Verify external API availability (HH, Telegram)
- Review environment variables

## Logs

Logs are written to `logs/` directory with timestamps. Configure log level via `LOG_LEVEL` env var:
```bash
LOG_LEVEL=DEBUG python -m pipelines.etl_pipeline
```

## Contributing

1. Create a feature branch
2. Make changes with tests
3. Verify tests pass: `pytest tests/`
4. Submit pull request

## License

MIT

## Support

For issues or questions, open an issue on GitHub or contact the maintainers.
