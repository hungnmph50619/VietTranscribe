$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { throw 'Chua cai dat. Hay chay .\install.ps1 truoc.' }
& $python (Join-Path $PSScriptRoot 'app.py')
