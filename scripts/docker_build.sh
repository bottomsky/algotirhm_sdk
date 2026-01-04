#!/usr/bin/env sh
set -eu

tag="${1:-algo-core-service:latest}"
docker build -t "$tag" -f Dockerfile .
