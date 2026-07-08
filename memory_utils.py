"""
╔══════════════════════════════════════════════════════════════════╗
║  memory_utils.py  —  AgentCore Memory helpers                   ║
╠══════════════════════════════════════════════════════════════════╣
║  Gives the AutoGen agent persistent memory across sessions,      ║
║  using Amazon Bedrock AgentCore Memory.                          ║
╚══════════════════════════════════════════════════════════════════╝

WHAT THIS ADDS
  Without this file, the agent is stateless: every request starts
  from zero, even from the same returning user.

  With this file wired into agent.py, the agent gains two layers
  of recall:

  1. SHORT-TERM MEMORY
     The raw conversation events from the user's most recent
     session. Available immediately (no delay).

  2. LONG-TERM MEMORY
     Facts extracted from past conversations by AgentCore's
     background extraction job (semantic memory). This becomes
     available a few minutes AFTER a conversation happened, not
     instantly — AgentCore needs time to process and summarise it.

HOW IT IS WIRED IN
  agent.py calls:
      context = get_memory_context(actor_id, session_id, current_prompt)
  before building the AutoGen system_message, and calls:
      save_turn(actor_id, session_id, user_prompt, agent_reply)
  after every response, so the next session can recall it.

REQUIRED ENVIRONMENT VARIABLE
  BEDROCK_AGENTCORE_MEMORY_ID
      The Memory resource ID created by setup_memory.ps1 or by
      `agentcore configure` when memory is enabled.

  If this variable is not set, every function in this file becomes
  a safe no-op — the agent still runs, it just has no memory.
"""

import logging
import os
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

log = logging.getLogger("memory_utils")

REGION    = os.environ.get("AWS_REGION", "us-east-1")
MEMORY_ID = os.environ.get("BEDROCK_AGENTCORE_MEMORY_ID", "")

_client = None


def _get_client():
    """Lazily create the bedrock-agentcore data-plane client."""
    global _client
    if _client is None:
        _client = boto3.client("bedrock-agentcore", region_name=REGION)
    return _client


def memory_enabled() -> bool:
    """Return True if a Memory resource has been configured."""
    return bool(MEMORY_ID)


# ─────────────────────────────────────────────────────────────────
# READ — short-term memory (most recent prior session's events)
# ─────────────────────────────────────────────────────────────────
def get_recent_events(actor_id: str, max_sessions: int = 1, max_events: int = 10) -> list[str]:
    """Return recent conversation turns for this user, most recent first.

    Reads the user's most recent previous session(s) via list_sessions
    and list_events. Returns a flat list of human-readable turn strings.
    """
    if not memory_enabled():
        return []

    client = _get_client()
    turns: list[str] = []

    try:
        sessions_resp = client.list_sessions(
            memoryId=MEMORY_ID,
            actorId=actor_id,
            maxResults=max_sessions,
        )
        sessions = sessions_resp.get("sessionSummaries", [])

        for session in sessions:
            session_id = session.get("sessionId")
            if not session_id:
                continue

            events_resp = client.list_events(
                memoryId=MEMORY_ID,
                actorId=actor_id,
                sessionId=session_id,
                maxResults=max_events,
            )
            for event in events_resp.get("events", []):
                payload = event.get("payload", [])
                for item in payload:
                    conv = item.get("conversational", {})
                    role = conv.get("role", "")
                    text = conv.get("content", {}).get("text", "")
                    if text:
                        turns.append(f"{role}: {text}")

    except ClientError as exc:
        log.warning("Could not read short-term memory: %s", exc)
    except Exception as exc:
        log.warning("Unexpected error reading short-term memory: %s", exc)

    return turns


# ─────────────────────────────────────────────────────────────────
# READ — long-term memory (semantic facts extracted about the user)
# ─────────────────────────────────────────────────────────────────
def get_long_term_facts(actor_id: str, query: str, max_results: int = 5) -> list[str]:
    """Return semantically relevant facts previously extracted about this user.

    Uses retrieve_memory_records with the current prompt as the search
    query. Results only appear once AgentCore's background extraction
    job has processed a prior session (typically a few minutes later).
    """
    if not memory_enabled():
        return []

    client = _get_client()
    facts: list[str] = []

    try:
        resp = client.retrieve_memory_records(
            memoryId=MEMORY_ID,
            namespace=f"/facts/{actor_id}",
            searchCriteria={"searchQuery": query, "topK": max_results},
        )
        for record in resp.get("memoryRecordSummaries", []):
            content = record.get("content", {}).get("text", "")
            if content:
                facts.append(content)

    except ClientError as exc:
        log.warning("Could not read long-term memory: %s", exc)
    except Exception as exc:
        log.warning("Unexpected error reading long-term memory: %s", exc)

    return facts


# ─────────────────────────────────────────────────────────────────
# COMBINED — build a single context block for the system prompt
# ─────────────────────────────────────────────────────────────────
def get_memory_context(actor_id: str, session_id: str, current_prompt: str) -> str:
    """Build a short text block summarising what is known about this user.

    Returns an empty string if memory is disabled or nothing is found —
    safe to always concatenate onto the system prompt.
    """
    if not memory_enabled():
        return ""

    recent   = get_recent_events(actor_id)
    facts    = get_long_term_facts(actor_id, current_prompt)

    if not recent and not facts:
        return ""

    lines = ["--- MEMORY CONTEXT (do not repeat this verbatim, use it naturally) ---"]

    if facts:
        lines.append("Known facts about this user:")
        for f in facts:
            lines.append(f"  - {f}")

    if recent:
        lines.append("Recent conversation history:")
        for turn in recent[-6:]:
            lines.append(f"  {turn}")

    lines.append("--- END MEMORY CONTEXT ---")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────
# WRITE — store this turn so future sessions can recall it
# ─────────────────────────────────────────────────────────────────
def save_turn(actor_id: str, session_id: str, user_text: str, agent_text: str) -> None:
    """Write the user's message and the agent's reply to AgentCore Memory.

    Safe no-op if memory is disabled. Failures are logged, never raised,
    so a memory write issue never breaks the user-facing response.
    """
    if not memory_enabled():
        return

    client = _get_client()
    now = datetime.now(timezone.utc)

    try:
        client.create_event(
            memoryId=MEMORY_ID,
            actorId=actor_id,
            sessionId=session_id,
            eventTimestamp=now,
            payload=[
                {"conversational": {"role": "USER", "content": {"text": user_text}}},
                {"conversational": {"role": "ASSISTANT", "content": {"text": agent_text}}},
            ],
        )
    except ClientError as exc:
        log.warning("Could not write to memory: %s", exc)
    except Exception as exc:
        log.warning("Unexpected error writing to memory: %s", exc)
