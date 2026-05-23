"""
Manual test script for RDSLoader database connectivity.
Verifies that PostgreSQL connection works and basic queries execute successfully.
Useful for debugging database configuration issues without running full pipelines.
Run with: python -m pytest tests/test_rds_loader_connection.py -v -s
TODO: Consider converting this to an automated pytest-based integration test.
"""
from src.loaders.rds_loader import RDSLoader

loader = RDSLoader()

# Check connection
print("Health:", loader.health_check())

# Query all jobs
df = loader.load_for_analytics("SELECT COUNT(*) as total_jobs FROM jobs")
print(df)

# See sample data
df = loader.load_for_analytics("SELECT * FROM jobs LIMIT 5")
print(df)
