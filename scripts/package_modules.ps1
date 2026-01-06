param(
    [string[]]$Modules = @("algo_sdk", "algo_dto"),
    [string]$OutputDir = "dist/modules",
    [string]$BundleName = "",
    [string]$PackageVersion = "0.0.0",
    [ValidateSet("zip", "whl", "both")]
    [string]$Format = "zip"
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$srcRoot = Join-Path $repoRoot "src"
$outputRoot = Join-Path $repoRoot $OutputDir

New-Item -ItemType Directory -Force -Path $outputRoot | Out-Null

Add-Type -AssemblyName System.IO.Compression.FileSystem

$moduleAliases = @{
    "algo_sdk_dto" = "algo_dto"
}

function Resolve-ModuleName([string]$name) {
    if ($moduleAliases.ContainsKey($name)) {
        return $moduleAliases[$name]
    }
    return $name
}

function Normalize-PackageName([string]$name) {
    return $name.Replace("_", "-")
}

function Resolve-PythonExe([string]$repoRoot) {
    $candidates = @(
        (Join-Path $repoRoot ".venv\Scripts\python.exe"),
        (Join-Path $repoRoot ".venv\bin\python")
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) {
            return $c
        }
    }
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Path
    }
    throw "Python not found. Create .venv first or ensure python is in PATH."
}

function New-StagingDir() {
    $base = Join-Path ([System.IO.Path]::GetTempPath()) (
        "algo-pack-" + [System.Guid]::NewGuid().ToString("N")
    )
    New-Item -ItemType Directory -Force -Path $base | Out-Null
    return $base
}

function Copy-ModuleToStaging([string]$module, [string]$stagingRoot) {
    $resolved = Resolve-ModuleName $module
    $source = Join-Path $srcRoot $resolved
    if (-not (Test-Path $source)) {
        throw "Module not found: $resolved (expected at $source)"
    }
    $dest = Join-Path $stagingRoot $resolved
    Copy-Item -Path $source -Destination $dest -Recurse -Force
}

function Remove-CacheArtifacts([string]$root) {
    Get-ChildItem -Path $root -Recurse -Force -Directory -Filter "__pycache__" |
    Remove-Item -Recurse -Force
    Get-ChildItem -Path $root -Recurse -Force -File -Filter "*.pyc" |
    Remove-Item -Force
}

function New-ZipFromStaging([string]$stagingRoot, [string]$zipPath) {
    if (Test-Path $zipPath) {
        Remove-Item $zipPath -Force
    }
    [System.IO.Compression.ZipFile]::CreateFromDirectory($stagingRoot, $zipPath)
}

function New-WheelFromStaging([string]$stagingRoot, [string]$wheelDir) {
    $py = Resolve-PythonExe $repoRoot
    Push-Location $stagingRoot
    try {
        & $py -m pip wheel . --no-deps --no-build-isolation -w $wheelDir
        if ($LASTEXITCODE -ne 0) {
            throw "Wheel build failed in staging dir: $stagingRoot"
        }
    }
    finally {
        Pop-Location
    }
}

function Write-SetupPy([string]$stagingRoot, [string]$packageName, [string]$version) {
    $content = @"
from setuptools import setup, find_namespace_packages

setup(
    name="{0}",
    version="{1}",
    packages=find_namespace_packages(),
    include_package_data=True,
)
"@ -f $packageName, $version
    $path = Join-Path $stagingRoot "setup.py"
    Set-Content -Path $path -Value $content -Encoding ASCII
}

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"

if ($BundleName) {
    $staging = New-StagingDir
    foreach ($module in $Modules) {
        Copy-ModuleToStaging $module $staging
    }
    Remove-CacheArtifacts $staging
    $packageName = Normalize-PackageName $BundleName
    Write-SetupPy $staging $packageName $PackageVersion
    if ($Format -in @("zip", "both")) {
        $zipPath = Join-Path $outputRoot (
            "{0}-{1}-{2}.zip" -f $packageName, $PackageVersion, $timestamp
        )
        New-ZipFromStaging $staging $zipPath
        Write-Host "Created $zipPath"
    }
    if ($Format -in @("whl", "both")) {
        New-WheelFromStaging $staging $outputRoot
        Write-Host "Created wheel(s) in $outputRoot"
    }
    Remove-Item $staging -Recurse -Force
}
else {
    foreach ($module in $Modules) {
        $staging = New-StagingDir
        Copy-ModuleToStaging $module $staging
        Remove-CacheArtifacts $staging
        $resolved = Resolve-ModuleName $module
        $packageName = Normalize-PackageName $resolved
        Write-SetupPy $staging $packageName $PackageVersion
        if ($Format -in @("zip", "both")) {
            $zipPath = Join-Path $outputRoot (
                "{0}-{1}-{2}.zip" -f $packageName, $PackageVersion, $timestamp
            )
            New-ZipFromStaging $staging $zipPath
            Write-Host "Created $zipPath"
        }
        if ($Format -in @("whl", "both")) {
            New-WheelFromStaging $staging $outputRoot
            Write-Host "Created wheel(s) in $outputRoot"
        }
        Remove-Item $staging -Recurse -Force
    }
}
