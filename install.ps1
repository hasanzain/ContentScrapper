# ContentScrapper 1-Click Automated Setup for Windows
$ErrorActionPreference = "Stop"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Starting 1-Click Setup for TikTok Scraper MCP" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# Check Python availability
$pyCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pyCmd) {
    $pyCmd = Get-Command py -ErrorAction SilentlyContinue
}

if (-not $pyCmd) {
    Write-Host "ERROR: Python 3.10+ not found in PATH." -ForegroundColor Red
    Write-Host "Please install Python from https://www.python.org/downloads/ and ensure 'Add to PATH' is checked." -ForegroundColor Yellow
    Exit 1
}

# Run install.py
& $pyCmd.Source install.py
