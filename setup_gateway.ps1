# ╔══════════════════════════════════════════════════════════════════╗
# ║  setup_gateway.ps1  —  Create an AgentCore Gateway + Lambda     ║
# ╚══════════════════════════════════════════════════════════════════╝
#
# WHAT THIS CREATES
#   1. An Amazon Cognito User Pool + App Client — Gateway requires
#      inbound requests to present a JWT bearer token, and Cognito
#      is the simplest way to issue one for testing.
#   2. A test user in that pool (used by gateway_utils.py to sign in
#      and obtain a token before calling Gateway).
#   3. An IAM execution role for the Lambda function.
#   4. The lambda/search_lambda.py function, zipped and deployed.
#   5. An AgentCore Gateway, configured with the Cognito pool as its
#      inbound JWT authorizer.
#   6. A Gateway Target that points at the Lambda function and
#      exposes it to the agent as an MCP tool ("gateway_search").
#
# This script performs several AWS operations end-to-end and can
# take a few minutes. Read the output at each step — if something
# fails partway through, you can safely re-run the script; steps
# that already exist will simply report so and continue.
#
# RUN
#   .\setup_gateway.ps1

Write-Host ""
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  Creating AgentCore Gateway (Cognito auth + Lambda target)" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

$region        = "us-east-1"
$poolName      = "ai-assistant-gateway-pool"
$clientName    = "ai-assistant-gateway-client"
$testUsername  = "gateway-test-user"
$testPassword  = "GatewayDemo!2024"
$lambdaName    = "ai-assistant-search-lambda"
$roleName      = "AIAssistantSearchLambdaRole"
$gatewayName   = "ai-assistant-gateway"
$targetName    = "gateway-search-target"

# ── 1. Cognito User Pool ───────────────────────────────────────────
Write-Host "  [1/6]  Creating Cognito User Pool..." -ForegroundColor Yellow
$poolResult = aws cognito-idp create-user-pool `
    --region $region `
    --pool-name $poolName `
    --output json 2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Host "  ❌  Failed to create user pool." -ForegroundColor Red
    Write-Host $poolResult -ForegroundColor Red
    exit 1
}
$poolId = ($poolResult | ConvertFrom-Json).UserPool.Id
Write-Host "  ✅  User Pool ID: $poolId" -ForegroundColor Green
Write-Host ""

# ── 2. App Client (with USER_PASSWORD_AUTH enabled) ────────────────
Write-Host "  [2/6]  Creating App Client..." -ForegroundColor Yellow
$clientResult = aws cognito-idp create-user-pool-client `
    --region $region `
    --user-pool-id $poolId `
    --client-name $clientName `
    --explicit-auth-flows "ALLOW_USER_PASSWORD_AUTH" "ALLOW_REFRESH_TOKEN_AUTH" `
    --output json 2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Host "  ❌  Failed to create app client." -ForegroundColor Red
    Write-Host $clientResult -ForegroundColor Red
    exit 1
}
$clientId = ($clientResult | ConvertFrom-Json).UserPoolClient.ClientId
Write-Host "  ✅  App Client ID: $clientId" -ForegroundColor Green
Write-Host ""

# ── 3. Test user ────────────────────────────────────────────────────
Write-Host "  [3/6]  Creating test user '$testUsername'..." -ForegroundColor Yellow
aws cognito-idp admin-create-user `
    --region $region `
    --user-pool-id $poolId `
    --username $testUsername `
    --message-action SUPPRESS `
    --output json 2>&1 | Out-Null

aws cognito-idp admin-set-user-password `
    --region $region `
    --user-pool-id $poolId `
    --username $testUsername `
    --password $testPassword `
    --permanent `
    --output json 2>&1 | Out-Null

Write-Host "  ✅  Test user ready (username: $testUsername)" -ForegroundColor Green
Write-Host ""

# ── 4. IAM role + Lambda function ──────────────────────────────────
Write-Host "  [4/6]  Creating Lambda execution role..." -ForegroundColor Yellow

$trustPolicy = '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}'
$trustPolicy | Out-File -FilePath "lambda_trust_policy.json" -Encoding ascii

$roleResult = aws iam create-role `
    --role-name $roleName `
    --assume-role-policy-document file://lambda_trust_policy.json `
    --output json 2>&1

if ($LASTEXITCODE -ne 0 -and $roleResult -notmatch "EntityAlreadyExists") {
    Write-Host "  ❌  Failed to create IAM role." -ForegroundColor Red
    Write-Host $roleResult -ForegroundColor Red
    exit 1
}
if ($roleResult -match "EntityAlreadyExists") {
    Write-Host "  ℹ   Role already exists — reusing it." -ForegroundColor Gray
} else {
    Write-Host "  ✅  IAM role created." -ForegroundColor Green
}

aws iam attach-role-policy `
    --role-name $roleName `
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole `
    --output json 2>&1 | Out-Null

Write-Host "  Waiting 10s for role propagation..." -ForegroundColor Gray
Start-Sleep -Seconds 10

$accountId = (aws sts get-caller-identity --query Account --output text)
$roleArn = "arn:aws:iam::$accountId:role/$roleName"
Write-Host "  Role ARN: $roleArn" -ForegroundColor Gray
Write-Host ""

Write-Host "  [5/6]  Packaging and deploying the Lambda function..." -ForegroundColor Yellow

if (Test-Path "lambda_package") { Remove-Item -Recurse -Force "lambda_package" }
New-Item -ItemType Directory -Path "lambda_package" | Out-Null
Copy-Item "lambda\search_lambda.py" "lambda_package\"

Compress-Archive -Path "lambda_package\search_lambda.py" -DestinationPath "lambda_package.zip" -Force

$existingFn = aws lambda get-function --region $region --function-name $lambdaName 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ℹ   Lambda already exists — updating code..." -ForegroundColor Gray
    aws lambda update-function-code `
        --region $region `
        --function-name $lambdaName `
        --zip-file fileb://lambda_package.zip `
        --output json 2>&1 | Out-Null
} else {
    aws lambda create-function `
        --region $region `
        --function-name $lambdaName `
        --runtime python3.12 `
        --role $roleArn `
        --handler search_lambda.lambda_handler `
        --zip-file fileb://lambda_package.zip `
        --timeout 15 `
        --output json 2>&1 | Out-Null
}
Write-Host "  ✅  Lambda function deployed: $lambdaName" -ForegroundColor Green
Write-Host ""

$lambdaArn = "arn:aws:lambda:${region}:${accountId}:function:${lambdaName}"

# ── 6. AgentCore Gateway + Target ──────────────────────────────────
Write-Host "  [6/6]  Creating AgentCore Gateway..." -ForegroundColor Yellow

$authorizerConfig = @"
{
  "customJWTAuthorizer": {
    "allowedClients": ["$clientId"],
    "discoveryUrl": "https://cognito-idp.$region.amazonaws.com/$poolId/.well-known/openid-configuration"
  }
}
"@
$authorizerConfig | Out-File -FilePath "gateway_authorizer.json" -Encoding utf8

$gatewayResult = aws bedrock-agentcore-control create-gateway `
    --region $region `
    --name $gatewayName `
    --protocol-type MCP `
    --authorizer-type CUSTOM_JWT `
    --authorizer-configuration file://gateway_authorizer.json `
    --output json 2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Host "  ❌  Failed to create Gateway." -ForegroundColor Red
    Write-Host $gatewayResult -ForegroundColor Red
    exit 1
}
Write-Host $gatewayResult
$gatewayParsed = $gatewayResult | ConvertFrom-Json
$gatewayId  = $gatewayParsed.gatewayId
$gatewayUrl = $gatewayParsed.gatewayUrl
Write-Host "  ✅  Gateway created: $gatewayId" -ForegroundColor Green
Write-Host ""

Write-Host "  Creating Gateway Target (Lambda: $lambdaName)..." -ForegroundColor Yellow

$toolSchema = @'
{
  "tools": [
    {
      "name": "gateway_search",
      "description": "Search the internet for current information via the Gateway-hosted Lambda backend.",
      "inputSchema": {
        "type": "object",
        "properties": {
          "query": { "type": "string", "description": "The search query." }
        },
        "required": ["query"]
      }
    }
  ]
}
'@
$toolSchema | Out-File -FilePath "gateway_tool_schema.json" -Encoding utf8

$targetConfig = @"
{
  "lambdaConfiguration": {
    "lambdaArn": "$lambdaArn"
  }
}
"@
$targetConfig | Out-File -FilePath "gateway_target_config.json" -Encoding utf8

$targetResult = aws bedrock-agentcore-control create-gateway-target `
    --region $region `
    --gateway-identifier $gatewayId `
    --name $targetName `
    --target-configuration file://gateway_target_config.json `
    --tool-schema file://gateway_tool_schema.json `
    --output json 2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Host "  ❌  Failed to create Gateway Target." -ForegroundColor Red
    Write-Host $targetResult -ForegroundColor Red
    exit 1
}
Write-Host $targetResult
Write-Host "  ✅  Gateway Target created." -ForegroundColor Green
Write-Host ""

# Give the Lambda permission to be invoked by Gateway
aws lambda add-permission `
    --region $region `
    --function-name $lambdaName `
    --statement-id "AllowGatewayInvoke" `
    --action "lambda:InvokeFunction" `
    --principal "bedrock-agentcore.amazonaws.com" `
    --output json 2>&1 | Out-Null

# ── Summary ─────────────────────────────────────────────────────────
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  Gateway setup complete!" -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Set these for your CURRENT PowerShell session:" -ForegroundColor Yellow
Write-Host "    `$env:GATEWAY_URL = `"$gatewayUrl`"" -ForegroundColor Cyan
Write-Host "    `$env:GATEWAY_COGNITO_USER_POOL_ID = `"$poolId`"" -ForegroundColor Cyan
Write-Host "    `$env:GATEWAY_COGNITO_CLIENT_ID = `"$clientId`"" -ForegroundColor Cyan
Write-Host "    `$env:GATEWAY_COGNITO_USERNAME = `"$testUsername`"" -ForegroundColor Cyan
Write-Host "    `$env:GATEWAY_COGNITO_PASSWORD = `"$testPassword`"" -ForegroundColor Cyan
Write-Host ""

$env:GATEWAY_URL = $gatewayUrl
$env:GATEWAY_COGNITO_USER_POOL_ID = $poolId
$env:GATEWAY_COGNITO_CLIENT_ID = $clientId
$env:GATEWAY_COGNITO_USERNAME = $testUsername
$env:GATEWAY_COGNITO_PASSWORD = $testPassword
Write-Host "  (Already set for THIS PowerShell window.)" -ForegroundColor Gray
Write-Host ""
Write-Host "  Also add all five as deployment environment variables when you" -ForegroundColor White
Write-Host "  run deploy.ps1 (it will prompt you for them)." -ForegroundColor White
Write-Host ""
Write-Host "  Clean up temp files..." -ForegroundColor Gray
Remove-Item -Force "lambda_trust_policy.json","gateway_authorizer.json","gateway_tool_schema.json","gateway_target_config.json" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "lambda_package" -ErrorAction SilentlyContinue
Write-Host ""
