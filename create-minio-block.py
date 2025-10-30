#!/usr/bin/env python3
"""
Interactive script to create a Prefect AwsCredentials block for S3/MinIO.
This stores your S3 credentials securely in Prefect for use by the pipeline.
"""

from prefect_aws import AwsCredentials
import getpass

# MinIO endpoint - update this if your MinIO server is at a different location
MINIO_ENDPOINT = "https://s3.noroutine.me"

print("=" * 60)
print("S3 Credentials Block Setup")
print("=" * 60)
print("\nThis script will create a Prefect block to store your MinIO credentials.")
print("The credentials will be encrypted and stored securely by Prefect.\n")

# Get credentials interactively
block_name = input("Block name [minio-credentials]: ").strip() or "minio-credentials"
endpoint = input(f"S3 Endpoint [{MINIO_ENDPOINT}]: ").strip() or MINIO_ENDPOINT
access_key = input("S3 Access Key ID: ").strip()
secret_key = getpass.getpass("S3 Secret Access Key: ")

if not access_key or not secret_key:
    print("\nError: Both access key and secret key are required!")
    exit(1)

# Optional region and test bucket
region = input("AWS Region [us-east-1]: ").strip() or "us-east-1"
test_bucket = input("Test bucket name (optional, press Enter to skip): ").strip()

print("\n" + "-" * 60)
print("Creating Prefect block with the following configuration:")
print(f"  Block name: {block_name}")
print(f"  Endpoint: {endpoint}")
print(f"  Region: {region}")
print(f"  Access Key: {access_key[:4]}***")
print("-" * 60)

# Create and save the credentials block
try:
    aws_credentials = AwsCredentials(
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        aws_session_token=None,
        region_name=region,
        aws_client_parameters={
            "endpoint_url": endpoint
        }
    )

    aws_credentials.save(block_name, overwrite=True)

    print(f"\n✓ Successfully created block '{block_name}'!")

    # Test the credentials if bucket name provided
    if test_bucket:
        print(f"\n" + "-" * 60)
        print(f"Testing bucket access: {test_bucket}")
        print("-" * 60)

        try:
            # Reload the block and create S3 client
            print("Creating S3 client...")
            test_credentials = AwsCredentials.load(block_name)

            # Get endpoint from client parameters
            endpoint_url = None
            if test_credentials.aws_client_parameters:
                client_params = test_credentials.aws_client_parameters.model_dump()
                endpoint_url = client_params.get("endpoint_url")

            boto3_session = test_credentials.get_boto3_session()
            s3_client = boto3_session.client('s3', endpoint_url=endpoint_url)

            print(f"  Boto3 endpoint: {s3_client.meta.endpoint_url}")
            print(f"  Boto3 region: {s3_client.meta.region_name}")

            # Try to list objects
            print(f"\nListing objects in bucket '{test_bucket}'...")
            response = s3_client.list_objects_v2(Bucket=test_bucket, MaxKeys=5)

            if 'Contents' not in response:
                print(f"✓ Credentials valid! Bucket '{test_bucket}' is accessible (empty or no matching objects)")
            else:
                print(f"✓ Credentials valid! Found {len(response['Contents'])} object(s) in bucket:")
                for obj in response['Contents'][:5]:
                    print(f"  - {obj['Key']} ({obj['Size'] / 1024:.1f} KB)")

                if response.get('IsTruncated'):
                    print(f"  ... and more")

            print(f"\n✓ Validation successful! Credentials are working correctly.")

        except Exception as e:
            print(f"\n✗ Validation failed: {e}")
            print(f"\nThe block was created but credentials may not be working.")
            print(f"Please verify your access key, secret key, and endpoint.")
            exit(1)

    print(f"\nYou can now use this block in your pipeline:")
    print(f"  ipfix_pipeline(aws_credentials_block='{block_name}')")
    print("\nOr update the default in prefect.yaml if you used a different name.")

except Exception as e:
    print(f"\n✗ Error creating block: {e}")
    exit(1)
