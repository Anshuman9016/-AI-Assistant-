"""
╔══════════════════════════════════════════════════════════════════╗
║  chat.py  —  Full Interactive Chat with Your Deployed Agent     ║
╚══════════════════════════════════════════════════════════════════╝

HOW TO USE
  python chat.py
  python chat.py -ActorId alice

  Using the SAME -ActorId across separate runs of chat.py is what
  lets Memory recognise you as a returning user in a later session.

SETUP (one time)
  Set AGENT_ARN below to the ARN printed by `agentcore launch`.
"""

import json
import sys
import uuid
import boto3
from botocore.exceptions import ClientError

AGENT_ARN = "PASTE_YOUR_AGENT_ARN_HERE"
REGION    = "us-east-1"


def ask(prompt: str, actor_id: str, session_id: str) -> dict:
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
        return {"response": f"❌  AWS Error [{code}]: {msg}"}
    except Exception as exc:
        return {"response": f"❌  Unexpected error: {exc}"}

    chunks = []
    for chunk in response.get("response", []):
        chunks.append(chunk.decode("utf-8") if isinstance(chunk, bytes) else str(chunk))

    raw = "".join(chunks)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"response": raw}


def print_banner(actor_id: str) -> None:
    print()
    print("  ╔══════════════════════════════════════════════════════════╗")
    print("  ║   AI Assistant — AutoGen + Claude, Memory/Gateway/       ║")
    print("  ║           Identity/Guardrails on AgentCore              ║")
    print("  ╚══════════════════════════════════════════════════════════╝")
    print()
    print(f"  Signed in as actor_id: {actor_id}")
    print("  Commands:  /help   /clear   exit")
    print()


def main() -> None:
    if AGENT_ARN == "PASTE_YOUR_AGENT_ARN_HERE":
        print("\n⚠   Set AGENT_ARN in chat.py first (see README.md).\n")
        sys.exit(1)

    actor_id = "default-user"
    args = sys.argv[1:]
    if "-ActorId" in args:
        idx = args.index("-ActorId")
        if idx + 1 < len(args):
            actor_id = args[idx + 1]

    print_banner(actor_id)

    session_id    = str(uuid.uuid4())
    message_count = 0

    while True:
        try:
            user_input = input(f"  You [{message_count + 1}]: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n  Goodbye! 👋")
            break

        if not user_input:
            continue

        if user_input.lower() in {"exit", "quit", "bye", "q"}:
            print("\n  Agent: Goodbye! Have a great day! 👋\n")
            break

        if user_input.lower() == "/help":
            print()
            print("  Agent: I can answer questions, search the internet,")
            print("         remember you across sessions (if Memory is on),")
            print("         and call Gateway-hosted tools (if Gateway is on).")
            print()
            continue

        if user_input.lower() == "/clear":
            session_id    = str(uuid.uuid4())
            message_count = 0
            print("\n  ✅  New session started (same actor_id, fresh session_id)\n")
            continue

        print("  Agent: ", end="", flush=True)
        result = ask(user_input, actor_id, session_id)
        print(result.get("response", ""))
        print()
        message_count += 1


if __name__ == "__main__":
    main()
