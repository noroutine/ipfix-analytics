#!/usr/bin/env python3
"""
Production deployment script for Prefect flows.

This script provides a Python-based alternative to prefect.yaml for more complex
deployment scenarios. It supports:
- Programmatic deployment configuration
- Dynamic parameter generation
- Conditional deployment logic
- Tag-based filtering
- Environment-specific settings

Usage:
    python deploy.py                          # Deploy all production flows
    python deploy.py --flow clickhouse        # Deploy specific flow
    python deploy.py --all                    # Deploy all flows (including dev)
    python deploy.py --dry-run                # Show what would be deployed
"""

import argparse
import os
import subprocess
from typing import Optional
from prefect.deployments import Deployment
from prefect.server.schemas.schedules import IntervalSchedule
from datetime import timedelta


def get_git_commit_hash() -> str:
    """Get current git commit hash (short form)."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return "latest"


def get_docker_image_name(commit_hash: str) -> str:
    """Generate Docker image name with commit hash tag."""
    return f"cr.nrtn.dev/sandbox/ipfix-pipeline-worker:{commit_hash}"


def deploy_clickhouse_export_production(dry_run: bool = False) -> Optional[str]:
    """
    Deploy ClickHouse IPFIX export pipeline to production.

    This deployment:
    - Runs every 5 minutes
    - Actually exports and deletes data (dry_run=false)
    - Uses Docker work pool for isolation
    - Auto-builds and tags Docker image

    Args:
        dry_run: If True, only show what would be deployed

    Returns:
        Deployment ID if successful, None if dry_run
    """
    from clickhouse_export_pipeline import clickhouse_export_pipeline

    commit_hash = get_git_commit_hash()
    image_name = get_docker_image_name(commit_hash)

    print(f"Deploying ClickHouse Export to production")
    print(f"  Commit: {commit_hash}")
    print(f"  Image: {image_name}")
    print(f"  Schedule: Every 5 minutes")
    print(f"  Dry run: disabled (LIVE mode)")

    if dry_run:
        print("  [DRY RUN] Would deploy but skipping...")
        return None

    deployment = Deployment.build_from_flow(
        flow=clickhouse_export_pipeline,
        name="clickhouse-export-production",
        version=commit_hash,
        description="ClickHouse IPFIX Export Pipeline - exports IPFIX data to MinIO parquet every 5 minutes (LIVE)",
        tags=["production", "clickhouse", "export", "scheduled"],
        work_pool_name="bo01-runner-docker",
        work_queue_name=None,
        parameters={
            "clickhouse_host": os.getenv("CLICKHOUSE_HOST", "clickhouse"),
            "clickhouse_port": int(os.getenv("CLICKHOUSE_PORT", "8123")),
            "clickhouse_user": os.getenv("CLICKHOUSE_USER", "default"),
            "clickhouse_password": os.getenv("CLICKHOUSE_PASSWORD", ""),
            "clickhouse_database": os.getenv("CLICKHOUSE_DATABASE", "playground"),
            "minio_credentials_block": "minio-ipfix-credentials",
            "minio_bucket": os.getenv("MINIO_BUCKET", "ipfix"),
            "sql_script_path": "scripts/ipfix-export.sql",
            "dry_run": False  # Production mode - actually exports and deletes
        },
        schedule=IntervalSchedule(interval=timedelta(seconds=300)),  # 5 minutes
        # Build step would go here if using build_from_flow with docker
        # For now, assume image is pre-built
        job_variables={
            "image": image_name
        },
        pull=[
            {
                "prefect.deployments.steps.run_shell_script": {
                    "script": "python /scripts/setup-ssh.py"
                }
            },
            {
                "prefect.deployments.steps.git_clone": {
                    "id": "clone",
                    "repository": "ssh://git@nrtn.dev/noroutine/ipfix-analytics.git",
                    "branch": "master"
                }
            }
        ]
    )

    deployment_id = deployment.apply()
    print(f"✓ Deployed: {deployment_id}")
    return deployment_id


def deploy_ipfix_analytics_production(dry_run: bool = False) -> Optional[str]:
    """
    Deploy IPFIX Analytics pipeline to production.

    This deployment:
    - Runs every hour
    - Processes dbt, Evidence, and deploys to R2
    - Uses Docker work pool
    - Auto-builds and tags Docker image

    Args:
        dry_run: If True, only show what would be deployed

    Returns:
        Deployment ID if successful, None if dry_run
    """
    from ipfix_pipeline import ipfix_pipeline

    commit_hash = get_git_commit_hash()
    image_name = get_docker_image_name(commit_hash)

    print(f"Deploying IPFIX Analytics to production")
    print(f"  Commit: {commit_hash}")
    print(f"  Image: {image_name}")
    print(f"  Schedule: Every hour")
    print(f"  Retention: 5 days")

    if dry_run:
        print("  [DRY RUN] Would deploy but skipping...")
        return None

    deployment = Deployment.build_from_flow(
        flow=ipfix_pipeline,
        name="ipfix-analytics-production",
        version=commit_hash,
        description="IPFIX Analytics Pipeline - dbt, Evidence, and R2 deployment (production)",
        tags=["production", "analytics", "dbt", "evidence", "scheduled"],
        work_pool_name="bo01-runner-docker",
        work_queue_name=None,
        parameters={
            "retention_days": int(os.getenv("RETENTION_DAYS", "5")),
            "minio_credentials_block": "minio-ipfix-credentials",
            "r2_credentials_block": "r2-ipfix-analytics-credentials"
        },
        schedule=IntervalSchedule(interval=timedelta(seconds=3600)),  # 1 hour
        job_variables={
            "image": image_name
        },
        pull=[
            {
                "prefect.deployments.steps.run_shell_script": {
                    "script": "python /scripts/setup-ssh.py"
                }
            },
            {
                "prefect.deployments.steps.git_clone": {
                    "id": "clone",
                    "repository": "ssh://git@nrtn.dev/noroutine/ipfix-analytics.git",
                    "branch": "master"
                }
            }
        ]
    )

    deployment_id = deployment.apply()
    print(f"✓ Deployed: {deployment_id}")
    return deployment_id


def build_docker_image(dry_run: bool = False) -> str:
    """
    Build and push Docker image for deployments using the build script.

    Uses scripts/build-ipfix-pipeline-image.sh which builds multi-arch images
    (linux/amd64, linux/arm64) and pushes to the registry.

    Args:
        dry_run: If True, only show what would be built

    Returns:
        Image name with tag
    """
    commit_hash = get_git_commit_hash()
    image_name = get_docker_image_name(commit_hash)

    print(f"\nBuilding Docker image:")
    print(f"  Image: {image_name}")
    print(f"  Script: scripts/build-ipfix-pipeline-image.sh")
    print(f"  Platforms: linux/amd64, linux/arm64")

    if dry_run:
        print("  [DRY RUN] Would build and push but skipping...")
        return image_name

    # Call the build script
    # The script builds with git SHA by default, and we can pass custom tag if needed
    build_script = "scripts/build-ipfix-pipeline-image.sh"

    print(f"\n  Running {build_script}...")

    try:
        # Run the build script - it handles everything
        subprocess.run(
            ["bash", build_script],
            check=True,
            cwd="."
        )
        print("  ✓ Build and push successful")
        return image_name
    except subprocess.CalledProcessError as e:
        print(f"  ✗ Build failed: {e}")
        raise


# Deployment registry - maps flow names to deployment functions
DEPLOYMENTS = {
    "clickhouse": deploy_clickhouse_export_production,
    "analytics": deploy_ipfix_analytics_production,
}


def main():
    parser = argparse.ArgumentParser(
        description="Deploy Prefect flows to production",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        "--flow",
        choices=list(DEPLOYMENTS.keys()),
        help="Deploy specific flow (default: all production flows)"
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Deploy all flows including dev (not just production)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deployed without actually deploying"
    )

    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip Docker image build (assume image already exists)"
    )

    parser.add_argument(
        "--build-only",
        action="store_true",
        help="Only build Docker image, don't deploy"
    )

    args = parser.parse_args()

    print("="*60)
    print("Prefect Production Deployment Script")
    print("="*60)

    # Build Docker image first (unless skipped)
    if not args.skip_build:
        try:
            image_name = build_docker_image(dry_run=args.dry_run)

            if args.build_only:
                print("\n" + "="*60)
                print("Build complete. Skipping deployment (--build-only)")
                print("="*60)
                return

        except Exception as e:
            print(f"\nDocker build failed: {e}")
            print("Use --skip-build to deploy without building")
            return 1

    # Determine which flows to deploy
    if args.flow:
        flows_to_deploy = [args.flow]
        print(f"\nDeploying specific flow: {args.flow}")
    else:
        flows_to_deploy = list(DEPLOYMENTS.keys())
        print(f"\nDeploying all production flows: {', '.join(flows_to_deploy)}")

    # Deploy flows
    print("\n" + "="*60)
    print("Deploying Flows")
    print("="*60 + "\n")

    deployed = []
    failed = []

    for flow_name in flows_to_deploy:
        deploy_func = DEPLOYMENTS[flow_name]

        try:
            deployment_id = deploy_func(dry_run=args.dry_run)
            if deployment_id or args.dry_run:
                deployed.append(flow_name)
        except Exception as e:
            print(f"✗ Failed to deploy {flow_name}: {e}")
            failed.append(flow_name)

    # Summary
    print("\n" + "="*60)
    print("Deployment Summary")
    print("="*60)

    if args.dry_run:
        print("\n[DRY RUN] No deployments were actually created")

    if deployed:
        print(f"\n✓ Successfully deployed ({len(deployed)}):")
        for flow_name in deployed:
            print(f"  - {flow_name}")

    if failed:
        print(f"\n✗ Failed to deploy ({len(failed)}):")
        for flow_name in failed:
            print(f"  - {flow_name}")
        return 1

    if not args.dry_run:
        print("\n💡 View deployments in Prefect UI:")
        print("   https://prefect.noroutine.me")

    print("\n" + "="*60)

    return 0


if __name__ == "__main__":
    exit(main())
