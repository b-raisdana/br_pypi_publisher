#!/usr/bin/env pwsh
$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Always run through the active environment (venv or conda). Resolving a bare
# `python` can land on the base interpreter, which has no build/twine/pre-commit.
$Py = $null
$candidates = @()
if ($env:VIRTUAL_ENV) {
    $candidates += (Join-Path $env:VIRTUAL_ENV "Scripts\python.exe")
    $candidates += (Join-Path $env:VIRTUAL_ENV "bin\python")
}
if ($env:CONDA_PREFIX) {
    $candidates += (Join-Path $env:CONDA_PREFIX "python.exe")
    $candidates += (Join-Path $env:CONDA_PREFIX "Scripts\python.exe")
}
foreach ($candidate in $candidates) {
    if (Test-Path -LiteralPath $candidate) { $Py = $candidate; break }
}
if (-not $Py) { $Py = (Get-Command python -ErrorAction SilentlyContinue).Source }
if (-not $Py) {
    Write-Error "No python found. Activate a venv or conda environment first."
    exit 1
}

& $Py (Join-Path $scriptDir "publish_to_pypi.py") @args
exit $LASTEXITCODE