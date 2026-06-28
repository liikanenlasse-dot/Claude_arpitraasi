# Push this project to GitHub from Windows PowerShell.
# Run this file from the folder where you want to keep the repository.

$ErrorActionPreference = "Stop"

$RepoUrl = "https://github.com/liikanenlasse-dot/Claude_arpitraasi.git"
$RepoDir = "Claude_arpitraasi"

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git is not installed or not available in PATH. Install Git for Windows first."
}

if (-not (Test-Path $RepoDir)) {
    git clone $RepoUrl $RepoDir
}

Copy-Item -Path ".\*" -Destination $RepoDir -Recurse -Force -Exclude $RepoDir, ".git", "*.zip"
Set-Location $RepoDir

git add .
git status

git commit -m "Initial Veikkaus odds monitor"
git push origin main

Write-Host "Done. Open: https://github.com/liikanenlasse-dot/Claude_arpitraasi" -ForegroundColor Green
