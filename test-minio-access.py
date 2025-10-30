#!/usr/bin/env python3
"""
Test script to verify MinIO bucket access using Prefect AwsCredentials block.
This helps debug connection issues without running the full pipeline.
"""

from prefect_aws import AwsCredentials
from datetime import datetime

# Configuration
BLOCK_NAME = "minio-credentials"
BUCKET_NAME = "ipfix"
PREFIX = "ipfix_"

print("=" * 60)
print("MinIO Bucket Access Test")
print("=" * 60)

# Load credentials from Prefect block
print(f"\n[1/4] Loading credentials from block: {BLOCK_NAME}")
try:
    aws_credentials = AwsCredentials.load(BLOCK_NAME)
    print("✓ Block loaded successfully")
except Exception as e:
    print(f"✗ Failed to load block: {e}")
    exit(1)

# Extract endpoint configuration
endpoint_url = None
if aws_credentials.aws_client_parameters:
    client_params = aws_credentials.aws_client_parameters.model_dump()
    endpoint_url = client_params.get("endpoint_url")

print(f"\n[2/4] Configuration from block:")
print(f"  - Endpoint: {endpoint_url}")
print(f"  - Region: {aws_credentials.region_name}")

# Create S3 client
print(f"\n[3/4] Creating boto3 S3 client...")
try:
    boto3_session = aws_credentials.get_boto3_session()
    s3_client = boto3_session.client('s3', endpoint_url=endpoint_url)
    print("✓ S3 client created")
    print(f"  - Boto3 endpoint: {s3_client.meta.endpoint_url}")
    print(f"  - Boto3 region: {s3_client.meta.region_name}")
except Exception as e:
    print(f"✗ Failed to create S3 client: {e}")
    exit(1)

# List bucket contents
print(f"\n[4/4] Listing objects in bucket '{BUCKET_NAME}' with prefix '{PREFIX}'...")
try:
    response = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix=PREFIX)

    if 'Contents' not in response:
        print(f"✓ Bucket accessible, but no files found with prefix '{PREFIX}'")
    else:
        print(f"✓ Bucket accessible! Found {len(response['Contents'])} file(s):")
        print("\n" + "-" * 60)
        for obj in response['Contents']:
            file_key = obj['Key']
            last_modified = obj['LastModified']
            file_size_mb = obj['Size'] / (1024 * 1024)
            age_days = (datetime.now(last_modified.tzinfo) - last_modified).days
            print(f"  {file_key}")
            print(f"    Size: {file_size_mb:.2f} MB")
            print(f"    Modified: {last_modified.isoformat()} ({age_days} days ago)")
            print()
        print("-" * 60)

        total_size_gb = sum(obj['Size'] for obj in response['Contents']) / (1024**3)
        print(f"\nTotal: {len(response['Contents'])} files, {total_size_gb:.2f} GB")

except Exception as e:
    print(f"✗ Failed to list bucket: {e}")
    print(f"\nError type: {type(e).__name__}")
    if hasattr(e, 'response'):
        print(f"Error details: {e.response}")
    exit(1)

print("\n" + "=" * 60)
print("Test completed successfully!")
print("=" * 60)
