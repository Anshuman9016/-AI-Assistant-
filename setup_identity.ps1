# ╔══════════════════════════════════════════════════════════════════╗
# ║  setup_identity.ps1  —  Create an AgentCore Identity workload   ║
# ╚══════════════════════════════════════════════════════════════════╝
#
# WHAT THIS CREATES
#   1. A "workload identity" — an identity for the AGENT ITSELF
#      (not a human user), which AgentCore uses to authenticate
#      the agent when it asks for credentials.
#   2. An API-key credential provider — a secure, central place to
#      store one secret (a demo API key), which the agent can ask
#      Identity to "vend" at runtime instead of reading it from a
#      plain environment variable.
#
# WHAT YOU DO WITH THE OUTPUT
#   Export both names as environment variables and pass them to
#   deploy.ps1 as deployment environment variables.
#
# RUN
#   .\setup_identity.ps1
#   (You will be prompted to paste a demo API key value to store —
#    any placeholder string is fine for testing this pattern.)

Write-Host ""
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  Creating AgentCore Identity workload + credential provider" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

$region = "us-east-1"
$workloadName = "ai-assistant-workload"
$providerName = "demo-quotes-api"

Write-Host "  [1/2]  Creating workload identity '$workloadName'..." -ForegroundColor Yellow
$workloadResult = aws bedrock-agentcore-control create-workload-identity `
    --region $region `
    --name $workloadName `
    --output json 2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Host "  ❌  Failed to create workload identity." -ForegroundColor Red
    Write-Host $workloadResult -ForegroundColor Red
    exit 1
}
Write-Host $workloadResult
Write-Host "  ✅  Workload identity created." -ForegroundColor Green
Write-Host ""

Write-Host "  [2/2]  Creating an API-key credential provider '$providerName'..." -ForegroundColor Yellow
Write-Host "  Paste any placeholder API key value (this is just a demo secret)." -ForegroundColor Gray
$apiKeyValue = Read-Host "  Demo API key value"

if ([string]::IsNullOrWhiteSpace($apiKeyValue)) {
    $apiKeyValue = "demo-placeholder-key-12345"
    Write-Host "  Using placeholder value: $apiKeyValue" -ForegroundColor Gray
}

$providerResult = aws bedrock-agentcore-control create-api-key-credential-provider `
    --region $region `
    --name $providerName `
    --api-key $apiKeyValue `
    --output json 2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Host "  ❌  Failed to create credential provider." -ForegroundColor Red
    Write-Host $providerResult -ForegroundColor Red
    exit 1
}
Write-Host $providerResult
Write-Host "  ✅  Credential provider created." -ForegroundColor Green
Write-Host ""

Write-Host "  Set these for your CURRENT PowerShell session:" -ForegroundColor Yellow
Write-Host "    `$env:IDENTITY_WORKLOAD_NAME = `"$workloadName`"" -ForegroundColor Cyan
Write-Host "    `$env:IDENTITY_CREDENTIAL_PROVIDER = `"$providerName`"" -ForegroundColor Cyan
Write-Host ""

$env:IDENTITY_WORKLOAD_NAME = $workloadName
$env:IDENTITY_CREDENTIAL_PROVIDER = $providerName
Write-Host "  (Already set for THIS PowerShell window.)" -ForegroundColor Gray
Write-Host ""
Write-Host "  Also add both as deployment environment variables when you run" -ForegroundColor White
Write-Host "  deploy.ps1 (it will prompt you for them)." -ForegroundColor White
Write-Host ""
Write-Host "  Make sure your AgentCoreExecutionRole IAM role has permission" -ForegroundColor Gray
Write-Host "  for bedrock-agentcore:GetResourceApiKey / GetWorkloadAccessToken." -ForegroundColor Gray
Write-Host ""
