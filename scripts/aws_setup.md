# AWS Setup Guide

Step-by-step instructions to provision the AWS services used by this pipeline.
Estimated cost at portfolio scale: **~$15–25/month** (mostly RDS t3.micro).

---

## 1. IAM — create a pipeline user

```bash
# Create the user
aws iam create-user --user-name job-market-pipeline

# Attach only the permissions needed (least privilege)
aws iam put-user-policy \
  --user-name job-market-pipeline \
  --policy-name PipelinePolicy \
  --policy-document file://scripts/iam_policy.json

# Generate access keys and store in GitHub Secrets
aws iam create-access-key --user-name job-market-pipeline
```

**iam_policy.json** — minimal permissions:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:GetObject", "s3:ListBucket"],
      "Resource": [
        "arn:aws:s3:::job-market-pipeline-raw",
        "arn:aws:s3:::job-market-pipeline-raw/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
      "Resource": "arn:aws:logs:*:*:log-group:/job-market-pipeline/*"
    }
  ]
}
```

---

## 2. S3 — create the bucket

```bash
# Create bucket (replace region as needed)
aws s3api create-bucket \
  --bucket job-market-pipeline-raw \
  --region eu-west-1 \
  --create-bucket-configuration LocationConstraint=eu-west-1

# Enable versioning (good practice)
aws s3api put-bucket-versioning \
  --bucket job-market-pipeline-raw \
  --versioning-configuration Status=Enabled

# Block all public access
aws s3api put-public-access-block \
  --bucket job-market-pipeline-raw \
  --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,\
    BlockPublicPolicy=true,RestrictPublicBuckets=true

# Enable default encryption
aws s3api put-bucket-encryption \
  --bucket job-market-pipeline-raw \
  --server-side-encryption-configuration \
    '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
```

**Expected folder structure after pipeline runs:**
```
s3://job-market-pipeline-raw/
├── raw/
│   ├── headhunter/2024/03/15/jobs_06-00-12.json
│   ├── djinni/2024/03/15/jobs_06-02-45.json
│   └── remoteok/2024/03/15/jobs_06-04-01.json
├── processed/
│   └── 2024/03/15/jobs_clean.parquet
└── reports/
    └── 2024-03-15/summary.json
```

---

## 3. RDS PostgreSQL — create the database

```bash
# Create subnet group (use your existing VPC subnets)
aws rds create-db-subnet-group \
  --db-subnet-group-name job-market-subnet-group \
  --db-subnet-group-description "Job Market Pipeline" \
  --subnet-ids subnet-xxxx subnet-yyyy

# Create RDS instance (t3.micro = free tier eligible)
aws rds create-db-instance \
  --db-instance-identifier jobmarket-db \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --engine-version 15 \
  --master-username pipeline_user \
  --master-user-password YOUR_PASSWORD \
  --allocated-storage 20 \
  --db-name jobmarket \
  --db-subnet-group-name job-market-subnet-group \
  --vpc-security-group-ids sg-xxxx \
  --backup-retention-period 7 \
  --no-publicly-accessible \
  --storage-encrypted

# Wait until available (~5 minutes)
aws rds wait db-instance-available --db-instance-identifier jobmarket-db

# Get the endpoint
aws rds describe-db-instances \
  --db-instance-identifier jobmarket-db \
  --query "DBInstances[0].Endpoint.Address"
```

Then run the schema:
```bash
psql -h YOUR_ENDPOINT -U pipeline_user -d jobmarket -f scripts/init_db.sql
```

---

## 4. CloudWatch — log group

```bash
aws logs create-log-group \
  --log-group-name /job-market-pipeline/etl \
  --region eu-west-1

# Retention: 30 days
aws logs put-retention-policy \
  --log-group-name /job-market-pipeline/etl \
  --retention-in-days 30
```

---

## 5. EventBridge — backup daily trigger (optional)

```bash
# Rule: trigger at 06:00 UTC daily
aws events put-rule \
  --name "JobMarketPipelineDailyTrigger" \
  --schedule-expression "cron(0 6 * * ? *)" \
  --state ENABLED \
  --description "Triggers job market ETL pipeline daily"
```

---

## Security checklist

- [ ] RDS is NOT publicly accessible (only reachable from pipeline VPC)
- [ ] S3 bucket has public access blocked
- [ ] IAM user has only S3 + CloudWatch Logs permissions (no admin)
- [ ] DB password stored in GitHub Secrets, never in code
- [ ] S3 encryption at rest enabled (AES256)
- [ ] RDS storage encryption enabled
- [ ] RDS automated backups enabled (7 days)
