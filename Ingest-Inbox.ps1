# Double-click launcher for the normal knowledge-base inbox ingestion flow.
#
# Runs from the repository root, activates .venv, then executes:
#   python tools\ingest_inbox.py

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RepoRoot

$ActivateScript = Join-Path $RepoRoot ".venv\Scripts\Activate.ps1"
if (-not (Test-Path $ActivateScript)) {
    Write-Host "Could not find the virtual environment activation script:" -ForegroundColor Red
    Write-Host "  $ActivateScript"
    Write-Host ""
    Write-Host "Create the venv first, for example:"
    Write-Host "  python -m venv .venv"
    Write-Host "  .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt"
    Write-Host ""
    Read-Host "Press Enter to close"
    exit 1
}

Write-Host "Activating virtual environment..."
. $ActivateScript

Write-Host "Running inbox ingestion..."
python tools\ingest_inbox.py

$ExitCode = $LASTEXITCODE
Write-Host ""
if ($ExitCode -eq 0) {
    Write-Host "Inbox ingestion finished successfully." -ForegroundColor Green
} else {
    Write-Host "Inbox ingestion failed with exit code $ExitCode." -ForegroundColor Red
}

Read-Host "Press Enter to close"
exit $ExitCode
