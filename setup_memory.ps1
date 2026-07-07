# ╔══════════════════════════════════════════════════════════════════╗
# ║  setup_memory.ps1  —  Create an AgentCore Memory resource       ║
# ╚══════════════════════════════════════════════════════════════════╝
#
# WHAT THIS CREATES
#   An AgentCore Memory resource with:
#     - Short-term storage (raw conversation events) — always on
#     - A long-term "semantic" strategy — extracts durable facts
#       about each user in the background after a session ends
#
# WHAT YOU DO WITH THE OUTPUT
#   This script prints a Memory ID. Save it — you will export it
#   as an environment variable before running the agent, and pass
#   it to `agentcore launch` as a deployment environment variable.
#
# RUN
#   .\setup_memory.ps1

Write-Host ""
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  Creating AgentCore Memory resource" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

$region = "us-east-1"
$memoryName = "ai_assistant_memory"

Write-Host "  Creating memory '$memoryName' in $region..." -ForegroundColor Yellow
Write-Host "  This includes a semantic long-term memory strategy." -ForegroundColor Gray
Write-Host ""

$strategyJson = '[{"semanticMemoryStrategy":{"name":"UserFactsStrategy","namespaces":["/facts/{actorId}"]}}]'

$createResult = aws bedrock-agentcore-control create-memory `
    --region $region `
    --name $memoryName `
    --description "Memory for the AutoGen AI Assistant (full build)" `
    --memory-strategies $strategyJson `
    --event-expiry-duration 90 `
    --output json 2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Host "  ❌  Failed to create memory." -ForegroundColor Red
    Write-Host $createResult -ForegroundColor Red
    Write-Host ""
    Write-Host "  Common causes:" -ForegroundColor White
    Write-Host "    - AWS CLI does not yet recognise 'bedrock-agentcore-control'" -ForegroundColor White
    Write-Host "      -> run: aws --version   (needs a recent version; update if old)" -ForegroundColor White
    Write-Host "    - Your IAM user/role lacks bedrock-agentcore-control:CreateMemory" -ForegroundColor White
    exit 1
}

Write-Host $createResult
Write-Host ""

# Try to extract the memory ID from the JSON response
$memoryId = ($createResult | ConvertFrom-Json).memory.id
if (-not $memoryId) {
    $memoryId = ($createResult | ConvertFrom-Json).memoryId
}

if ($memoryId) {
    Write-Host "  ✅  Memory created!" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Memory ID: $memoryId" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Set this for your CURRENT PowerShell session:" -ForegroundColor Yellow
    Write-Host "    `$env:BEDROCK_AGENTCORE_MEMORY_ID = `"$memoryId`"" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Also add it as a deployment environment variable when you run" -ForegroundColor White
    Write-Host "  deploy.ps1 (it will prompt you for it)." -ForegroundColor White
    Write-Host ""

    # Offer to set it immediately for this session
    $env:BEDROCK_AGENTCORE_MEMORY_ID = $memoryId
    Write-Host "  (Already set for THIS PowerShell window.)" -ForegroundColor Gray
} else {
    Write-Host "  ⚠   Could not automatically parse the Memory ID from the response." -ForegroundColor Yellow
    Write-Host "  Look for 'id' or 'memoryId' in the JSON output above and set it manually:" -ForegroundColor White
    Write-Host "    `$env:BEDROCK_AGENTCORE_MEMORY_ID = `"<paste-id-here>`"" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "  Note: it can take a minute or two for the memory resource to" -ForegroundColor Gray
Write-Host "  become ACTIVE. Check status with:" -ForegroundColor Gray
Write-Host "    aws bedrock-agentcore-control get-memory --region $region --memory-id $memoryId" -ForegroundColor Cyan
Write-Host ""
