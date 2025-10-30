from prefect import flow, task, get_run_logger
import subprocess
from pathlib import Path
from datetime import datetime, timedelta, timezone
from prefect_aws import AwsCredentials
import os

@task(name="Run dbt build", retries=2)
def run_dbt_build() -> dict:
    """Run dbt build to materialize all models"""
    logger = get_run_logger()
    dbt_dir = Path(__file__).parent / "dbt"

    logger.info("Starting dbt build...")

    # Stream output in real-time
    process = subprocess.Popen(
        ["dbt", "build"],
        cwd=dbt_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    # Stream and log output line by line as it happens
    output_lines = []
    for line in process.stdout:
        line = line.rstrip()
        logger.info(line)
        output_lines.append(line)

    # Wait for process to complete
    process.wait()

    if process.returncode != 0:
        error_msg = f"dbt build failed with return code {process.returncode}"
        logger.error(error_msg)
        logger.error("Full output above ^^^")
        raise subprocess.CalledProcessError(
            process.returncode,
            ["dbt", "build"],
            output="\n".join(output_lines)
        )

    logger.info("dbt build completed successfully!")

    return {
        "stdout": "\n".join(output_lines),
        "returncode": process.returncode
    }

@task(name="Refresh Evidence sources")
def refresh_evidence_sources() -> str:
    """
    Run npm run sources to refresh Evidence source queries.
    """
    logger = get_run_logger()
    evidence_dir = Path(__file__).parent / "evidence"

    logger.info("Running npm run sources...")

    process = subprocess.Popen(
        ["npm", "run", "sources"],
        cwd=evidence_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    # Stream output
    output_lines = []
    for line in process.stdout:
        line = line.rstrip()
        logger.info(line)
        output_lines.append(line)

    process.wait()

    if process.returncode != 0:
        error_msg = f"npm run sources failed with return code {process.returncode}"
        logger.error(error_msg)
        raise subprocess.CalledProcessError(
            process.returncode,
            ["npm", "run", "sources"],
            output="\n".join(output_lines)
        )

    logger.info("Evidence sources refreshed successfully!")
    return "sources refreshed"

@task(name="Build Evidence")
def build_evidence() -> str:
    """
    Run npm run build to rebuild Evidence site.
    """
    logger = get_run_logger()
    evidence_dir = Path(__file__).parent / "evidence"

    logger.info("Running npm run build...")

    process = subprocess.Popen(
        ["npm", "run", "build"],
        cwd=evidence_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    # Stream output
    output_lines = []
    for line in process.stdout:
        line = line.rstrip()
        logger.info(line)
        output_lines.append(line)

    process.wait()

    if process.returncode != 0:
        error_msg = f"npm run build failed with return code {process.returncode}"
        logger.error(error_msg)
        raise subprocess.CalledProcessError(
            process.returncode,
            ["npm", "run", "build"],
            output="\n".join(output_lines)
        )

    logger.info("Evidence build completed successfully!")
    return "build completed"

@task(name="Deploy to R2", retries=2)
def deploy_to_r2(aws_credentials_block: str,
                 bucket_name: str = "ipfix-analytics") -> str:
    """
    Deploy Evidence build directory to Cloudflare R2 using rclone.
    Credentials are loaded from Prefect block and used to configure rclone on-the-fly.

    Args:
        aws_credentials_block: Name of the Prefect AwsCredentials block for R2 access
        bucket_name: Name of the R2 bucket (default: "ipfix-analytics")

    Returns:
        Status string
    """
    logger = get_run_logger()
    evidence_dir = Path(__file__).parent / "evidence"
    build_dir = evidence_dir / "build"

    if not build_dir.exists():
        raise FileNotFoundError(f"Build directory not found: {build_dir}")

    logger.info(f"Deploying {build_dir} to R2 bucket '{bucket_name}'...")

    # Load R2 credentials from Prefect block
    logger.info(f"Loading R2 credentials from block: {aws_credentials_block}")
    aws_credentials = AwsCredentials.load(aws_credentials_block)

    # Get endpoint configuration
    endpoint_url = None
    if aws_credentials.aws_client_parameters:
        client_params = aws_credentials.aws_client_parameters.model_dump()
        endpoint_url = client_params.get("endpoint_url")

    logger.info(f"R2 endpoint: {endpoint_url}")

    # Get credentials from block
    access_key_id = aws_credentials.aws_access_key_id
    secret_access_key = aws_credentials.aws_secret_access_key

    # Handle SecretStr objects if they are used
    if hasattr(access_key_id, 'get_secret_value'):
        access_key_id = access_key_id.get_secret_value()
    if hasattr(secret_access_key, 'get_secret_value'):
        secret_access_key = secret_access_key.get_secret_value()

    if not access_key_id or not secret_access_key:
        raise ValueError("Missing access key or secret key in credentials block")

    # Configure rclone via environment variables
    # This creates a temporary "r2" remote configuration for this process
    rclone_env = os.environ.copy()
    rclone_env['RCLONE_CONFIG_R2_TYPE'] = 's3'
    rclone_env['RCLONE_CONFIG_R2_PROVIDER'] = 'Cloudflare'
    rclone_env['RCLONE_CONFIG_R2_ACCESS_KEY_ID'] = access_key_id
    rclone_env['RCLONE_CONFIG_R2_SECRET_ACCESS_KEY'] = secret_access_key
    rclone_env['RCLONE_CONFIG_R2_ENDPOINT'] = endpoint_url
    rclone_env['RCLONE_CONFIG_R2_ACL'] = 'public-read'  # For public website hosting

    logger.info("Configured rclone with credentials from Prefect block")

    # Run rclone copy with the configured environment
    process = subprocess.Popen(
        [
            "rclone", "sync",
            "build/",
            f"r2:{bucket_name}",
            "-v",
            "--progress",
            "--stats", "10s",
            "--checksum"
        ],
        cwd=evidence_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=rclone_env
    )

    # Stream output
    output_lines = []
    for line in process.stdout:
        line = line.rstrip()
        logger.info(line)
        output_lines.append(line)

    process.wait()

    if process.returncode != 0:
        error_msg = f"rclone copy failed with return code {process.returncode}"
        logger.error(error_msg)
        raise subprocess.CalledProcessError(
            process.returncode,
            ["rclone", "copy"],
            output="\n".join(output_lines)
        )

    logger.info("Deployment to R2 completed successfully!")
    return "deployed to R2"

@task(name="Cleanup old bucket files", retries=1)
def cleanup_old_files(aws_credentials_block: str,
                      bucket_name: str = "ipfix",
                      prefix: str = "ipfix_",
                      retention_days: int = 5) -> dict:
    """
    Clean up parquet files older than retention_days from MinIO bucket.
    Only files matching the prefix pattern will be considered for deletion.

    Args:
        aws_credentials_block: Name of the Prefect AwsCredentials block to use
        bucket_name: Name of the S3/MinIO bucket (default: "ipfix")
        prefix: File prefix pattern to match (default: "ipfix_")
        retention_days: Number of days to retain files (default: 5)

    Returns:
        Dictionary with cleanup statistics
    """
    logger = get_run_logger()

    # Calculate cutoff date
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
    logger.info(f"Cleaning up files older than {cutoff_date.isoformat()} ({retention_days} days)")

    # Load credentials from Prefect block
    logger.info(f"Loading credentials from block: {aws_credentials_block}")
    aws_credentials = AwsCredentials.load(aws_credentials_block)

    # Get the endpoint URL from the credentials block
    # aws_client_parameters is a Pydantic model, convert to dict
    endpoint_url = None
    if aws_credentials.aws_client_parameters:
        client_params = aws_credentials.aws_client_parameters.model_dump()
        endpoint_url = client_params.get("endpoint_url")
    logger.info(f"Block endpoint: {endpoint_url}")
    logger.info(f"Block region: {aws_credentials.region_name}")

    # Initialize S3 client with credentials from block
    # We need to pass the endpoint_url explicitly to the client
    boto3_session = aws_credentials.get_boto3_session()
    s3_client = boto3_session.client(
        's3',
        endpoint_url=endpoint_url
    )

    # Log what boto3 is actually using
    logger.info(f"Boto3 client endpoint: {s3_client.meta.endpoint_url}")
    logger.info(f"Boto3 client region: {s3_client.meta.region_name}")

    try:
        # List all objects in bucket with the specified prefix
        logger.info(f"Listing objects in bucket '{bucket_name}' with prefix '{prefix}'...")
        response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=prefix)

        if 'Contents' not in response:
            logger.info(f"No files found with prefix '{prefix}' in bucket '{bucket_name}'")
            return {
                "files_checked": 0,
                "files_deleted": 0,
                "bytes_freed": 0,
                "retention_days": retention_days
            }

        files_to_delete = []
        total_size = 0

        # Check each file's modification date
        for obj in response['Contents']:
            file_key = obj['Key']
            last_modified = obj['LastModified']
            file_size = obj['Size']

            if last_modified < cutoff_date:
                files_to_delete.append(file_key)
                total_size += file_size
                logger.info(f"Marking for deletion: {file_key} (modified: {last_modified.isoformat()}, size: {file_size} bytes)")

        # Delete old files
        deleted_count = 0
        if files_to_delete:
            logger.info(f"Deleting {len(files_to_delete)} old file(s)...")
            for file_key in files_to_delete:
                try:
                    s3_client.delete_object(Bucket=bucket_name, Key=file_key)
                    logger.info(f"Deleted: {file_key}")
                    deleted_count += 1
                except Exception as e:
                    logger.error(f"Failed to delete {file_key}: {str(e)}")
        else:
            logger.info(f"No files older than {retention_days} days found. Nothing to delete.")

        result = {
            "files_checked": len(response['Contents']),
            "files_deleted": deleted_count,
            "bytes_freed": total_size,
            "retention_days": retention_days
        }

        logger.info(f"Cleanup completed: {deleted_count} files deleted, {total_size / (1024**2):.2f} MB freed")
        return result

    except Exception as e:
        logger.error(f"Error during bucket cleanup: {str(e)}")
        raise

@flow(name="IPFIX Analytics Pipeline", log_prints=True)
def ipfix_pipeline(retention_days: int = 5,
                   minio_credentials_block: str = "minio-ipfix-credentials",
                   r2_credentials_block: str = "r2-ipfix-analytics-credentials"):
    """
    Main pipeline that:
    1. Runs dbt build to materialize staging and mart models to DuckDB
    2. Refreshes Evidence sources (runs queries against updated DuckDB)
    3. Builds Evidence static site
    4. Deploys build to Cloudflare R2
    5. Cleans up old parquet files from MinIO bucket (only if all previous steps succeed)

    Args:
        retention_days: Number of days to retain parquet files in MinIO bucket (default: 5)
        minio_credentials_block: Name of the Prefect AwsCredentials block for MinIO access (default: "minio-ipfix-credentials")
        r2_credentials_block: Name of the Prefect AwsCredentials block for R2 access (default: "r2-ipfix-analytics-credentials")
    """

    print("Starting IPFIX Analytics Pipeline...")

    # Step 1: Run dbt build
    print("Step 1: Running dbt build...")
    dbt_result = run_dbt_build()
    print(f"dbt build completed with return code: {dbt_result['returncode']}")

    # Step 2: Refresh Evidence sources
    print("Step 2: Refreshing Evidence sources...")
    sources_status = refresh_evidence_sources()
    print(f"Evidence sources: {sources_status}")

    # Step 3: Build Evidence site
    print("Step 3: Building Evidence site...")
    build_status = build_evidence()
    print(f"Evidence build: {build_status}")

    # Step 4: Deploy to R2
    print("Step 4: Deploying to R2...")
    deploy_status = deploy_to_r2(aws_credentials_block=r2_credentials_block)
    print(f"R2 deployment: {deploy_status}")

    # Step 5: Cleanup old files from MinIO bucket
    print(f"Step 5: Cleaning up files older than {retention_days} days from MinIO bucket...")
    cleanup_result = cleanup_old_files(
        aws_credentials_block=minio_credentials_block,
        retention_days=retention_days
    )
    print(f"Cleanup completed: {cleanup_result['files_deleted']} files deleted, {cleanup_result['bytes_freed'] / (1024**2):.2f} MB freed")

    print("Pipeline completed successfully!")

    return {
        "dbt_status": "success",
        "evidence_sources": sources_status,
        "evidence_build": build_status,
        "r2_deploy": deploy_status,
        "cleanup": cleanup_result
    }


if __name__ == "__main__":
    ipfix_pipeline()
