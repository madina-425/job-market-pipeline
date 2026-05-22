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