$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
try {
    & py -3.11 --version
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.11 not found' }
} catch {
    Write-Host 'Dang cai Python 3.11 ...'
    winget install --id Python.Python.3.11 --exact --accept-package-agreements --accept-source-agreements
    Write-Host 'Mo lai PowerShell roi chay lai install.ps1.'
    exit 1
}
& py -3.11 -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'Khong tao duoc moi truong Python' }
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'Khong nang cap duoc pip' }
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Khong cai duoc thu vien' }
Write-Host 'CAI DAT HOAN TAT. Chay .\run.ps1 de mo phan mem.' -ForegroundColor Green
