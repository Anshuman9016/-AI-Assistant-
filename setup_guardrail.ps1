# ╔══════════════════════════════════════════════════════════════════╗
# ║  setup_guardrail.ps1  —  Create a Bedrock Guardrail (Policy)    ║
# ╚══════════════════════════════════════════════════════════════════╝
#
# WHAT THIS CREATES
#   An Amazon Bedrock Guardrail with:
#     - A denied topics filter (example: competitor bashing / illegal
#       advice — edit topicsConfig.json to fit your own policy)
#     - Standard content filters (hate, insults, sexual, violence,
#       misconduct) set to a medium-high blocking threshold
#     - PII detection or default (blocks common PII types)
#
# WHAT YOU DO WITH THE OUTPUT
#   This script prints a Guardrail ID and version. Export both as
#   environment variables before running the agent, and pass them
#   to deploy.ps1 as deployment environment variables.
#
# RUN
#   .\setup_guardrail.ps1

Write-Host ""
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  Creating Bedrock Guardrail (Policy layer)" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

$region = "us-east-1"
$guardrailName = "ai-assistant-policy"

# ── Guardrail configuration (edit this to fit your own policy) ────
$topicsConfig = @'
{
  "topicsConfig": [
    {
      "name": "IllegalActivity",
      "definition": "Requests for help planning or carrying out illegal activities.",
      "examples": ["How do I break into a house without a key?"],
      "type": "DENY"
    }
  ]
}
'@
$topicsConfig | Out-File -FilePath "guardrail_topics.json" -Encoding utf8

$contentPolicyConfig = @'
{
  "filtersConfig": [
    { "type": "HATE",       "inputStrength": "HIGH",   "outputStrength": "HIGH" },
    { "type": "INSULTS",    "inputStrength": "MEDIUM", "outputStrength": "MEDIUM" },
    { "type": "SEXUAL",     "inputStrength": "HIGH",   "outputStrength": "HIGH" },
    { "type": "VIOLENCE",   "inputStrength": "HIGH",   "outputStrength": "HIGH" },
    { "type": "MISCONDUCT", "inputStrength": "HIGH",   "outputStrength": "HIGH" }
  ]
}
'@
$contentPolicyConfig | Out-File -FilePath "guardrail_content_policy.json" -Encoding utf8

$sensitiveInfoConfig = @'
{
  "piiEntitiesConfig": [
    { "type": "EMAIL",           "action": "ANONYMIZE" },
    { "type": "PHONE",           "action": "ANONYMIZE" },
    { "type": "US_SOCIAL_SECURITY_NUMBER", "action": "BLOCK" },
    { "type": "CREDIT_DEBIT_CARD_NUMBER",  "action": "BLOCK" }
  ]
}
'@
$sensitiveInfoConfig | Out-File -FilePath "guardrail_pii.json" -Encoding utf8

Write-Host "  Creating guardrail '$guardrailName'..." -ForegroundColor Yellow
Write-Host ""

$createResult = aws bedrock create-guardrail `
    --region $region `
    --name $guardrailName `
    --description "Policy layer for the AutoGen AI Assistant" `
    --topic-policy-config file://guardrail_topics.json `
    --content-policy-config file://guardrail_content_policy.json `
    --sensitive-information-policy-config file://guardrail_pii.json `
    --blocked-input-messaging "I'm not able to help with that request." `
    --blocked-outputs-messaging "I generated a response, but it didn't pass our content policy." `
    --output json 2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Host "  ❌  Failed to create guardrail." -ForegroundColor Red
    Write-Host $createResult -ForegroundColor Red
    exit 1
}

Write-Host $createResult
Write-Host ""

$parsed = $createResult | ConvertFrom-Json
$guardrailId = $parsed.guardrailId

if ($guardrailId) {
    Write-Host "  ✅  Guardrail created!" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Publishing a DRAFT version so it can be referenced..." -ForegroundColor Yellow

    $versionResult = aws bedrock create-guardrail-version `
        --region $region `
        --guardrail-identifier $guardrailId `
        --description "Initial version" `
        --output json 2>&1

    Write-Host $versionResult
    $versionParsed = $versionResult | ConvertFrom-Json
    $guardrailVersion = $versionParsed.version
    if (-not $guardrailVersion) { $guardrailVersion = "DRAFT" }

    Write-Host ""
    Write-Host "  Guardrail ID:      $guardrailId" -ForegroundColor Cyan
    Write-Host "  Guardrail Version: $guardrailVersion" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Set these for your CURRENT PowerShell session:" -ForegroundColor Yellow
    Write-Host "    `$env:GUARDRAIL_ID = `"$guardrailId`"" -ForegroundColor Cyan
    Write-Host "    `$env:GUARDRAIL_VERSION = `"$guardrailVersion`"" -ForegroundColor Cyan
    Write-Host ""

    $env:GUARDRAIL_ID = $guardrailId
    $env:GUARDRAIL_VERSION = $guardrailVersion
    Write-Host "  (Already set for THIS PowerShell window.)" -ForegroundColor Gray
} else {
    Write-Host "  ⚠   Could not parse the Guardrail ID automatically." -ForegroundColor Yellow
    Write-Host "  Find 'guardrailId' in the JSON output above and set it manually." -ForegroundColor White
}

Write-Host ""
Write-Host "  Tip: edit guardrail_topics.json / guardrail_content_policy.json /" -ForegroundColor Gray
Write-Host "  guardrail_pii.json and re-run this script to adjust the policy." -ForegroundColor Gray
Write-Host ""
