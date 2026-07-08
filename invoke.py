"""
╔══════════════════════════════════════════════════════════════════╗
║  invoke.py  —  Send One Question to the Deployed Agent          ║
╚══════════════════════════════════════════════════════════════════╝

HOW TO USE
  python invoke.py "What is machine learning?"
  python invoke.py "hello" -ActorId alice -SessionId morning-chat

SETUP (one time)
  Set AGENT_ARN below to the ARN printed by `agentcore launch`.
"""

import json
import sys
import uuid
import boto3
from botocore.exceptions import ClientError

# ─────────────────────────────────────────────────────────────────
# ⚙️  SET THIS VALUE
# ─────────────────────────────────────────────────────────────────
AGENT_ARN = "PASTE_YOUR_AGENT_ARN_HERE"
REGION    = "us-east-1"
# ─────────────────────────────────────────────────────────────────


def invoke_agent(prompt: str, actor_id: str, session_id: str) -> dict:
    """Send one prompt to the deployed AgentCore agent."""
    client  = boto3.client("bedrock-agentcore", region_name=REGION)
    payload = json.dumps({
        "prompt": prompt,
        "actor_id": actor_id,
        "session_id": session_id,
    }).encode("utf-8")

    try:
        response = client.invoke_agent_runtime(
            agentRuntimeArn=AGENT_ARN,
            runtimeSessionId=session_id,
            payload=payload,
            qualifier="DEFAULT",
        )
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        msg  = exc.response["Error"]["Message"]
        return {"response": f"AWS Error [{code}]: {msg}"}

    chunks = []
    for chunk in response.get("response", []):
        chunks.append(chunk.decode("utf-8") if isinstance(chunk, bytes) else str(chunk))

    raw = "".join(chunks)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"response": raw}


def main() -> None:
    if AGENT_ARN == "PASTE_YOUR_AGENT_ARN_HERE":
        print("\n⚠   Set AGENT_ARN in invoke.py first (see README.md).\n")
        sys.exit(1)

    args = sys.argv[1:]
    actor_id   = "default-user"
    session_id = str(uuid.uuid4())
    prompt_parts = []

    i = 0
    while i < len(args):
        if args[i] == "-ActorId" and i + 1 < len(args):
            actor_id = args[i + 1]
            i += 2
        elif args[i] == "-SessionId" and i + 1 < len(args):
            session_id = args[i + 1]
            i += 2
        else:
            prompt_parts.append(args[i])
            i += 1

    prompt = " ".join(prompt_parts).strip() or "Hello! What can you do?"

    print(f"\n  You   : {prompt}")
    result = invoke_agent(prompt, actor_id, session_id)
    print(f"  Agent : {result.get('response', '')}\n")


if __name__ == "__main__":
    main()
