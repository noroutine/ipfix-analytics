#!/bin/bash
# build-image.sh
set -euo pipefail

# Configuration
IMAGE_REGISTRY="cr.noroutine.me/sandbox"
IMAGE_NAME="ipfix-pipeline-worker"
PLATFORMS="linux/amd64,linux/arm64"
BUILDER_NAME="multiarch"

# Get version info
GIT_SHA=$(git rev-parse --short HEAD)
GIT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
FULL_IMAGE="$IMAGE_REGISTRY/$IMAGE_NAME"

# Allow custom tag override (e.g., for specific commit or version)
CUSTOM_TAG="${1:-}"

echo "================================================"
echo "Building Multi-Platform Docker Image"
echo "================================================"
echo "Image: $FULL_IMAGE"
echo "SHA: $GIT_SHA"
echo "Branch: $GIT_BRANCH"
echo "Platforms: $PLATFORMS"
if [ -n "$CUSTOM_TAG" ]; then
  echo "Custom tag: $CUSTOM_TAG"
fi
echo "================================================"

# Setup buildx
if ! docker buildx inspect "$BUILDER_NAME" >/dev/null 2>&1; then
  echo "Creating buildx builder: $BUILDER_NAME"
  docker buildx create --name "$BUILDER_NAME" --driver docker-container
else
  echo "Using existing buildx builder: $BUILDER_NAME"
fi

docker buildx use "$BUILDER_NAME"
docker buildx inspect --bootstrap

# Build and push
echo "Building and pushing..."

# Build tag arguments
TAG_ARGS=(
  --tag "$FULL_IMAGE:$GIT_SHA"
  --tag "$FULL_IMAGE:$GIT_BRANCH"
  --tag "$FULL_IMAGE:latest"
)

# Add custom tag if provided
if [ -n "$CUSTOM_TAG" ]; then
  TAG_ARGS+=(--tag "$FULL_IMAGE:$CUSTOM_TAG")
fi

docker buildx build \
  --platform "$PLATFORMS" \
  "${TAG_ARGS[@]}" \
  --push \
  --load \
  --progress=plain \
  .

echo ""
echo "✅ Build complete!"
echo "Tags pushed:"
echo "  • $FULL_IMAGE:$GIT_SHA"
echo "  • $FULL_IMAGE:$GIT_BRANCH"
echo "  • $FULL_IMAGE:latest"
if [ -n "$CUSTOM_TAG" ]; then
  echo "  • $FULL_IMAGE:$CUSTOM_TAG"
fi
echo ""
