# One-time setup: use system Python 3.12 (no venv).
# Run in PowerShell (Admin not required):
#   powershell -ExecutionPolicy Bypass -File scripts\setup_system_python.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Py = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"

if (-not (Test-Path $Py)) {
  Write-Host "Python 3.12 not found. Install with:"
  Write-Host "  winget install Python.Python.3.12"
  exit 1
}

Set-Location $Root
Write-Host "Using $Py"
& $Py -m pip install --upgrade pip
& $Py -m pip install ipykernel jupyter
& $Py -m ipykernel install --user --name python312 --display-name "Python 3.12 (system)"
& $Py -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
& $Py -m pip install -r requirements.txt
& $Py -c "import torch; print('CUDA:', torch.cuda.is_available()); import ipykernel; print('ipykernel OK')"
Write-Host "Done. In VS Code: Python: Select Interpreter -> Python 3.12 (system)"
