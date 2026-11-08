# Repository da duoc tao: https://github.com/hungnmph50619/VietTranscribe
# Script nay chi day cac thay doi tai may len repo hien co.
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'Can cai Git truoc.' }
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { throw 'Can cai GitHub CLI truoc.' }
& gh auth status
if ($LASTEXITCODE -ne 0) { & gh auth login }
if (-not (Test-Path .git)) { & git init -b main }
& git remote get-url origin *> $null
if ($LASTEXITCODE -ne 0) {
    & git remote add origin https://github.com/hungnmph50619/VietTranscribe.git
}
& git fetch origin main
if ($LASTEXITCODE -ne 0) { throw 'Khong tai duoc nhanh main tu GitHub.' }
Write-Host 'Repo da ton tai. Nen git clone moi ve may de tranh xung dot, roi chinh sua va push.' -ForegroundColor Yellow
Write-Host 'Dia chi: https://github.com/hungnmph50619/VietTranscribe'
