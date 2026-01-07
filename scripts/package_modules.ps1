param(
    [string[]]$Modules = @("algo_sdk", "algo_dto", "algo_decorators", "algo_core_service"),
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

function Normalize-Modules([string[]]$modules) {
    if (-not $modules) {
        return @()
    }
    if ($modules.Count -eq 1) {
        $single = $modules[0]
        if ($single -match "[,;\s]") {
            return @($single -split "[,;\s]+" | Where-Object { $_ -and $_.Trim() })
        }
    }
    return $modules
}

function Get-ModuleDependencies([string]$resolvedModule, [string]$version) {
    $name = Normalize-PackageName $resolvedModule
    $deps = @()
    switch ($name) {
        "algo-dto" {
            $deps += "pydantic>=2.12.5"
            $deps += "numpy>=2.4.0"
        }
        "algo-decorators" {
            $deps += "pydantic>=2.12.5"
            $deps += "typing-extensions>=4.12.2; python_version < '3.12'"
        }
        "algo-sdk" {
            $deps += "algo-decorators>=$version"
            $deps += "fastapi>=0.128.0"
            $deps += "pydantic>=2.12.5"
            $deps += "python-dotenv>=1.2.1"
            $deps += "pyyaml>=6.0.3"
            $deps += "typing-extensions>=4.12.2; python_version < '3.12'"
            $deps += "uvicorn>=0.40.0"
        }
        "algo-core-service" {
            $deps += "algo-dto>=$version"
            $deps += "algo-sdk>=$version"
        }
        default {
            $deps = @()
        }
    }
    return $deps
}

function Merge-Dependencies([string[]]$moduleNames, [string]$version) {
    $set = New-Object System.Collections.Generic.HashSet[string]
    foreach ($m in $moduleNames) {
        $resolved = Resolve-ModuleName $m
        $deps = Get-ModuleDependencies $resolved $version
        foreach ($d in $deps) {
            [void]$set.Add($d)
        }
    }
    return $set.ToArray()
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

function Ensure-PipInstalled([string]$pythonExe) {
    try {
        & $pythonExe -m pip --version | Out-Null
        if ($LASTEXITCODE -eq 0) { return }
    }
    catch {
    }

    & $pythonExe -m ensurepip --upgrade | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "pip bootstrap failed via ensurepip"
    }

    & $pythonExe -m pip --version | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "pip is still unavailable after ensurepip"
    }
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
    Ensure-PipInstalled $py
    Push-Location $stagingRoot
    try {
        & $py -m pip wheel . --no-deps -w $wheelDir
        if ($LASTEXITCODE -ne 0) {
            throw "Wheel build failed in staging dir: $stagingRoot"
        }
    }
    finally {
        Pop-Location
    }
}

function Write-SetupPy(
    [string]$stagingRoot,
    [string]$packageName,
    [string]$version,
    [string[]]$installRequires
) {
    $requiresLines = ""
    if ($installRequires -and $installRequires.Length -gt 0) {
        $quoted = $installRequires | ForEach-Object { "        `"$($_)`"," }
        $requiresLines = ($quoted -join "`r`n")
    }
    $content = @"
from setuptools import setup, find_packages

setup(
    name="{0}",
    version="{1}",
    python_requires=">=3.11",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
{2}
    ],
)
"@ -f $packageName, $version, $requiresLines
    $path = Join-Path $stagingRoot "setup.py"
    Set-Content -Path $path -Value $content -Encoding ASCII
}

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$Modules = Normalize-Modules $Modules

if ($BundleName) {
    $staging = New-StagingDir
    foreach ($module in $Modules) {
        Copy-ModuleToStaging $module $staging
    }
    Remove-CacheArtifacts $staging
    $packageName = Normalize-PackageName $BundleName
    $bundleDeps = Merge-Dependencies $Modules $PackageVersion
    Write-SetupPy $staging $packageName $PackageVersion $bundleDeps
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
        $deps = Get-ModuleDependencies $resolved $PackageVersion
        Write-SetupPy $staging $packageName $PackageVersion $deps
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
