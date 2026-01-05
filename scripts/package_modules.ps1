param(
    [string[]]$Modules = @("algo_sdk", "algo_dto"),
    [string]$OutputDir = "dist/modules",
    [string]$BundleName = "",
    [string]$PackageVersion = "0.0.0"
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

function Write-SetupPy([string]$stagingRoot, [string]$packageName, [string]$version) {
    $content = @"
from setuptools import setup, find_packages

setup(
    name="{0}",
    version="{1}",
    packages=find_packages(),
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
    $zipPath = Join-Path $outputRoot (
        "{0}-{1}-{2}.zip" -f $packageName, $PackageVersion, $timestamp
    )
    New-ZipFromStaging $staging $zipPath
    Remove-Item $staging -Recurse -Force
    Write-Host "Created $zipPath"
}
else {
    foreach ($module in $Modules) {
        $staging = New-StagingDir
        Copy-ModuleToStaging $module $staging
        Remove-CacheArtifacts $staging
        $resolved = Resolve-ModuleName $module
        $packageName = Normalize-PackageName $resolved
        Write-SetupPy $staging $packageName $PackageVersion
        $zipPath = Join-Path $outputRoot (
            "{0}-{1}-{2}.zip" -f $packageName, $PackageVersion, $timestamp
        )
        New-ZipFromStaging $staging $zipPath
        Remove-Item $staging -Recurse -Force
        Write-Host "Created $zipPath"
    }
}
