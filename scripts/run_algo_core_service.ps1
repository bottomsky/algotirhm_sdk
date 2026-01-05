$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot

$envFile = Join-Path $repoRoot ".env"
if (Test-Path $envFile) {
    $lines = Get-Content -Path $envFile -Encoding UTF8
    foreach ($line in $lines) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) {
            continue
        }
        $m = [regex]::Match($trimmed, "^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$")
        if (-not $m.Success) {
            continue
        }
        $key = $m.Groups[1].Value
        $value = $m.Groups[2].Value
        if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        if (-not $env:$key) {
            Set-Item -Path "Env:$key" -Value $value
        }
    }
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
