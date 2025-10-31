# Build Scripts

## build-ipfix-pipeline-image.sh

Multi-architecture Docker image builder for the IPFIX pipeline worker.

### Features

- **Multi-platform builds**: Creates images for both `linux/amd64` and `linux/arm64`
- **Automatic tagging**: Tags with git commit SHA, branch name, and `latest`
- **Docker buildx**: Uses docker buildx for cross-platform builds
- **Registry push**: Automatically pushes to `cr.nrtn.dev/sandbox/ipfix-pipeline-worker`

### Usage

#### Basic build (uses git SHA and branch):
```bash
bash scripts/build-ipfix-pipeline-image.sh
```

This creates and pushes:
- `cr.nrtn.dev/sandbox/ipfix-pipeline-worker:{git-sha}`
- `cr.nrtn.dev/sandbox/ipfix-pipeline-worker:{branch}`
- `cr.nrtn.dev/sandbox/ipfix-pipeline-worker:latest`

#### Build with custom tag:
```bash
bash scripts/build-ipfix-pipeline-image.sh v1.2.3
```

This creates all the above tags PLUS:
- `cr.nrtn.dev/sandbox/ipfix-pipeline-worker:v1.2.3`

### Requirements

- Docker with buildx plugin
- Docker registry authentication for `cr.nrtn.dev`
- Git repository (for SHA and branch detection)

### Example Output

```
================================================
Building Multi-Platform Docker Image
================================================
Image: cr.nrtn.dev/sandbox/ipfix-pipeline-worker
SHA: abc1234
Branch: master
Platforms: linux/amd64,linux/arm64
Custom tag: v1.2.3
================================================
Creating buildx builder: multiarch
...
Building and pushing...
...
✅ Build complete!
Tags pushed:
  • cr.nrtn.dev/sandbox/ipfix-pipeline-worker:abc1234
  • cr.nrtn.dev/sandbox/ipfix-pipeline-worker:master
  • cr.nrtn.dev/sandbox/ipfix-pipeline-worker:latest
  • cr.nrtn.dev/sandbox/ipfix-pipeline-worker:v1.2.3
```

### Used By

- `deploy.py` - Python deployment script calls this automatically
- `prefect.yaml` - Can be called in build steps
- CI/CD pipelines - Direct invocation for automated builds

### Troubleshooting

#### Buildx builder not found
```bash
# Create manually
docker buildx create --name multiarch --driver docker-container
docker buildx use multiarch
```

#### Registry authentication error
```bash
# Login to registry
docker login cr.nrtn.dev
```

#### Platform not supported
Ensure Docker Desktop or Docker daemon supports the target platforms. On macOS with Docker Desktop, this is automatic. On Linux, you may need to install qemu:
```bash
docker run --privileged --rm tonistiigi/binfmt --install all
```
