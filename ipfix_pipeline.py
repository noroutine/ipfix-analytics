from prefect import flow, task, get_run_logger
import subprocess
from pathlib import Path

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
def deploy_to_r2() -> str:
    """
    Deploy Evidence build directory to Cloudflare R2 using rclone.
    """
    logger = get_run_logger()
    evidence_dir = Path(__file__).parent / "evidence"
    build_dir = evidence_dir / "build"

    logger.info(f"Deploying {build_dir} to R2...")

    # rclone copy with good options:
    # -v = verbose output
    # --progress = show progress during transfer
    # --stats 10s = show stats every 10 seconds
    # --checksum = use checksums instead of mod-time & size
    # --exclude .DS_Store = skip macOS metadata files
    process = subprocess.Popen(
        [
            "rclone", "copy",
            "build/",
            "r2:ipfix-analytics",
            "-v",
            "--progress",
            "--stats", "10s",
            "--checksum",
            "--exclude", ".DS_Store"
        ],
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
        error_msg = f"rclone copy failed with return code {process.returncode}"
        logger.error(error_msg)
        raise subprocess.CalledProcessError(
            process.returncode,
            ["rclone", "copy"],
            output="\n".join(output_lines)
        )

    logger.info("Deployment to R2 completed successfully!")
    return "deployed to R2"

@flow(name="IPFIX Analytics Pipeline", log_prints=True)
def ipfix_pipeline():
    """
    Main pipeline that:
    1. Runs dbt build to materialize staging and mart models to DuckDB
    2. Refreshes Evidence sources (runs queries against updated DuckDB)
    3. Builds Evidence static site
    4. Deploys build to Cloudflare R2
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
    deploy_status = deploy_to_r2()
    print(f"R2 deployment: {deploy_status}")

    print("Pipeline completed successfully!")

    return {
        "dbt_status": "success",
        "evidence_sources": sources_status,
        "evidence_build": build_status,
        "r2_deploy": deploy_status
    }


if __name__ == "__main__":
    ipfix_pipeline()
