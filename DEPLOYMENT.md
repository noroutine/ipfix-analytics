# Prefect Deployment Setup

for future me:

```bash
./scripts/build-ipfix-pipeline-image.sh
uv run prefect deploy --all
```


## Overview
This document describes how to deploy the IPFIX Analytics Pipeline to a non-local Prefect worker pool using git-based deployment.

## Configuration

### 1. Git Repository
The deployment fetches code from:
```
ssh://git@nrtn.dev/noroutine/ipfix-analytics.git
```

### 2. Required Secrets and Environment Variables

#### SSH Key for Git Clone
The worker needs SSH access to clone the repository. You have two options:

**Option A: Use Prefect Secret Block**
```bash
# Create a secret block for your SSH private key
prefect block register -m prefect_aws  # or appropriate module

# In Prefect UI, create a Secret block named "git-ssh-key" with your SSH private key
```

Then update `prefect.yaml` pull section:
```yaml
pull:
- prefect.deployments.steps.git_clone:
    repository: ssh://git@nrtn.dev/noroutine/ipfix-analytics.git
    branch: master
    credentials: "{{ prefect.blocks.secret.git-ssh-key }}"
```

**Option B: Configure SSH on Worker**
Ensure the worker machine has:
- SSH key in `~/.ssh/id_rsa` (or similar)
- Correct permissions: `chmod 600 ~/.ssh/id_rsa`
- Host added to known_hosts: `ssh-keyscan nrtn.dev >> ~/.ssh/known_hosts`

#### Rclone Configuration for R2
The pipeline uses rclone to deploy to Cloudflare R2. Configure rclone on the worker:

**Option A: Environment Variables**
```bash
export RCLONE_CONFIG_R2_TYPE=s3
export RCLONE_CONFIG_R2_PROVIDER=Cloudflare
export RCLONE_CONFIG_R2_ACCESS_KEY_ID=<your-r2-access-key>
export RCLONE_CONFIG_R2_SECRET_ACCESS_KEY=<your-r2-secret-key>
export RCLONE_CONFIG_R2_ENDPOINT=<your-account-id>.r2.cloudflarestorage.com
export RCLONE_CONFIG_R2_ACL=private
```

**Option B: Create rclone.conf on Worker**
Place this at `~/.config/rclone/rclone.conf`:
```ini
[r2]
type = s3
provider = Cloudflare
access_key_id = <your-r2-access-key>
secret_access_key = <your-r2-secret-key>
endpoint = <your-account-id>.r2.cloudflarestorage.com
acl = private
```

**Option C: Use Prefect Variables/Blocks**
You can create a custom initialization step in `prefect.yaml`:

```yaml
pull:
- prefect.deployments.steps.git_clone:
    repository: ssh://git@nrtn.dev/noroutine/ipfix-analytics.git
    branch: master
- prefect.deployments.steps.run_shell_script:
    script: |
      mkdir -p ~/.config/rclone
      cat > ~/.config/rclone/rclone.conf << EOF
      [r2]
      type = s3
      provider = Cloudflare
      access_key_id = {{ prefect.variables.r2_access_key }}
      secret_access_key = {{ prefect.variables.r2_secret_key }}
      endpoint = {{ prefect.variables.r2_endpoint }}
      acl = private
      EOF
```

Then create Prefect variables:
```bash
prefect variable set r2_access_key "your-access-key"
prefect variable set r2_secret_key "your-secret-key"
prefect variable set r2_endpoint "your-account-id.r2.cloudflarestorage.com"
```

### 3. Worker Environment Requirements

The worker must have these tools installed:
- Python 3.x with prefect
- dbt-core with dbt-duckdb
- Node.js and npm
- rclone

## Deployment Steps

### 1. Create a Work Pool
```bash
# Create a process-based work pool (or use Docker/Kubernetes)
prefect work-pool create default --type process
```

### 2. Deploy the Flow
```bash
# From the project directory
prefect deploy --all

# Or deploy specific deployment
prefect deploy -n ipfix-analytics-deployment
```

### 3. Start a Worker
On your worker machine:
```bash
# Start a worker that polls the work pool
prefect worker start --pool default
```

### 4. Run the Deployment
```bash
# Trigger a flow run
prefect deployment run 'IPFIX Analytics Pipeline/ipfix-analytics-deployment'
```

## Updating the Deployment

After making changes to the code:
1. Commit and push to git
2. The next flow run will automatically fetch the latest code
3. No need to redeploy unless you change `prefect.yaml`

## Scheduling

To add a schedule, update the deployment in `prefect.yaml`:
```yaml
deployments:
- name: ipfix-analytics-deployment
  # ... other fields ...
  schedule:
    cron: "0 2 * * *"  # Run daily at 2 AM
    timezone: "UTC"
```

Then redeploy:
```bash
prefect deploy --all
```
