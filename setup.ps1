# ╔══════════════════════════════════════════════════════════════════╗
# ║  setup.ps1  —  One-Click Project Setup (Windows PowerShell)     ║
# ╚══════════════════════════════════════════════════════════════════╝
#
# Creates a virtual environment, installs all dependencies (including
# MCP support for Gateway), and checks your AWS CLI + credentials.
#
# Run:
#   .\setup.ps1
#
# If scripts are blocked, run this once first:
#   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

Write-Host ""
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  AI Assistant (Full) — Project Setup" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

# ── Step 1: Python ────────────────────────────────────────────────
Write-Host "  [1/5]  Checking Python..." -ForegroundColor Yellow
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ❌  Python not found. Install from https://python.org (tick 'Add to PATH')." -ForegroundColor Red
    exit 1
}
Write-Host "  ✅  $pythonVersion" -ForegroundColor Green
Write-Host ""

# ── Step 2: Virtual environment ───────────────────────────────────
Write-Host "  [2/5]  Creating virtual environment (.venv)..." -ForegroundColor Yellow
if (Test-Path ".venv") {
    Write-Host "         .venv already exists — skipping" -ForegroundColor Gray
} else {
    python -m venv .venv
    Write-Host "  ✅  Virtual environment created" -ForegroundColor Green
}
Write-Host ""

# ── Step 3: Install packages ──────────────────────────────────────
Write-Host "  [3/5]  Installing packages (1-3 minutes)..." -ForegroundColor Yellow
& ".venv\Scripts\pip.exe" install --upgrade pip --quiet
& ".venv\Scripts\pip.exe" install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ❌  Package install failed. Try: .venv\Scripts\pip install -r requirements.txt" -ForegroundColor Red
    exit 1
}
Write-Host "  ✅  All packages installed" -ForegroundColor Green
Write-Host ""

# ── Step 4: AWS CLI ────────────────────────────────────────────────
Write-Host "  [4/5]  Checking AWS CLI..." -ForegroundColor Yellow
$awsVersion = aws --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ⚠   AWS CLI not found. Install: https://awscli.amazonaws.com/AWSCLIV2.msi" -ForegroundColor Yellow
} else {
    Write-Host "  ✅  $awsVersion" -ForegroundColor Green
}
Write-Host ""

# ── Step 5: AWS credentials ────────────────────────────────────────
Write-Host "  [5/5]  Checking AWS credentials..." -ForegroundColor Yellow
$identity = aws sts get-caller-identity 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ⚠   Not configured. Run: aws configure" -ForegroundColor Yellow
} else {
    $accountId = (aws sts get-caller-identity --query Account --output text 2>&1)
    Write-Host "  ✅  AWS Account: $accountId" -ForegroundColor Green
}
Write-Host ""

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  Setup complete!" -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  NEXT STEPS:" -ForegroundColor Yellow
Write-Host "  1. .venv\Scripts\Activate.ps1" -ForegroundColor Cyan
Write-Host "  2. (Optional) Run setup_memory.ps1 / setup_guardrail.ps1 /" -ForegroundColor White
Write-Host "     setup_identity.ps1 / setup_gateway.ps1 to enable extra features" -ForegroundColor White
Write-Host "  3. python agent.py         (local test)" -ForegroundColor Cyan
Write-Host "  4. python test_local.py    (in a second window)" -ForegroundColor Cyan
Write-Host "  5. .\deploy.ps1            (deploy to AWS)" -ForegroundColor Cyan
Write-Host ""
