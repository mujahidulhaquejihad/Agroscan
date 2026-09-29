# Update CT 101 with current agroscan/ backend/ web/ deploy/ only.
# Does not copy Datasets, models, or re-run ct101-setup.sh.
#
# From I:\Agroscan\Agroscan:
#   powershell -ExecutionPolicy Bypass -File .\deploy\update-ct101.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root

$Ct = if ($env:AGROSCAN_CT_HOST) { $env:AGROSCAN_CT_HOST } else { "192.168.0.51" }
$User = if ($env:AGROSCAN_CT_USER) { $env:AGROSCAN_CT_USER } else { "root" }
$Staging = Join-Path $env:TEMP "agroscan-update"
$Tar = Join-Path $env:TEMP "agroscan-update.tar"
$Sh = Join-Path $env:TEMP "agroscan-update.sh"

Write-Host "Packing from $Root"
if (Test-Path $Staging) { Remove-Item -Recurse -Force $Staging }
New-Item -ItemType Directory -Path $Staging | Out-Null

foreach ($name in @("agroscan", "backend", "web", "deploy")) {
  Copy-Item -Recurse -Force (Join-Path $Root $name) (Join-Path $Staging $name)
}
Get-ChildItem $Staging -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
  Remove-Item -Recurse -Force

if (Test-Path $Tar) { Remove-Item -Force $Tar }
Push-Location $Staging
try {
  tar -cf $Tar agroscan backend web deploy
} finally {
  Pop-Location
}

$remoteLines = @(
  "#!/bin/sh",
  "set -eu",
  "tar -xf /tmp/agroscan-update.tar -C /opt/agroscan",
  'sed -i "s/\r$//" /opt/agroscan/deploy/agroscan.service',
  "touch /opt/agroscan/.env",
  "grep -q AGROSCAN_LLM_MAX_NEW /opt/agroscan/.env || echo AGROSCAN_LLM_MAX_NEW=1024 >> /opt/agroscan/.env",
  'sed -i "s/^AGROSCAN_LLM_MAX_NEW=.*/AGROSCAN_LLM_MAX_NEW=1024/" /opt/agroscan/.env',
  "grep -q AGROSCAN_GEMINI_MODEL /opt/agroscan/.env || echo AGROSCAN_GEMINI_MODEL=gemini-flash-latest >> /opt/agroscan/.env",
  'sed -i "s/^AGROSCAN_GEMINI_MODEL=.*/AGROSCAN_GEMINI_MODEL=gemini-flash-latest/" /opt/agroscan/.env',
  "install -m 644 /opt/agroscan/deploy/agroscan.service /etc/systemd/system/agroscan.service",
  "systemctl daemon-reload",
  "systemctl restart agroscan",
  "sleep 2",
  "systemctl is-active agroscan",
  "curl -sS -m 15 http://127.0.0.1:8000/api/status"
)
$unix = ($remoteLines -join "`n") + "`n"
[System.IO.File]::WriteAllBytes($Sh, [System.Text.Encoding]::UTF8.GetBytes($unix))

$remote = "${User}@${Ct}"
Write-Host "Copying to $remote ..."
scp $Tar $Sh "${remote}:/tmp/"
ssh $remote "sed -i 's/\r`$//' /tmp/agroscan-update.sh && sh /tmp/agroscan-update.sh"
Write-Host "Done. Hard-refresh https://agroscan.mujahidulhaquejihad.com"
