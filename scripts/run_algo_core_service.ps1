$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot

# .env is loaded by algo_core_service.main via algo_sdk.
$srcPath = Join-Path $repoRoot "src"
if (-not $env:PYTHONPATH) {
    $env:PYTHONPATH = $srcPath
} elseif (-not ($env:PYTHONPATH -split ";" | Where-Object { $_ -eq $srcPath })) {
    $env:PYTHONPATH = "$srcPath;$env:PYTHONPATH"
}

if (-not $env:SERVICE_INSTANCE_ID -or [string]::IsNullOrWhiteSpace($env:SERVICE_INSTANCE_ID)) {
    $name = $env:SERVICE_NAME
    if ([string]::IsNullOrWhiteSpace($name)) {
        $name = "algo-service"
    }
    $suffix = [guid]::NewGuid().ToString("N").Substring(0, 8)
    $env:SERVICE_INSTANCE_ID = "$name-$suffix"
}

$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (Test-Path $venvPython) {
    & $venvPython -m algo_core_service.main
}
else {
    python -m algo_core_service.main
}
