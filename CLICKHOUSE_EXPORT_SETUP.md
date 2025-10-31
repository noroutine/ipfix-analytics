# ClickHouse IPFIX Export Pipeline Setup

This document describes how to set up and deploy the ClickHouse IPFIX export pipeline as a POC for deploying multiple Prefect pipelines to different work pools.

## Overview

The ClickHouse IPFIX export pipeline:
- **Dry Run Mode (Default)**: Safely counts rows without making any changes
- **Normal Mode**: Executes `scripts/ipfix-export.sql` against ClickHouse
  - Marks unexported IPFIX rows (sets `exported = 1`)
  - Exports marked rows directly to MinIO as Parquet with zstd compression
  - Deletes exported rows from ClickHouse (to manage storage)
- Runs every 5 minutes (configurable)
- Uses the same `minio_credentials_block` as the IPFIX pipeline
- Shares the same Docker image for simplified deployment

## How It Works

The pipeline uses ClickHouse's native S3 export functionality via the SQL script:
1. **Template Substitution**: Loads MinIO credentials from Prefect block and substitutes into SQL template
2. **SQL Execution**: Executes the multi-step SQL script that:
   - Counts and marks rows for export
   - Uses `INSERT INTO FUNCTION s3()` to write directly to MinIO
   - Deletes exported rows to prevent re-export and manage storage

This approach is more efficient than downloading data through Python, as ClickHouse writes directly to S3/MinIO.

## Prerequisites

1. **MinIO Credentials Block** (already exists): `minio-ipfix-credentials`
2. **ClickHouse Server**: Access to a ClickHouse instance with `playground.ipfix_raw_data` table
3. **Python Dependencies**: Added `clickhouse-connect` to `pyproject.toml`
4. **SQL Script**: `scripts/ipfix-export.sql` (included)

## Dry Run Mode (Safety Feature)

**By default, the pipeline runs in dry run mode** to prevent accidental data export or deletion.

### What Dry Run Does:
- ✅ Connects to ClickHouse
- ✅ Counts unexported rows (where `exported = 0`)
- ✅ Counts already exported rows (where `exported = 1`)
- ✅ Reports total row count
- ❌ Does NOT mark rows for export
- ❌ Does NOT export to MinIO
- ❌ Does NOT delete any data

### Output Example:
```
DRY RUN MODE - Counting rows only
Unexported rows (exported = 0): 1,234,567
Exported rows (exported = 1): 0
Total rows: 1,234,567
DRY RUN COMPLETE - No data was exported or deleted
Set dry_run=False to actually export and delete
```

### Disabling Dry Run:
Set `dry_run: false` in deployment parameters to actually export data. Only the production deployment has this enabled by default.

## Configuration

### 1. Update ClickHouse Connection Parameters

Edit the deployment parameters in `prefect.yaml` to match your ClickHouse instance:

```yaml
parameters:
  clickhouse_host: your-clickhouse-host.com
  clickhouse_port: 8123  # HTTP interface port (NOT 9000!)
  clickhouse_user: default
  clickhouse_password: "your-password"
  clickhouse_database: playground
  minio_credentials_block: minio-ipfix-credentials
  minio_bucket: ipfix
  sql_script_path: scripts/ipfix-export.sql
  dry_run: true  # Set to false to actually export
```

**Important**: Use port `8123` for the HTTP interface. Port `9000` is for the native protocol (clickhouse-client) and will not work with the Python `clickhouse-connect` library.

### 2. Customize the Export Logic

The export logic is defined in `scripts/ipfix-export.sql`. Key template variables that get substituted:
- `{{ s3_endpoint }}`: Extracted from MinIO credentials block
- `{{ s3_bucket }}`: From deployment parameter `minio_bucket`
- `{{ s3_access_key }}`: From MinIO credentials block
- `{{ s3_secret_key }}`: From MinIO credentials block

The SQL script exports from `playground.ipfix_raw_data` table. To customize:
- Edit the SQL script to change the export query, table, or logic
- Modify the file path pattern: currently `ipfix_decoded_YYYYMMDD_HHmmSS.parquet`
- Adjust the WHERE clause to change what gets exported

**SQL Script Requirements**:
- Each statement must end with a semicolon (`;`)
- Comments can be on their own line (starting with `--`) or inline (after `--`)
- Multi-line statements are supported (e.g., `ALTER TABLE ... UPDATE ...`)
- The parser strips all comments before execution
- The default `scripts/ipfix-export.sql` contains 11 statements (check logs for "Parsed N SQL statements")

## Deployment Options

The pipeline includes three deployment configurations:

### 1. Local Development (Dry Run)
```bash
prefect deploy --name clickhouse-export-local-dev
```
- **Dry run enabled by default** - only counts rows
- Runs on local process work pool
- No Docker required
- Perfect for testing connectivity and counting data

### 2. Docker Development (Dry Run)
```bash
prefect deploy --name clickhouse-export-docker-dev
```
- **Dry run enabled by default** - only counts rows
- Uses the same Docker image as IPFIX pipeline (`Dockerfile`)
- Runs on Docker work pool
- Tests containerized deployment safely

### 3. Production (Live Export)
```bash
prefect deploy --name clickhouse-export-production
```
- **Dry run DISABLED** - actually exports and deletes data
- Scheduled to run every 5 minutes (300 seconds)
- Runs on `bo01-runner-docker` work pool
- Full production deployment with real data operations

## Building the Docker Image

The pipeline uses the same Docker image as the IPFIX analytics pipeline (`Dockerfile`). This simplifies deployment and image management.

The shared image includes:
- Python 3.13-slim base image
- All required dependencies including `clickhouse-connect`
- Node.js, rclone, and dbt (used by IPFIX pipeline, available but not used by this pipeline)

The main Dockerfile is used for all deployments. No separate image needed.

## Testing the Pipeline

### Test Locally (Dry Run)
```bash
# This will only count rows, not export anything
python clickhouse_export_pipeline.py
```

### Test Locally (Live Mode)
```bash
# Edit clickhouse_export_pipeline.py and change the last line to:
# clickhouse_export_pipeline(dry_run=False)
python clickhouse_export_pipeline.py
```

### Run via Prefect (Dry Run)
```bash
prefect deployment run clickhouse-ipfix-export-pipeline/clickhouse-export-local-dev
```

### Run via Prefect (Live Mode)
```bash
# Override the dry_run parameter
prefect deployment run clickhouse-ipfix-export-pipeline/clickhouse-export-local-dev \
  --param dry_run=false
```

### Check Results
After running, check your MinIO bucket for the exported parquet files:
```bash
# Using mc (MinIO client)
mc ls myminio/ipfix/

# Files will be named: ipfix_decoded_YYYYMMDD_HHmmSS.parquet
```

Check ClickHouse to verify rows were exported and deleted:
```sql
-- Should show 0 rows marked for export
SELECT count(*) FROM playground.ipfix_raw_data WHERE exported = 1;

-- Should show only unexported rows
SELECT count(*) FROM playground.ipfix_raw_data WHERE exported = 0;
```

## Work Pool Configuration

The pipeline demonstrates deploying to different work pools:

1. **Local Process**: `ws-mac-00055-local-process`
   - Direct execution on the host machine
   - No containerization

2. **Docker (Dev)**: `ws-mac-00055-docker`
   - Containerized execution
   - Local Docker work pool

3. **Docker (Production)**: `bo01-runner-docker`
   - Remote Docker work pool
   - Production deployment

## Monitoring

View pipeline runs in the Prefect UI:
```
https://prefect.noroutine.me
```

Check logs for:
- ClickHouse connection status
- Export statistics (row count, file size)
- MinIO upload confirmation

## Troubleshooting

### Connection Issues

**Error: "Port 9000 is for clickhouse-client program"**
```
HTTP driver received HTTP status 400, server response:
Port 9000 is for clickhouse-client program
You must use port 8123 for HTTP.
```

**Solution**: Change `clickhouse_port` to `8123` in your deployment parameters.

ClickHouse has two main interfaces:
- **Port 9000**: Native TCP protocol (for `clickhouse-client` CLI)
- **Port 8123**: HTTP protocol (for Python libraries like `clickhouse-connect`)

This pipeline uses the Python `clickhouse-connect` library, which requires the HTTP interface on port 8123.

**Other Connection Issues:**
- Verify ClickHouse host is accessible from your network
- Check firewall rules allow port 8123
- Verify credentials are correct
- Test connection: `curl http://your-clickhouse-host:8123/ping`

### MinIO Upload Fails
- Confirm `minio_credentials_block` exists: `prefect block ls`
- Verify bucket exists in MinIO
- Check endpoint URL in credentials block

### SQL Parsing Errors

**Error: "Multi-statements are not allowed"**
```
Syntax error (Multi-statements are not allowed): failed at position...
```

**Cause**: The SQL parser failed to properly split statements, or inline comments weren't stripped correctly.

**Solution**:
1. Ensure each SQL statement ends with a semicolon (`;`)
2. Check that inline comments use `--` syntax
3. Multi-line statements (like `ALTER TABLE ... UPDATE ...`) should have the semicolon on the last line
4. Avoid putting SQL code in string literals that contains `--` (it will be treated as a comment)

**Debug**: The pipeline logs show "Parsed N SQL statements" - verify this matches the expected number of statements in your script.

### Docker Build Fails
- Ensure all files are present: `pyproject.toml`, `uv.lock`, `.python-version`
- Check that `clickhouse-connect` is in `pyproject.toml`

## File Structure

```
.
├── clickhouse_export_pipeline.py   # Pipeline code
├── Dockerfile                      # Shared Docker image (used by both pipelines)
├── prefect.yaml                    # Deployment configurations for both pipelines
├── pyproject.toml                  # Python dependencies (includes clickhouse-connect)
├── scripts/
│   └── ipfix-export.sql           # SQL script with template variables
└── CLICKHOUSE_EXPORT_SETUP.md     # This file
```

## Why Use One Image?

Using a single Docker image for both pipelines simplifies:
- **Image management**: Only one image to build, push, and maintain
- **Dependencies**: Shared Python packages (boto3, prefect, prefect-aws)
- **CI/CD**: Single build process for all pipelines
- **Storage**: No duplicate base layers

The extra dependencies (Node.js, dbt, rclone) from the IPFIX pipeline don't impact the ClickHouse export pipeline's execution.

## Safety Benefits of Dry Run Mode

The dry run mode provides several safety advantages:

1. **Test Connectivity**: Verify ClickHouse connection without risk
2. **Count Data**: See how many rows would be affected before exporting
3. **Validate Configuration**: Check that table and credentials work correctly
4. **Prevent Accidents**: Default-safe behavior prevents accidental data deletion
5. **Development Safety**: Dev deployments stay in dry run, only production exports

## Workflow Recommendation

1. **Start in Dry Run**: Always test with `dry_run=true` first
2. **Verify Counts**: Check that unexported row counts make sense
3. **Test Once Live**: Run once with `dry_run=false` manually
4. **Enable Scheduling**: Once verified, enable production deployment with schedule

## Next Steps

1. Update ClickHouse connection parameters in `prefect.yaml`
2. Test in dry run mode: `python clickhouse_export_pipeline.py`
3. Verify row counts look correct
4. Deploy: `prefect deploy --name clickhouse-export-local-dev`
5. Test one live export: `prefect deployment run ... --param dry_run=false`
6. Enable production: `prefect deploy --name clickhouse-export-production`
