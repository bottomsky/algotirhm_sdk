$ErrorActionPreference = "Stop"

param(
    [string]$Tag = "algo-core-service:latest"
)

docker build -t $Tag -f Dockerfile .
