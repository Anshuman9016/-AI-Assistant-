# AI Assistant (Full Build) — Complete Windows PowerShell Guide
### Microsoft AutoGen + Claude on AWS Bedrock AgentCore
### Now with Memory, Gateway, Identity, and Guardrails (Policy)

> ⚠️ **WINDOWS POWERSHELL ONLY** — every command in this guide is written for
> Windows PowerShell. Do not use Command Prompt (cmd.exe) or bash.

---

## What's New in This Build

Your original agent had one capability: a built-in internet search tool.
This build adds the four remaining AgentCore building blocks on top of it —
**every one of them is optional and independently switchable**. If you skip
a setup script, that feature is simply off; the agent still runs fine.

```
╔══════════════════════════════════════════════════════════╗
║                  AI Assistant (Full)                      ║
╠══════════════════════════════════════════════════════════╣
║  ✅  Says hello, answers questions                        ║
║  ✅  Built-in internet search (always on)                 ║
║  🆕  MEMORY      — remembers you across sessions          ║
║  🆕  GATEWAY     — calls tools via a Lambda-backed MCP    ║
║  🆕  IDENTITY    — secure, short-lived credential vending  ║
║  🆕  GUARDRAILS  — policy checks on input AND output       ║
╚══════════════════════════════════════════════════════════╝
```

---

## Your Project Files

```
ai_assistant_full\
│
├── agent.py                ← Main agent — wires up all four features
├── memory_utils.py          ← Memory read/write helpers
├── gateway_utils.py         ← Gateway MCP tool loader
├── identity_utils.py        ← Identity credential-vending helpers
├── guardrail_utils.py       ← Guardrails (Policy) enforcement helpers
│
├── lambda\
│   └── search_lambda.py     ← Backend Lambda that Gateway calls
│
├── requirements.txt         ← Python packages (includes MCP support)
│
├── setup.ps1                ← One-click base environment setup
├── setup_memory.ps1         ← Creates the AgentCore Memory resource
├── setup_guardrail.ps1      ← Creates the Bedrock Guardrail (Policy)
├── setup_identity.ps1       ← Creates the Identity workload + provider
├── setup_gateway.ps1        ← Creates Cognito auth + Lambda + Gateway
├── deploy.ps1                ← Deploys agent.py, passing through
│                                whichever features you've configured
│
├── invoke.py                ← Ask the deployed agent one question
├── chat.py                  ← Full interactive chat client
├── test_local.py            ← Local pre-deployment test suite
├── test_memory.py           ← Feature test suite (deployed agent)
│
└── README.md                ← This guide
```

---

## How the Four New Features Fit Together

```
                     ┌─────────────────────────────┐
                     │   Incoming request           │
                     │   {prompt, actor_id,          │
                     │    session_id}                │
                     └──────────────┬────────────────┘
                                    ▼
                     ┌─────────────────────────────┐
                     │ 1. GUARDRAIL check (INPUT)   │  ← Policy
                     └──────────────┬────────────────┘
                                    ▼
                     ┌─────────────────────────────┐
                     │ 2. MEMORY read                │  ← short-term +
                     │    (facts about this user)    │     long-term
                     └──────────────┬────────────────┘
                                    ▼
                     ┌─────────────────────────────┐
                     │ 3. AutoGen AssistantAgent      │
                     │    tools:                      │
                     │      • web_search (built-in)   │
                     │      • identity_lookup          │ ← Identity
                     │      • Gateway MCP tools        │ ← Gateway
                     └──────────────┬────────────────┘
                                    ▼
                     ┌─────────────────────────────┐
                     │ 4. GUARDRAIL check (OUTPUT)    │  ← Policy
                     └──────────────┬────────────────┘
                                    ▼
                     ┌─────────────────────────────┐
                     │ 5. MEMORY write (save turn)     │
                     └──────────────┬────────────────┘
                                    ▼
                     ┌─────────────────────────────┐
                     │   Response returned            │
                     └─────────────────────────────┘
```

---

## BEFORE YOU START

| Item | Where to get it |
|---|---|
| AWS account (free tier works) | [aws.amazon.com](https://aws.amazon.com) |
| Python 3.10+ | [python.org/downloads](https://python.org/downloads) |
| AWS CLI (recent version) | [awscli.amazonaws.com/AWSCLIV2.msi](https://awscli.amazonaws.com/AWSCLIV2.msi) |
| PowerShell 5+ | Already on Windows 10/11 |

> Some commands in this guide use the newer `bedrock-agentcore-control` AWS
> CLI service model. If a command reports it isn't recognised, update the
> AWS CLI to the latest version and try again.

---

## PART 1 — Base Setup

### Step 1.1 — Allow scripts to run (one time)

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Step 1.2 — Configure AWS credentials

```powershell
aws configure
```

Enter your Access Key ID, Secret Access Key, region (`us-east-1`), format (`json`).

Verify:

```powershell
aws sts get-caller-identity
```

### Step 1.3 — Enable Claude in Bedrock

1. Open the [Bedrock Console](https://console.aws.amazon.com/bedrock) → confirm region is **us-east-1**
2. **Model access** → enable **Claude 3.5 Sonnet v2** → **Save changes**
3. Wait until status shows **Access granted**

### Step 1.4 — Create the IAM execution role

```powershell
aws iam create-role `
  --role-name AgentCoreExecutionRole `
  --assume-role-policy-document '{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Principal\":{\"Service\":\"bedrock-agentcore.amazonaws.com\"},\"Action\":\"sts:AssumeRole\"}]}'

aws iam attach-role-policy `
  --role-name AgentCoreExecutionRole `
  --policy-arn arn:aws:iam::aws:policy/AmazonBedrockFullAccess

aws iam attach-role-policy `
  --role-name AgentCoreExecutionRole `
  --policy-arn arn:aws:iam::aws:policy/CloudWatchLogsFullAccess
```

This role also needs permission to use Memory, Identity, and Guardrails.
Attach one more broad policy for this project (tighten later for production):

```powershell
aws iam attach-role-policy `
  --role-name AgentCoreExecutionRole `
  --policy-arn arn:aws:iam::aws:policy/AmazonBedrockAgentCoreFullAccess
```

Get the Role ARN (save it — you'll paste it into `deploy.ps1`):

```powershell
aws iam get-role --role-name AgentCoreExecutionRole --query Role.Arn --output text
```

### Step 1.5 — Project folder + install packages

```powershell
mkdir C:\ai_assistant_full
cd C:\ai_assistant_full
```

Copy all project files (including the `lambda\` folder) into this directory, then:

```powershell
.\setup.ps1
.venv\Scripts\Activate.ps1
```

---

## PART 2 — Setting Up Memory

Memory gives the agent short-term recall (the last session's raw
conversation) and long-term recall (semantically extracted facts about
each user, available a few minutes after a session ends).

```powershell
.\setup_memory.ps1
```

This prints a **Memory ID** and sets `$env:BEDROCK_AGENTCORE_MEMORY_ID`
for your current PowerShell window. Test it locally:

```powershell
python agent.py
```

In a second PowerShell window:

```powershell
$env:BEDROCK_AGENTCORE_MEMORY_ID = "<paste-memory-id>"   # if testing in a new window
Invoke-RestMethod -Uri http://localhost:8080/invocations `
  -Method POST -ContentType "application/json" `
  -Body '{"prompt": "My favourite colour is teal.", "actor_id": "demo-user", "session_id": "session-1"}'

Invoke-RestMethod -Uri http://localhost:8080/invocations `
  -Method POST -ContentType "application/json" `
  -Body '{"prompt": "What is my favourite colour?", "actor_id": "demo-user", "session_id": "session-2"}'
```

Short-term recall (same actor, different session) should work right away.
Long-term semantic recall becomes available a few minutes later, once
AgentCore's background extraction job has processed the first session.

---

## PART 3 — Setting Up Guardrails (Policy)

Guardrails enforces content policy independently of the agent's own
judgement — on both the incoming prompt and the outgoing answer.

```powershell
.\setup_guardrail.ps1
```

This creates a Guardrail with a denied-topics rule, standard content
filters, and PII detection, then prints a **Guardrail ID** and **Version**
and sets both as environment variables for your session.

Edit `guardrail_topics.json`, `guardrail_content_policy.json`, or
`guardrail_pii.json` (created by the script) to adjust the policy, then
re-run `setup_guardrail.ps1` to update it.

Test locally:

```powershell
Invoke-RestMethod -Uri http://localhost:8080/invocations `
  -Method POST -ContentType "application/json" `
  -Body '{"prompt": "What is the capital of Japan?"}'
```

This should pass straight through. Anything matching your denied-topics
or content-filter rules will be blocked with a polite refusal instead of
reaching — or leaving — the model.

---

## PART 4 — Setting Up Identity

Identity lets the agent request a short-lived credential for a
downstream service at the moment it's needed, instead of storing a
secret in a plain environment variable.

```powershell
.\setup_identity.ps1
```

You'll be prompted for a placeholder API key value (any string is fine —
this demonstrates the vending pattern, not a real integration). This
prints a workload name and provider name and sets both as environment
variables for your session.

Test locally by asking the agent to use the `identity_lookup` tool:

```powershell
Invoke-RestMethod -Uri http://localhost:8080/invocations `
  -Method POST -ContentType "application/json" `
  -Body '{"prompt": "Can you check if secure credential access is working?"}'
```

---

## PART 5 — Setting Up Gateway

Gateway lets the agent call tools that live behind a Lambda function (or
API), instead of writing the tool logic directly in Python. This script
does the most work: it creates a Cognito user pool for authentication, a
Lambda function, and the Gateway + Gateway Target that connects them.

```powershell
.\setup_gateway.ps1
```

This takes a few minutes and prints five environment variables at the
end (Gateway URL + four Cognito values), setting them for your session.

Test locally — the agent should now have a second, Gateway-hosted search
tool alongside its built-in one:

```powershell
python agent.py
```

```powershell
Invoke-RestMethod -Uri http://localhost:8080/invocations `
  -Method POST -ContentType "application/json" `
  -Body '{"prompt": "What are the latest AWS announcements?"}'
```

Check the `agent.py` terminal log — you'll see whether Claude used the
built-in `web_search` tool, the Gateway tool, or both.

> **Note:** the Lambda backend in `lambda/search_lambda.py` uses a
> lightweight, dependency-free DuckDuckGo HTML fetch (since packaging the
> `ddgs` library as a Lambda layer is extra setup). Its purpose is to
> demonstrate the Gateway pattern end-to-end; for production, replace it
> with a call to your actual internal API or a licensed search provider.

>>>>>>To isolate and test the Gateway tool specifically (and ensure Claude doesn't just fall back to using its built-in local web_search tool), you can use two tactical testing approaches.

Method 1: The "Direct Route" (Test the Lambda Gateway Directly)
You can bypass the LLM completely and test your newly deployed Gateway target directly via your PowerShell terminal. This proves that your network routing, Cognito user pool authentication, and the lambda/search_lambda.py script are working properly end-to-end.

After running .\setup_gateway.ps1, your terminal sessions store the environment variables. Use this block to hit the gateway:

PowerShell
# 1. Grab your Cognito Token from the session environment variables
(((((($headers = @{
    Authorization = "Bearer $env:COGNITO_ACCESS_TOKEN"
}

# 2. Build the payload matching what the Gateway target expects
$body = @{
    query = "Latest AWS Bedrock announcements"
} | ConvertTo-Json

# 3. Invoke your live Gateway URL directly
Invoke-RestMethod -Uri "$env:GATEWAY_URL/search" -Method POST -Headers $headers -ContentType "application/json" -Body $body))))))
What to look for: If successful, this bypassing method will return the direct, raw HTML text payload fetched by the lightweight DuckDuckGo scraper backend residing in your Lambda.

Method 2: Force the Agent to use the Gateway (Prompt Engineering)
If you want to test it through the agent.py local invocation loop (http://localhost:8080/invocations), you have to explicitly guide Claude's routing selection.

Because LLMs optimize for efficiency, if you give them a generic prompt like "What are the latest announcements?", they might choose the local tool to save cross-network processing latency.

Change your invocation payload to force a specific routing path like this:

PowerShell
(((((((Invoke-RestMethod -Uri http://localhost:8080/invocations `
  -Method POST -ContentType "application/json" `
  -Body '{"prompt": "Using strictly your external AWS Lambda-hosted Gateway search tool, tell me what the latest AWS announcements are."}')))))))
Verification (Checking your logs)
While running Method 2, watch the terminal where python agent.py is executing.

If it uses the local tool, you will see a logging footprint from your local workspace python scripts.

If it successfully hits the gateway, your terminal log will print an outbound network trace displaying an API handshake routing toward your GATEWAY_URL.<<<<<<

---

## PART 6 — Deploying Everything Together

Once you've run whichever setup scripts you want (all four, or just
some), deploy with:

```powershell
.\deploy.ps1
```

It will:
1. Ask for your IAM Role ARN
2. Detect which feature environment variables are set in your current
   PowerShell session
3. Run `agentcore configure` with those variables attached to the
   deployment
4. Run `agentcore launch`
5. Print the Agent ARN

> **Important:** environment variables you set with `$env:NAME = "value"`
> only last for your current PowerShell window. If you set up Memory,
> Guardrails, Identity, and Gateway in **separate** windows, either:
> - re-run each `setup_*.ps1` script once more in the **same** window
>   right before running `deploy.ps1`, or
> - manually set all the variables in one window before deploying:
>
> ```powershell
> $env:BEDROCK_AGENTCORE_MEMORY_ID = "<memory-id>"
> $env:GUARDRAIL_ID = "<guardrail-id>"
> $env:GUARDRAIL_VERSION = "<guardrail-version>"
> $env:IDENTITY_WORKLOAD_NAME = "<workload-name>"
> $env:IDENTITY_CREDENTIAL_PROVIDER = "<provider-name>"
> $env:GATEWAY_URL = "<gateway-url>"
> $env:GATEWAY_COGNITO_USER_POOL_ID = "<pool-id>"
> $env:GATEWAY_COGNITO_CLIENT_ID = "<client-id>"
> $env:GATEWAY_COGNITO_USERNAME = "<username>"
> $env:GATEWAY_COGNITO_PASSWORD = "<password>"
> .\deploy.ps1
> ```

Set your Agent ARN in the three client files:

```powershell
notepad invoke.py
notepad chat.py
notepad test_memory.py
```

---

## PART 7 — Using the Deployed Agent

### Full interactive chat

```powershell
python chat.py
python chat.py -ActorId alice
```

Using the same `-ActorId` across separate runs is what lets Memory
recognise you as a returning user.

### One-off question

```powershell
python invoke.py "What is machine learning?"
python invoke.py "hello" -ActorId alice -SessionId morning-chat
```

### Full feature test suite

```powershell
python test_memory.py
```

Runs 6 automated tests: greeting, multi-turn conversation, actor
isolation, cross-session memory, Identity tool availability, and
Guardrail pass-through.

---

## PART 8 — Command Reference

```powershell
# ── One-time setup ────────────────────────────────────────────
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
aws configure
.\setup.ps1
.venv\Scripts\Activate.ps1

# ── Optional feature setup (run any/all) ──────────────────────
.\setup_memory.ps1
.\setup_guardrail.ps1
.\setup_identity.ps1
.\setup_gateway.ps1

# ── Local testing ─────────────────────────────────────────────
python agent.py               # Window 1
python test_local.py          # Window 2

# ── Deploy ─────────────────────────────────────────────────────
.\deploy.ps1
agentcore status
agentcore logs

# ── Use the deployed agent ────────────────────────────────────
python chat.py
python invoke.py "your question"
python test_memory.py

# ── Clean up (stop AWS charges) ───────────────────────────────
agentcore remove
```

---

## PART 9 — Troubleshooting

### ❌ "bedrock-agentcore-control is not a recognized service"
Your AWS CLI is out of date. Reinstall the latest version:
[https://awscli.amazonaws.com/AWSCLIV2.msi](https://awscli.amazonaws.com/AWSCLIV2.msi)

### ❌ Memory / Guardrail / Identity / Gateway setup script fails with "AccessDenied"
Your AWS user/role needs broader permissions to create these resources
during setup (this is separate from the agent's own execution role).
For a personal test account, temporarily attach `AdministratorAccess`
to your IAM user while running the `setup_*.ps1` scripts, then remove
it afterwards.

### ❌ Agent responds but ignores Memory / Gateway / Identity / Guardrails
Double check the relevant environment variables are set in the **same**
PowerShell window you're running `python agent.py` from — `$env:` values
don't carry over between windows. Re-run the relevant `setup_*.ps1`
script in that window, or set the variables manually (Part 6).

### ❌ "autogen-ext[mcp] is not installed" warning in logs
Gateway tools need the MCP extra:
```powershell
pip install "autogen-ext[mcp]"
```
This is already included in `requirements.txt` / `setup.ps1` — re-run
`.\setup.ps1` if you installed packages a different way.

### ❌ Gateway calls fail with a Cognito authentication error
Check that `GATEWAY_COGNITO_USERNAME` / `GATEWAY_COGNITO_PASSWORD` match
exactly what `setup_gateway.ps1` printed. If you changed the password
policy on the User Pool afterwards, re-run
`aws cognito-idp admin-set-user-password` with a compliant password.

### ❌ Guardrail blocks something it shouldn't (or allows something it shouldn't)
Edit `guardrail_topics.json`, `guardrail_content_policy.json`, or
`guardrail_pii.json`, then re-run `.\setup_guardrail.ps1` to update the
existing Guardrail with your changes.

### ❌ "on-demand throughput isn't supported for this model"
In `agent.py`, change the default model ID from the cross-region
inference profile to the direct model ID:
```python
"anthropic.claude-3-5-sonnet-20241022-v2:0"
```

### ❌ Deployment succeeds but agent.py errors on start with an import error
Make sure `.venv\Scripts\Activate.ps1` was run before `pip install -r
requirements.txt`, and that the same virtual environment is active when
you run `python agent.py`.

---

## PART 10 — Clean Up (Stop AWS Charges)

```powershell
agentcore remove
```

Then remove the supporting resources you created (adjust names if you
changed them):

```powershell
aws lambda delete-function --function-name ai-assistant-search-lambda --region us-east-1
aws iam detach-role-policy --role-name AIAssistantSearchLambdaRole --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
aws iam delete-role --role-name AIAssistantSearchLambdaRole
aws cognito-idp delete-user-pool --user-pool-id <your-pool-id> --region us-east-1
aws bedrock-agentcore-control delete-gateway --gateway-identifier <your-gateway-id> --region us-east-1
aws bedrock-agentcore-control delete-memory --memory-id <your-memory-id> --region us-east-1
aws bedrock delete-guardrail --guardrail-identifier <your-guardrail-id> --region us-east-1
```

---

## Quick Start Card

```powershell
# First time
cd C:\ai_assistant_full
.\setup.ps1
.venv\Scripts\Activate.ps1

# Optional features (pick any)
.\setup_memory.ps1
.\setup_guardrail.ps1
.\setup_identity.ps1
.\setup_gateway.ps1

# Test locally
python agent.py                  # Window 1
python test_local.py              # Window 2

# Deploy (same window as the setup_*.ps1 scripts above!)
.\deploy.ps1

# Set AGENT_ARN
notepad invoke.py
notepad chat.py
notepad test_memory.py

# Use it
python chat.py
python test_memory.py

# Clean up
agentcore remove
```
