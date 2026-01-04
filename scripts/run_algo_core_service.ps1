$ErrorActionPreference = "Stop"

if (-not $env:SERVICE_INSTANCE_ID -or [string]::IsNullOrWhiteSpace($env:SERVICE_INSTANCE_ID)) {
    $name = $env:SERVICE_NAME
    if ([string]::IsNullOrWhiteSpace($name)) {
        $name = "algo-service"
    }
    $suffix = [guid]::NewGuid().ToString("N").Substring(0, 8)
    $env:SERVICE_INSTANCE_ID = "$name-$suffix"
}

python -m algo_core_service.main
