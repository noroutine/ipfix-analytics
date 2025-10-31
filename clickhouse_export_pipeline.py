from prefect import flow, task, get_run_logger
from prefect_aws import AwsCredentials
from pathlib import Path
import clickhouse_connect


@task(name="Execute IPFIX Export Script", retries=2)
def execute_ipfix_export_script(
    clickhouse_host: str,
    clickhouse_port: int,  # Should be 8123 for HTTP interface
    clickhouse_user: str,
    clickhouse_password: str,
    clickhouse_database: str,
    minio_credentials_block: str,
    minio_bucket: str,
    sql_script_path: str = "scripts/ipfix-export.sql",
    dry_run: bool = True
) -> dict:
    """
    Execute the IPFIX export SQL script against ClickHouse.

    In dry_run mode (default), only counts rows without exporting or deleting.
    In normal mode, the script marks rows for export, exports to S3/MinIO, and deletes exported rows.

    Note: Uses the ClickHouse HTTP interface (port 8123), not the native protocol (port 9000).

    Args:
        clickhouse_host: ClickHouse server hostname
        clickhouse_port: ClickHouse HTTP interface port (must be 8123 for HTTP, not 9000)
        clickhouse_user: ClickHouse username
        clickhouse_password: ClickHouse password
        clickhouse_database: ClickHouse database name
        minio_credentials_block: Name of the Prefect AwsCredentials block for MinIO access
        minio_bucket: MinIO bucket name
        sql_script_path: Path to SQL script file
        dry_run: If True, only count rows without exporting or deleting (default: True)

    Returns:
        Dictionary with execution statistics
    """
    logger = get_run_logger()

    logger.info(f"DRY RUN MODE: {'ENABLED - will only count rows' if dry_run else 'DISABLED - will export and delete'}")

    # Load MinIO credentials to get template variables
    logger.info(f"Loading MinIO credentials from block: {minio_credentials_block}")
    minio_creds = AwsCredentials.load(minio_credentials_block)

    # Get endpoint URL
    endpoint_url = None
    if minio_creds.aws_client_parameters:
        client_params = minio_creds.aws_client_parameters.model_dump()
        endpoint_url = client_params.get("endpoint_url")

    # Extract credentials
    access_key_id = minio_creds.aws_access_key_id
    secret_access_key = minio_creds.aws_secret_access_key

    # Handle SecretStr objects
    if hasattr(access_key_id, 'get_secret_value'):
        access_key_id = access_key_id.get_secret_value()
    if hasattr(secret_access_key, 'get_secret_value'):
        secret_access_key = secret_access_key.get_secret_value()

    # Strip protocol from endpoint for S3 URL
    s3_endpoint = endpoint_url.replace('https://', '').replace('http://', '')

    logger.info(f"S3 endpoint: {s3_endpoint}")
    logger.info(f"S3 bucket: {minio_bucket}")

    # Read SQL script
    script_path = Path(__file__).parent / sql_script_path
    logger.info(f"Reading SQL script from {script_path}")

    with open(script_path, 'r') as f:
        sql_template = f.read()

    # Replace template variables
    sql_script = sql_template.replace('{{ s3_endpoint }}', s3_endpoint)
    sql_script = sql_script.replace('{{ s3_bucket }}', minio_bucket)
    sql_script = sql_script.replace('{{ s3_access_key }}', access_key_id)
    sql_script = sql_script.replace('{{ s3_secret_key }}', secret_access_key)

    logger.info(f"Template variables substituted")

    # Connect to ClickHouse
    logger.info(f"Connecting to ClickHouse at {clickhouse_host}:{clickhouse_port}")
    client = clickhouse_connect.get_client(
        host=clickhouse_host,
        port=clickhouse_port,
        username=clickhouse_user,
        password=clickhouse_password,
        database=clickhouse_database
    )

    try:
        # Dry run mode: just count rows
        if dry_run:
            logger.info("=" * 60)
            logger.info("DRY RUN MODE - Counting rows only")
            logger.info("=" * 60)

            # Count unexported rows
            count_query = "SELECT count(*) as cnt FROM playground.ipfix_raw_data WHERE exported = 0"
            result = client.query(count_query)
            unexported_count = result.result_rows[0][0] if result.result_rows else 0

            logger.info(f"Unexported rows (exported = 0): {unexported_count:,}")

            # Count already exported rows
            exported_query = "SELECT count(*) as cnt FROM playground.ipfix_raw_data WHERE exported = 1"
            result = client.query(exported_query)
            exported_count = result.result_rows[0][0] if result.result_rows else 0

            logger.info(f"Exported rows (exported = 1): {exported_count:,}")

            # Total count
            total_query = "SELECT count(*) as cnt FROM playground.ipfix_raw_data"
            result = client.query(total_query)
            total_count = result.result_rows[0][0] if result.result_rows else 0

            logger.info(f"Total rows: {total_count:,}")

            logger.info("=" * 60)
            logger.info("DRY RUN COMPLETE - No data was exported or deleted")
            logger.info("Set dry_run=False to actually export and delete")
            logger.info("=" * 60)

            return {
                "dry_run": True,
                "unexported_rows": unexported_count,
                "exported_rows": exported_count,
                "total_rows": total_count,
                "statements_executed": 0
            }

        # Normal mode: execute the full script
        logger.info("=" * 60)
        logger.info("NORMAL MODE - Executing export script")
        logger.info("=" * 60)

        # Split script into individual statements
        # Handle inline comments and multi-line statements properly
        statements = []
        current_statement = []

        for line in sql_script.split('\n'):
            # Strip inline comments (anything after -- on the same line)
            if '--' in line:
                # Split on first occurrence of --
                line_parts = line.split('--', 1)
                line = line_parts[0]

            # Skip empty lines or pure comment lines
            if not line.strip():
                continue

            current_statement.append(line)

            # Check if line ends with semicolon (end of statement)
            if line.rstrip().endswith(';'):
                statement = '\n'.join(current_statement).strip()
                if statement:
                    statements.append(statement)
                current_statement = []

        # Handle any remaining statement without semicolon
        if current_statement:
            statement = '\n'.join(current_statement).strip()
            if statement:
                statements.append(statement)

        # Execute each statement
        logger.info(f"Parsed {len(statements)} SQL statements from script")
        results = []

        for i, statement in enumerate(statements, 1):
            logger.info(f"\nExecuting statement {i}/{len(statements)}")
            logger.info(f"Preview: {statement[:150]}...")

            try:
                result = client.command(statement)
                logger.info(f"✓ Statement {i} completed successfully")

                results.append({
                    "statement_number": i,
                    "preview": statement[:100],
                    "result": str(result) if result else None,
                    "status": "success"
                })
            except Exception as e:
                logger.error(f"✗ Statement {i} failed: {str(e)}")
                logger.error(f"Full statement:\n{statement}")
                raise

        logger.info(f"\n{'='*60}")
        logger.info(f"All {len(statements)} statements executed successfully")
        logger.info(f"{'='*60}")

        return {
            "dry_run": False,
            "statements_executed": len(statements),
            "results": results
        }

    finally:
        client.close()


@flow(name="ClickHouse IPFIX Export", log_prints=True)
def clickhouse_export_pipeline(
    clickhouse_host: str = "localhost",
    clickhouse_port: int = 8123,  # HTTP interface port (NOT 9000!)
    clickhouse_user: str = "default",
    clickhouse_password: str = "",
    clickhouse_database: str = "playground",
    minio_credentials_block: str = "minio-ipfix-credentials",
    minio_bucket: str = "ipfix",
    sql_script_path: str = "scripts/ipfix-export.sql",
    dry_run: bool = True
):
    """
    Export IPFIX data from ClickHouse to MinIO using the ipfix-export.sql script.

    In dry_run mode (default), only counts rows without exporting or deleting.
    In normal mode, the script:
    1. Marks unexported rows for export (exported = 1)
    2. Exports marked rows to S3/MinIO as parquet with zstd compression
    3. Deletes exported rows from ClickHouse

    Runs every 5 minutes to export new IPFIX data.

    Args:
        clickhouse_host: ClickHouse server hostname (default: localhost)
        clickhouse_port: ClickHouse HTTP interface port (default: 8123, NOT 9000!)
        clickhouse_user: ClickHouse username (default: default)
        clickhouse_password: ClickHouse password (default: empty)
        clickhouse_database: ClickHouse database name (default: playground)
        minio_credentials_block: Name of the Prefect AwsCredentials block for MinIO access
        minio_bucket: MinIO bucket name (default: ipfix)
        sql_script_path: Path to SQL script file (default: scripts/ipfix-export.sql)
        dry_run: If True, only count rows without exporting or deleting (default: True)
    """

    print("Starting ClickHouse IPFIX Export Pipeline...")
    print(f"Database: {clickhouse_database}")
    print(f"MinIO Bucket: {minio_bucket}")
    print(f"SQL Script: {sql_script_path}")
    print(f"Dry Run: {dry_run}")

    # Execute the IPFIX export script
    if dry_run:
        print("\n⚠️  DRY RUN MODE - Will only count rows, no export/delete")
    else:
        print("\n⚡ NORMAL MODE - Will export and delete rows")

    result = execute_ipfix_export_script(
        clickhouse_host=clickhouse_host,
        clickhouse_port=clickhouse_port,
        clickhouse_user=clickhouse_user,
        clickhouse_password=clickhouse_password,
        clickhouse_database=clickhouse_database,
        minio_credentials_block=minio_credentials_block,
        minio_bucket=minio_bucket,
        sql_script_path=sql_script_path,
        dry_run=dry_run
    )

    # Print results based on mode
    if result.get('dry_run'):
        print(f"\nDry run results:")
        print(f"  Unexported rows: {result['unexported_rows']:,}")
        print(f"  Already exported: {result['exported_rows']:,}")
        print(f"  Total rows: {result['total_rows']:,}")
        print(f"\n💡 To actually export data, set dry_run=False in deployment parameters")
    else:
        print(f"\n{result['statements_executed']} SQL statements executed successfully")

        # Print results from each statement
        if 'results' in result:
            for stmt_result in result['results']:
                if stmt_result['result']:
                    print(f"Statement {stmt_result['statement_number']}: {stmt_result['result']}")

    print("\n" + "="*60)
    print("Pipeline completed successfully!")
    print("="*60)

    return result


if __name__ == "__main__":
    clickhouse_export_pipeline()
