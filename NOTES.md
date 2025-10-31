## Prefect

```bash
# If you need it
export PREFECT_API_URL=https://prefect.noroutine.me/api

# Run local worker pool
uv run prefect worker start --pool ws-mac-00055-local-process --name $(hostname -s)

# Run docker worker pool
uv run prefect worker start --pool ws-mac-00055-docker --name $(hostname -s)
```

```bash
# start prefect server
uv run prefect server start

# start local workerpool
uv run prefect worker start --pool "local-workerpool"
```

