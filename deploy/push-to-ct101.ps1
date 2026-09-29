# Pack runtime files and copy to Proxmox CT 101 (192.168.0.51).
# Does not copy Datasets/, llm_data/, or *.train.pt
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\deploy\push-to-ct101.ps1
# Optional: $env:AGROSCAN_CT_USER = "root"

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$Ct = if ($env:AGROSCAN_CT_HOST) { $env:AGROSCAN_CT_HOST } else { "192.168.0.51" }
$User = if ($env:AGROSCAN_CT_USER) { $env:AGROSCAN_CT_USER } else { "root" }
$Staging = Join-Path $env:TEMP "agroscan-ct101"
$Tar = Join-Path $env:TEMP "agroscan-runtime.tar"

Write-Host "Staging runtime (no Datasets) -> $Staging"
if (Test-Path $Staging) { Remove-Item -Recurse -Force $Staging }
New-Item -ItemType Directory -Path $Staging | Out-Null

function Copy-Tree($rel) {
  $src = Join-Path $Root $rel
  $dst = Join-Path $Staging $rel
  New-Item -ItemType Directory -Path (Split-Path $dst) -Force | Out-Null
  Copy-Item -Recurse -Force $src $dst
}

Copy-Tree "agroscan"
Copy-Tree "backend"
Copy-Tree "web"
Copy-Tree "data"
Copy-Tree "deploy"
Copy-Item (Join-Path $Root "requirements.txt") (Join-Path $Staging "requirements.txt")
Copy-Item (Join-Path $Root ".env.example") (Join-Path $Staging ".env.example")
$envSrc = Join-Path $Root ".env"
if (Test-Path $envSrc) { Copy-Item $envSrc (Join-Path $Staging ".env") }

Get-ChildItem (Join-Path $Staging "agroscan") -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
Get-ChildItem (Join-Path $Staging "backend") -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force

New-Item -ItemType Directory -Path (Join-Path $Staging "models") | Out-Null
$modelsDir = Join-Path $Staging "models"
Get-ChildItem (Join-Path $Root "models") -File -Filter "*.pt" | Where-Object {
  $_.Name -notlike "*.train.pt"
} | ForEach-Object {
  Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $modelsDir $_.Name)
}

if (Test-Path $Tar) { Remove-Item -Force $Tar }
Push-Location $Staging
try {
  tar -cf $Tar agroscan backend web data deploy models requirements.txt .env.example
  if (Test-Path ".env") { tar -rf $Tar .env }
} finally {
  Pop-Location
}

$remote = "${User}@${Ct}"
Write-Host "SSH $remote ..."
ssh -o ConnectTimeout=10 $remote "mkdir -p /opt/agroscan"
scp $Tar "${remote}:/tmp/agroscan-runtime.tar"
ssh $remote "tar -xf /tmp/agroscan-runtime.tar -C /opt/agroscan; sed -i 's/\r$//' /opt/agroscan/deploy/ct101-setup.sh /opt/agroscan/deploy/agroscan.service; chmod +x /opt/agroscan/deploy/ct101-setup.sh; sh /opt/agroscan/deploy/ct101-setup.sh"
Write-Host "Done. LAN: http://${Ct}:8000 (only if you change bind). Public: https://agroscan.mujahidulhaquejihad.com after the tunnel token is installed."
