#!/usr/bin/env bash

set -e

REPO_DIR=./.local-workerpool/ipfix-analytics-master

# Clone/update repo
mkdir -p "$REPO_DIR"
cd "$REPO_DIR"

if [ -d ".git" ]; then
  git fetch origin
  git reset --hard origin/main
  git clean -fd
else
  git clone git@nrtn.dev/noroutine/ipfix-analytics.git .
fi