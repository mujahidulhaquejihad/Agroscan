# Run AgroScan API + Qwen2.5-3B chat on this PC (RTX 3060 / 16 GB RAM)
# Usage (PowerShell):
#   1) Close Chrome/Brave/Discord temporarily (frees RAM)
#   2) .\scripts\run_local_with_llm.ps1

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

$env:USE_TF = "0"
$env:TRANSFORMERS_NO_TF = "1"
$env:TF_CPP_MIN_LOG_LEVEL = "3"
$env:AGROSCAN_LLM_ENABLED = "1"
$env:AGROSCAN_LLM_PRELOAD = "1"
$env:AGROSCAN_LLM_DEVICE = "cuda"
$env:AGROSCAN_LLM_BASE = "Qwen/Qwen2.5-3B-Instruct"
$env:AGROSCAN_LLM_4BIT = "1"

Write-Host "Starting AgroScan on http://127.0.0.1:8000"
Write-Host "Qwen2.5-3B will preload on GPU (4-bit). If it fails, close browsers and POST /api/llm/load"
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
