FROM python:3.13-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    jq \
    unzip \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js (v20 LTS)
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Install rclone
RUN curl https://rclone.org/install.sh | bash

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock .python-version ./

# Install Python dependencies with uv
RUN uv pip install --system -r pyproject.toml

# COPY ipfix_pipeline.py /opt/prefect/ipfix-big-data/
COPY ./scripts/setup-ssh.py /scripts/setup-ssh.py
WORKDIR /opt/prefect/worker

ENV PREFECT_API_URL=https://prefect.noroutine.me/api

# Default command (you can override this)
CMD ["/bin/bash"]
