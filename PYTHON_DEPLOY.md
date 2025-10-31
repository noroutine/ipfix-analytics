# Python-Based Deployment Guide

This guide covers using the `deploy.py` script for programmatic Prefect deployments - a more flexible alternative to YAML for production environments.

## Why Python Deployments?

The `deploy.py` script provides advantages over `prefect.yaml`:

✅ **Dynamic Configuration** - Use environment variables and conditional logic
✅ **DRY Principle** - Share configuration across deployments with functions
✅ **Better Error Handling** - Detailed error messages and deployment summary
✅ **Programmatic Control** - Integrate with CI/CD and other tools
✅ **Type Safety** - Python IDE support and type checking

## Quick Start

### Deploy All Production Flows
```bash
# Build Docker image and deploy
python deploy.py

# See what would be deployed (no changes)
python deploy.py --dry-run
```

### Deploy Specific Flow
```bash
# ClickHouse export only
python deploy.py --flow clickhouse

# Analytics pipeline only
python deploy.py --flow analytics
```

### Skip Docker Build
```bash
# Use existing image
python deploy.py --skip-build

# Build image only, don't deploy
python deploy.py --build-only
```

## Environment Variables

The deployment script reads configuration from environment variables:

```bash
# ClickHouse settings
export CLICKHOUSE_HOST=10.1.7.12
export CLICKHOUSE_PORT=8123
export CLICKHOUSE_USER=default
export CLICKHOUSE_PASSWORD=""
export CLICKHOUSE_DATABASE=playground

# MinIO settings
export MINIO_BUCKET=ipfix

# Analytics settings
export RETENTION_DAYS=5

# Deploy with custom config
python deploy.py
```

## Deployment Features

### Automatic Docker Image Building

The script uses `scripts/build-ipfix-pipeline-image.sh` to build multi-architecture images:

```bash
$ python deploy.py

Building Docker image:
  Image: cr.nrtn.dev/sandbox/ipfix-pipeline-worker:abc1234
  Script: scripts/build-ipfix-pipeline-image.sh
  Platforms: linux/amd64, linux/arm64

Running scripts/build-ipfix-pipeline-image.sh...
================================================
Building Multi-Platform Docker Image
================================================
Image: cr.nrtn.dev/sandbox/ipfix-pipeline-worker
SHA: abc1234
Branch: master
Platforms: linux/amd64,linux/arm64
================================================
✓ Build and push successful

Deploying ClickHouse Export to production
  Commit: abc1234
  Image: cr.nrtn.dev/sandbox/ipfix-pipeline-worker:abc1234
  Schedule: Every 5 minutes
```

**Tags created automatically:**
- `{commit-sha}` - Git commit hash (e.g., `abc1234`)
- `{branch}` - Git branch name (e.g., `master`)
- `latest` - Latest build

**Multi-arch support:**
- `linux/amd64` - x86_64 architecture
- `linux/arm64` - ARM64 architecture (e.g., Apple Silicon, AWS Graviton)

### Production Tags

All production deployments are tagged for easy filtering:

- `production` - Production environment
- `clickhouse` / `analytics` - Service type
- `export` / `analytics` - Function
- `scheduled` - Has automatic schedule

Query by tags:
```bash
prefect deployment ls --tag production
```

### Dry Run Mode

Test deployment configuration without making changes:

```bash
$ python deploy.py --dry-run

Building Docker image:
  Image: cr.nrtn.dev/sandbox/ipfix-pipeline-worker:abc1234
  [DRY RUN] Would build and push but skipping...

Deploying ClickHouse Export to production
  Commit: abc1234
  Schedule: Every 5 minutes
  [DRY RUN] Would deploy but skipping...

[DRY RUN] No deployments were actually created
```

## Current Deployments

### ClickHouse IPFIX Export

**Function:** `deploy_clickhouse_export_production()`

- **Schedule:** Every 5 minutes (300 seconds)
- **Work Pool:** `bo01-runner-docker`
- **Mode:** Live export (dry_run=false)
- **Parameters:**
  - `clickhouse_host` - From `CLICKHOUSE_HOST` env var (default: "clickhouse")
  - `clickhouse_port` - From `CLICKHOUSE_PORT` env var (default: 8123)
  - `clickhouse_database` - From `CLICKHOUSE_DATABASE` env var (default: "playground")
  - `minio_bucket` - From `MINIO_BUCKET` env var (default: "ipfix")
  - `dry_run` - false (production exports and deletes data)

### IPFIX Analytics Pipeline

**Function:** `deploy_ipfix_analytics_production()`

- **Schedule:** Every hour (3600 seconds)
- **Work Pool:** `bo01-runner-docker`
- **Components:** dbt, Evidence, R2 deployment
- **Parameters:**
  - `retention_days` - From `RETENTION_DAYS` env var (default: 5)
  - `minio_credentials_block` - "minio-ipfix-credentials"
  - `r2_credentials_block` - "r2-ipfix-analytics-credentials"

## Adding New Deployments

To add a new production deployment:

### 1. Define Deployment Function

```python
def deploy_my_new_flow_production(dry_run: bool = False) -> Optional[str]:
    """Deploy my new flow to production."""
    from my_module import my_flow_function

    commit_hash = get_git_commit_hash()
    image_name = get_docker_image_name(commit_hash)

    print(f"Deploying My New Flow to production")
    print(f"  Commit: {commit_hash}")

    if dry_run:
        print("  [DRY RUN] Would deploy but skipping...")
        return None

    # Prefect 3.x API: use flow.deploy() directly
    deployment_id = my_flow_function.deploy(
        name="my-new-flow-production",
        version=commit_hash,
        description="My new flow for production",
        tags=["production", "my-flow", "scheduled"],
        work_pool_name="bo01-runner-docker",
        job_variables={"image": image_name},
        parameters={
            "param1": os.getenv("PARAM1", "default"),
            "param2": int(os.getenv("PARAM2", "100"))
        },
        cron="*/10 * * * *",  # Every 10 minutes
        paused=False,
        enforce_parameter_schema=True
    )

    print(f"✓ Deployed: {deployment_id}")
    return str(deployment_id)
```

### 2. Register in Deployment Registry

```python
DEPLOYMENTS = {
    "clickhouse": deploy_clickhouse_export_production,
    "analytics": deploy_ipfix_analytics_production,
    "my-flow": deploy_my_new_flow_production,  # Add here
}
```

### 3. Deploy

```bash
python deploy.py --flow my-flow
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Deploy to Production

on:
  push:
    branches: [master]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.13'

      - name: Install dependencies
        run: |
          pip install prefect prefect-aws

      - name: Build and Deploy
        env:
          CLICKHOUSE_HOST: ${{ secrets.CLICKHOUSE_HOST }}
          CLICKHOUSE_PORT: 8123
          PREFECT_API_URL: ${{ secrets.PREFECT_API_URL }}
          PREFECT_API_KEY: ${{ secrets.PREFECT_API_KEY }}
        run: |
          python deploy.py
```

### GitLab CI Example

```yaml
deploy:production:
  stage: deploy
  script:
    - pip install -r requirements.txt
    - python deploy.py
  only:
    - master
  environment:
    name: production
  variables:
    PREFECT_API_URL: $PREFECT_API_URL
    PREFECT_API_KEY: $PREFECT_API_KEY
```

## Comparison with YAML

| Feature | YAML (prefect.yaml) | Python (deploy.py) |
|---------|---------------------|-------------------|
| Dynamic config | ❌ Limited | ✅ Full Python |
| Environment vars | ❌ Template syntax | ✅ Native os.getenv() |
| Conditional logic | ❌ No | ✅ Yes |
| Error handling | ❌ Basic | ✅ Comprehensive |
| Shared config | ❌ Copy-paste | ✅ Functions |
| Version control | ✅ Easy | ✅ Easy |
| Learning curve | ✅ Simpler | ❌ More complex |

**Recommendation:**
- Use **Python** for production deployments
- Use **YAML** for local dev and testing
- Keep both in sync for consistency

## Troubleshooting

### ImportError when deploying

```
ImportError: No module named 'my_flow'
```

**Fix:** Ensure the flow module is in your git repository and the deployment pull step clones it correctly.

### Docker image not found

```bash
# Build image using Python script
python deploy.py --build-only

# Or call the build script directly
bash scripts/build-ipfix-pipeline-image.sh

# Or build with custom tag
bash scripts/build-ipfix-pipeline-image.sh custom-tag
```

### Work pool doesn't exist

```bash
# List work pools
prefect work-pool ls

# Create if missing
prefect work-pool create bo01-runner-docker --type docker
```

### Deployment not showing in UI

```bash
# Check if created
prefect deployment ls

# Inspect specific deployment
prefect deployment inspect clickhouse-export-pipeline/clickhouse-export-production
```

## Best Practices

1. **Always test with --dry-run first**
   ```bash
   python deploy.py --dry-run
   ```

2. **Use environment variables for secrets**
   ```bash
   export CLICKHOUSE_PASSWORD=$(cat /path/to/secret)
   python deploy.py
   ```

3. **Tag deployments consistently**
   - Use `production` tag for all prod deployments
   - Add service-specific tags (`clickhouse`, `analytics`)
   - Include function tags (`export`, `scheduled`)

4. **Version Docker images with git hash**
   - Already done automatically by `deploy.py` and the build script
   - Multi-arch images (amd64/arm64) built automatically
   - Makes rollback easy with git SHA tags

5. **Test locally before deploying**
   ```bash
   # Run flow locally first
   python clickhouse_export_pipeline.py

   # Then deploy
   python deploy.py --flow clickhouse
   ```

## Next Steps

- Set up CI/CD pipeline using deploy.py
- Configure environment-specific settings
- Add monitoring and alerting
- Set up deployment rollback strategy
