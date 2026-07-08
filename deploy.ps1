# ╔══════════════════════════════════════════════════════════════════╗
# ║  deploy.ps1  —  Deploy the Full Agent to AWS AgentCore          ║
# ╚══════════════════════════════════════════════════════════════════╝
#
# Deploys agent.py to AgentCore Runtime, and passes through whichever
# optional feature environment variables are currently set in this
# PowerShell session (from setup_memory.ps1 / setup_guardrail.ps1 /
# setup_identity.ps1 / setup_gateway.ps1).
#
# You do NOT need to have run all four setup scripts — any that you
# skip are simply left unset, and that feature stays disabled in the
# deployed agent (it still runs fine without it).
#
# RUN (with .venv activated)
#   .\deploy.ps1

Write-Host ""
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  AI Assistant (Full) — Deploy to AWS AgentCore" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

# ── Check agentcore CLI is available ──────────────────────────────
if (-not (Get-Command agentcore -ErrorAction SilentlyContinue)) {
    Write-Host "  ⚠   'agentcore' command not found." -ForegroundColor Yellow
    Write-Host "  Activate your virtual environment first:" -ForegroundColor White
    Write-Host "    .venv\Scripts\Activate.ps1" -ForegroundColor Cyan
    exit 1
}

# ── IAM execution role ─────────────────────────────────────────────
Write-Host "  You need an IAM Role ARN to deploy (see README.md Step 2.4)." -ForegroundColor White
$roleArn = Read-Host "  Paste your IAM Role ARN"

if ([string]::IsNullOrWhiteSpace($roleArn)) {
    Write-Host "  ❌  No ARN entered. Exiting." -ForegroundColor Red
    exit 1
}

# ── Collect optional feature environment variables ────────────────
Write-Host ""
Write-Host "  Checking which optional features are configured in this session..." -ForegroundColor Yellow
Write-Host ""

$envVars = @{}

function Add-IfSet($name) {
    $value = [System.Environment]::GetEnvironmentVariable($name, "Process")
    if (-not [string]::IsNullOrWhiteSpace($value)) {
        $script:envVars[$name] = $value
        Write-Host "    ✅  $name is set" -ForegroundColor Green
    } else {
        Write-Host "    ⚪  $name not set (feature disabled)" -ForegroundColor Gray
    }
}

Write-Host "  Memory:" -ForegroundColor White
Add-IfSet "BEDROCK_AGENTCORE_MEMORY_ID"

Write-Host "  Guardrails / Policy:" -ForegroundColor White
Add-IfSet "GUARDRAIL_ID"
Add-IfSet "GUARDRAIL_VERSION"

Write-Host "  Identity:" -ForegroundColor White
Add-IfSet "IDENTITY_WORKLOAD_NAME"
Add-IfSet "IDENTITY_CREDENTIAL_PROVIDER"

Write-Host "  Gateway:" -ForegroundColor White
Add-IfSet "GATEWAY_URL"
Add-IfSet "GATEWAY_COGNITO_USER_POOL_ID"
Add-IfSet "GATEWAY_COGNITO_CLIENT_ID"
Add-IfSet "GATEWAY_COGNITO_USERNAME"
Add-IfSet "GATEWAY_COGNITO_PASSWORD"

Write-Host ""

# Build a comma-separated KEY=VALUE list for `agentcore configure --env`
$envArgs = @()
foreach ($key in $envVars.Keys) {
    $envArgs += "$key=$($envVars[$key])"
}

# ── Step 1: Configure ──────────────────────────────────────────────
Write-Host "  [1/3]  Configuring deployment..." -ForegroundColor Yellow
Write-Host ""

if ($envArgs.Count -gt 0) {
    $envArgString = $envArgs -join ","
    agentcore configure `
        --entrypoint agent.py `
        --execution-role $roleArn `
        --region us-east-1 `
        --env $envArgString
} else {
    Write-Host "  No optional features configured — deploying with web_search only." -ForegroundColor Gray
    agentcore configure `
        --entrypoint agent.py `
        --execution-role $roleArn `
        --region us-east-1 `
        --disable-memory
}

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "  ❌  Configuration failed." -ForegroundColor Red
    Write-Host "  If '--env' is not recognised by your CLI version, set the" -ForegroundColor White
    Write-Host "  environment variables directly in .bedrock_agentcore.yaml" -ForegroundColor White
    Write-Host "  under the runtime's environment section, then re-run:" -ForegroundColor White
    Write-Host "    agentcore launch" -ForegroundColor Cyan
    exit 1
}

Write-Host ""
Write-Host "  ✅  Configuration saved." -ForegroundColor Green
Write-Host ""

# ── Step 2: Launch ─────────────────────────────────────────────────
Write-Host "  [2/3]  Deploying to AWS AgentCore (5-10 minutes)..." -ForegroundColor Yellow
Write-Host ""

agentcore launch

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "  ❌  Deployment failed. See README.md Troubleshooting." -ForegroundColor Red
    exit 1
}

# ── Step 3: Status ─────────────────────────────────────────────────
Write-Host ""
Write-Host "  [3/3]  Checking deployment status..." -ForegroundColor Yellow
Write-Host ""
agentcore status

Write-Host ""
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  Deployment complete!" -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  NEXT STEPS:" -ForegroundColor Yellow
Write-Host "  1. Copy the Agent ARN printed above" -ForegroundColor White
Write-Host "  2. Paste it into invoke.py, chat.py, and test_memory.py" -ForegroundColor White
Write-Host "       (AGENT_ARN = `"...`")" -ForegroundColor Cyan
Write-Host "  3. python chat.py            (start chatting)" -ForegroundColor Cyan
Write-Host "  4. python test_memory.py     (run the full feature test suite)" -ForegroundColor Cyan
Write-Host ""
