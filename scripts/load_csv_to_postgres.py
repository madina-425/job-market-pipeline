# scripts/load_csv_to_postgres.py

import pandas as pd
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()

# ── Configuration ─────────────────────────────────────────────────────────
CSV_PATH = "all_jobs_clean.csv"
DB_USER = os.getenv("DB_USER", "pipeline_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "devpassword")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "jobmarket")

DB_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# ── Load and Display ──────────────────────────────────────────────────────
print(f"📖 Reading {CSV_PATH}...")
df = pd.read_csv(CSV_PATH)

print(f"\n📊 Shape: {df.shape[0]} rows × {df.shape[1]} columns")
print(f"\n📋 Columns:\n{df.dtypes}")
print(f"\n🔍 First 2 rows:")
print(df.head(2))

# ── Upload to PostgreSQL ──────────────────────────────────────────────────
print(f"\n🚀 Connecting to {DB_URL}...")
try:
    engine = create_engine(DB_URL)
    
    # Test connection
    with engine.connect() as conn:
        result = conn.execute(text("SELECT version();"))
        print(f"✅ Connected: {result.scalar()}\n")
    
    # Load data
    print("⏳ Loading data into jobs table...")
    df.to_sql("jobs", engine, if_exists="append", index=False)
    print(f"✅ Successfully loaded {len(df)} rows into jobs table!\n")
    
    # Verify
    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM jobs;")).scalar()
        print(f"📈 Total jobs in database: {count}")
    
    engine.dispose()
    
except Exception as e:
    print(f"❌ Error: {e}")
    raise