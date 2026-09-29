# Run AgroScan API. Gemini from .env (local Gemma stays off).
#   powershell -ExecutionPolicy Bypass -File .\scripts\run_local_with_llm.ps1

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

$envFile = Join-Path (Get-Location) ".env"
if (Test-Path $envFile) {
  Get-Content -LiteralPath $envFile -Encoding UTF8 | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith("#") -or ($line.IndexOf("=") -lt 1)) { return }
    $k = $line.Substring(0, $line.IndexOf("=")).Trim()
    $v = $line.Substring($line.IndexOf("=") + 1).Trim().Trim('"').Trim("'")
    if ($k) { Set-Item -Path ("Env:" + $k) -Value $v }
  }
}

$env:USE_TF = "0"
$env:TRANSFORMERS_NO_TF = "1"
$env:TF_CPP_MIN_LOG_LEVEL = "3"
$env:AGROSCAN_LLM_ENABLED = "1"
$env:AGROSCAN_GEMINI = "1"
$env:AGROSCAN_LLM_LOCAL = "0"
$env:AGROSCAN_LLM_PRELOAD = "0"

if (-not $env:GEMINI_API_KEY) {
  Write-Host "No GEMINI_API_KEY in .env. Add it and run again."
  exit 1
}

Write-Host "Starting AgroScan on http://127.0.0.1:8000"
Write-Host "RAG chat: Gemini API (local Gemma off)"
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
