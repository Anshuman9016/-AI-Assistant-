"""
╔══════════════════════════════════════════════════════════════════╗
║            AI ASSISTANT — AWS Bedrock AgentCore (Full)          ║
╠══════════════════════════════════════════════════════════════════╣
║  Framework  : Microsoft AutoGen AgentChat v0.4+                 ║
║  Model      : Claude 3.5 Sonnet  (via AWS Bedrock)              ║
║  Tools      : web_search (DuckDuckGo) + Gateway MCP tools       ║
║  Memory     : AgentCore Memory (short-term + long-term)         ║
║  Identity   : AgentCore Identity (credential vending demo)      ║
║  Policy     : Amazon Bedrock Guardrails (input + output check)  ║
║  Runtime    : AWS Bedrock AgentCore                             ║
╚══════════════════════════════════════════════════════════════════╝

WHAT'S NEW IN THIS VERSION
  The original agent had one tool (web_search) and no memory. This
  version adds all four remaining AgentCore building blocks used in
  this project, each one fully OPTIONAL and independently switchable
  by environment variable:

    MEMORY      → BEDROCK_AGENTCORE_MEMORY_ID   (memory_utils.py)
    GATEWAY     → GATEWAY_URL + Cognito vars     (gateway_utils.py)
    IDENTITY    → IDENTITY_WORKLOAD_NAME + ...   (identity_utils.py)
    GUARDRAILS  → GUARDRAIL_ID                   (guardrail_utils.py)

  If none of these are set, this file behaves exactly like the
  original single-tool agent — nothing breaks by leaving them off.

REQUEST LIFECYCLE (see README.md for the full diagram)
  1. Guardrail checks the incoming prompt (if configured)
  2. Memory is read: short-term events + long-term facts for this user
  3. An AutoGen AssistantAgent is built with:
       - web_search              (always available)
       - identity_lookup          (if Identity is configured)
       - Gateway MCP tools        (if Gateway is configured)
       - a system prompt containing the memory context
  4. The agent reasons, optionally calls tools, and answers
  5. Guardrail checks the outgoing answer (if configured)
  6. The turn is written back to Memory (if configured)

HOW TO RUN LOCALLY (for testing before deploying)
  python agent.py
  Then in a new PowerShell window:
  Invoke-RestMethod -Uri http://localhost:8080/invocations `
    -Method POST -ContentType "application/json" `
    -Body '{"prompt": "hello", "actor_id": "demo-user", "session_id": "demo-session"}'

HOW TO DEPLOY
  See README.md
"""

import logging
import os

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from autogen_agentchat.agents import AssistantAgent
from autogen_core.models import ModelInfo
from autogen_ext.models.anthropic import (
    AnthropicBedrockChatCompletionClient,
    BedrockInfo,
)
from ddgs import DDGS

import memory_utils
import gateway_utils
import identity_utils
import guardrail_utils

# ─────────────────────────────────────────────────────────────────
# Logging  (visible in CloudWatch after deployment)
# ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
log = logging.getLogger("ai_assistant")


# ═══════════════════════════════════════════════════════════════
# TOOL 1: web_search  (always available — no AWS setup required)
# ═══════════════════════════════════════════════════════════════
def web_search(query: str) -> str:
    """Search the internet for up-to-date information.

    Use this tool for current events, breaking news, live data
    (prices, scores, weather), or anything that may have changed
    recently.

    Args:
        query: A clear, specific search query string.

    Returns:
        Top search results as plain text (title, summary, URL).
    """
    log.info("🔍  web_search → %s", query)
    try:
        results = DDGS().text(query, max_results=5)
    except Exception as exc:
        log.warning("Search error: %s", exc)
        return f"Search failed: {exc}"

    if not results:
        return "No results found for that query."

    output = []
    for i, r in enumerate(results, 1):
        output.append(
            f"[Result {i}]\n"
            f"Title   : {r.get('title', 'N/A')}\n"
            f"Summary : {r.get('body', 'N/A')}\n"
            f"URL     : {r.get('href', 'N/A')}"
        )
    return "\n\n".join(output)


# ═══════════════════════════════════════════════════════════════
# TOOL 2: identity_lookup  (only useful if Identity is configured)
#
# Demonstrates AgentCore Identity by vending a short-lived API key
# for a downstream service on demand, rather than storing it as a
# plain environment variable.
# ═══════════════════════════════════════════════════════════════
def identity_lookup(reason: str) -> str:
    """Obtain a secure, short-lived credential for the demo third-party
    API via AgentCore Identity, and report whether it succeeded.

    Use this tool only if the user explicitly asks you to check or
    demonstrate secure credential access — it does not fetch general
    information on its own.

    Args:
        reason: A short note on why the credential is needed.

    Returns:
        A short status message — never the raw secret itself.
    """
    log.info("🔐  identity_lookup → %s", reason)

    if not identity_utils.identity_enabled():
        return (
            "Identity is not configured for this deployment. "
            "Set IDENTITY_WORKLOAD_NAME and IDENTITY_CREDENTIAL_PROVIDER "
            "and run setup_identity.ps1 to enable this."
        )

    api_key = identity_utils.get_identity_api_key()
    if api_key:
        # Never return the raw secret to the model / user — only confirm success.
        return "Successfully vended a short-lived credential via AgentCore Identity. Access confirmed."
    return "AgentCore Identity is configured, but credential vending failed. Check the execution role and provider setup."


# ─────────────────────────────────────────────────────────────────
# MODEL CLIENT: Claude on AWS Bedrock
# ─────────────────────────────────────────────────────────────────
def _build_model_client() -> AnthropicBedrockChatCompletionClient:
    model_id = os.environ.get(
        "BEDROCK_MODEL_ID",
        "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
    )
    region = os.environ.get("AWS_REGION", "us-east-1")
    log.info("Model client → %s | region: %s", model_id, region)

    return AnthropicBedrockChatCompletionClient(
        model=model_id,
        temperature=0.3,
        model_info=ModelInfo(
            vision=False,
            function_calling=True,
            json_output=False,
            family="claude",
            structured_output=False,
        ),
        bedrock_info=BedrockInfo(
            aws_access_key=os.environ.get("AWS_ACCESS_KEY_ID", ""),
            aws_secret_key=os.environ.get("AWS_SECRET_ACCESS_KEY", ""),
            aws_session_token=os.environ.get("AWS_SESSION_TOKEN", ""),
            aws_region=region,
        ),
    )


# ─────────────────────────────────────────────────────────────────
# AUTOGEN AGENT — assembled fresh per request, with whichever
# optional components are currently configured
# ─────────────────────────────────────────────────────────────────
async def _build_agent(memory_context: str) -> AssistantAgent:
    tools = [web_search, identity_lookup]

    # Gateway tools are async to load (they open an MCP connection)
    gateway_tools = await gateway_utils.load_gateway_tools()
    tools.extend(gateway_tools)

    base_prompt = """You are a friendly, knowledgeable AI Assistant.

GREETING BEHAVIOUR
  When the user says hello, hi, hey, good morning, etc. — respond warmly
  and enthusiastically, then ask how you can help them today.

ANSWERING QUESTIONS
  • For general knowledge you are confident about: answer directly.
  • For anything time-sensitive — current events, news, prices, sports
    results, recent software releases, live data — ALWAYS call the
    web_search tool first (or a Gateway search tool if one is available).
    Never guess on facts that could be outdated.
  • After searching, synthesise the results into a clear, concise answer.
    Mention where the information came from when helpful.
  • Use identity_lookup only if the user explicitly asks you to check
    or demonstrate secure credential access.
  • If MEMORY CONTEXT is provided below, use it naturally to personalise
    your answer (e.g. remembering the user's name or prior topics) —
    do not read it back to the user verbatim.

TONE
  Be helpful, clear, and concise. Keep answers easy to understand.
  Use bullet points or numbered lists when listing multiple items."""

    system_message = base_prompt
    if memory_context:
        system_message = f"{base_prompt}\n\n{memory_context}"

    return AssistantAgent(
        name="ai_assistant",
        model_client=_build_model_client(),
        tools=tools,
        reflect_on_tool_use=True,
        system_message=system_message,
    )


# ─────────────────────────────────────────────────────────────────
# AGENTCORE ENTRYPOINT
#
# Input  (JSON):  {"prompt": "...", "actor_id": "...", "session_id": "..."}
# Output (JSON):  {"response": "...", "actor_id": "...", "session_id": "..."}
#
# actor_id / session_id identify the USER and the CONVERSATION for
# Memory. If omitted, both default to "default" — memory will still
# work, but will treat every caller as the same single user.
# ─────────────────────────────────────────────────────────────────
app = BedrockAgentCoreApp()


@app.entrypoint
async def invoke(payload: dict, context=None) -> dict:
    prompt     = payload.get("prompt", "").strip()
    actor_id   = payload.get("actor_id", "default")
    session_id = payload.get("session_id", "default")

    if not prompt:
        return {
            "response": "Hi! I'm your AI Assistant. Send me a message and I'll do my best to help! 😊",
            "actor_id": actor_id,
            "session_id": session_id,
        }

    log.info("📨  actor=%s session=%s prompt=%.100s", actor_id, session_id, prompt)

    # ── 1. POLICY — check the incoming prompt ──────────────────
    input_check = guardrail_utils.check_text(prompt, source="INPUT")
    if not input_check.allowed:
        log.warning("Blocked incoming prompt: %s", input_check.reason)
        return {
            "response": "I'm not able to help with that request. Could you rephrase it?",
            "actor_id": actor_id,
            "session_id": session_id,
        }

    # ── 2. MEMORY — read what we know about this user ──────────
    memory_context = memory_utils.get_memory_context(actor_id, session_id, prompt)

    # ── 3. Build and run the agent ───────────────────────────────
    agent  = await _build_agent(memory_context)
    result = await agent.run(task=prompt)

    answer = ""
    for msg in reversed(result.messages):
        content = getattr(msg, "content", None)
        if isinstance(content, str) and content.strip():
            answer = content.strip()
            break

    if not answer:
        answer = "I wasn't able to generate a response. Please try again."

    # ── 4. POLICY — check the outgoing answer ───────────────────
    output_check = guardrail_utils.check_text(answer, source="OUTPUT")
    if not output_check.allowed:
        log.warning("Blocked outgoing answer: %s", output_check.reason)
        answer = output_check.filtered_text or (
            "I generated a response, but it didn't pass our content policy. "
            "Could you try asking in a different way?"
        )

    # ── 5. MEMORY — write this turn for next time ────────────────
    memory_utils.save_turn(actor_id, session_id, prompt, answer)

    log.info("✅  Response ready (%d chars)", len(answer))
    return {"response": answer, "actor_id": actor_id, "session_id": session_id}


# ─────────────────────────────────────────────────────────────────
# Local dev server
# ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    log.info("Starting local dev server on http://localhost:8080")
    log.info("Memory enabled:     %s", memory_utils.memory_enabled())
    log.info("Gateway enabled:    %s", gateway_utils.gateway_enabled())
    log.info("Identity enabled:   %s", identity_utils.identity_enabled())
    log.info("Guardrail enabled:  %s", guardrail_utils.guardrail_enabled())
    app.run()
