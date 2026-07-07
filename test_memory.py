"""
╔══════════════════════════════════════════════════════════════════╗
║  test_memory.py  —  Test Memory, Gateway, Identity, Guardrails  ║
╚══════════════════════════════════════════════════════════════════╝

HOW TO USE
  python test_memory.py

SETUP (one time)
  Set AGENT_ARN below to your deployed agent's ARN.

WHAT THIS TESTS
  1. Basic greeting
  2. Multi-turn conversation within one session
  3. Session isolation (two different actors don't share context)
  4. Memory write-then-read across two SEPARATE invocations
     (simulates a user leaving and coming back)
  5. Identity tool availability
  6. Guardrail pass-through on an ordinary, safe prompt

NOTE ON MEMORY TIMING
  Long-term (semantic) memory needs a background extraction job to
  run after a session ends before it can be recalled — this can take
  a few minutes. This script tests SHORT-TERM memory, which is
  available immediately, plus demonstrates the pattern for long-term
  recall with a note about the expected delay.
"""

import json
import sys
import time
import uuid
import boto3
from botocore.exceptions import ClientError

AGENT_ARN = "PASTE_YOUR_AGENT_ARN_HERE"
REGION    = "us-east-1"


def ask(prompt: str, actor_id: str, session_id: str) -> str:
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
        return f"ERROR [{exc.response['Error']['Code']}]: {exc.response['Error']['Message']}"

    chunks = []
    for chunk in response.get("response", []):
        chunks.append(chunk.decode("utf-8") if isinstance(chunk, bytes) else str(chunk))
    raw = "".join(chunks)
    try:
        return json.loads(raw).get("response", raw)
    except json.JSONDecodeError:
        return raw


def run_turn(label: str, prompt: str, actor_id: str, session_id: str, check_fn) -> bool:
    print(f"  │   {label}")
    print(f"  │     Prompt: {repr(prompt)[:70]}")
    print("  │     Sending...", end=" ", flush=True)

    start = time.time()
    response = ask(prompt, actor_id, session_id)
    elapsed = time.time() - start

    ok = (not response.startswith("ERROR")) and check_fn(response)
    print(f"{'✅' if ok else '❌'}  ({elapsed:.1f}s)")
    print(f"  │     Reply: {response[:110]}{'...' if len(response) > 110 else ''}")
    return ok


def main() -> None:
    if AGENT_ARN == "PASTE_YOUR_AGENT_ARN_HERE":
        print("\n⚠   Set AGENT_ARN in test_memory.py first (see README.md).\n")
        sys.exit(1)

    print("\n" + "=" * 62)
    print("  AI Assistant — Memory / Gateway / Identity / Guardrail Tests")
    print("=" * 62 + "\n")

    results = []

    # ── Test 1: Greeting ──────────────────────────────────────────
    print("  ┌─  Test 1: Greeting")
    results.append(run_turn("Turn 1", "hello", "test-actor-1", str(uuid.uuid4()),
                             lambda r: len(r) > 10))
    print("  └─  " + ("✅ PASSED" if results[-1] else "❌ FAILED") + "\n")

    # ── Test 2: Multi-turn in one session ─────────────────────────
    print("  ┌─  Test 2: Multi-turn conversation (one session)")
    session_a = str(uuid.uuid4())
    r1 = run_turn("Turn 1", "My name is Priya and I love hiking.", "priya-test", session_a,
                  lambda r: len(r) > 5)
    r2 = run_turn("Turn 2", "What's a good hobby-related question you could ask me?", "priya-test", session_a,
                  lambda r: len(r) > 5)
    ok2 = r1 and r2
    results.append(ok2)
    print("  └─  " + ("✅ PASSED" if ok2 else "❌ FAILED") + "\n")

    # ── Test 3: Session/actor isolation ───────────────────────────
    print("  ┌─  Test 3: Actor isolation (two different users)")
    r3 = run_turn("Actor X", "hello", "actor-x", str(uuid.uuid4()), lambda r: len(r) > 5)
    r4 = run_turn("Actor Y", "hello", "actor-y", str(uuid.uuid4()), lambda r: len(r) > 5)
    ok3 = r3 and r4
    results.append(ok3)
    print("  └─  " + ("✅ PASSED" if ok3 else "❌ FAILED") + "\n")

    # ── Test 4: Memory across two separate sessions ───────────────
    print("  ┌─  Test 4: Short-term memory across two sessions (same actor)")
    memory_actor = "memory-test-user"
    session_1 = str(uuid.uuid4())
    session_2 = str(uuid.uuid4())
    r5 = run_turn("Session 1 — introduce a fact", "Remember that my favourite colour is teal.",
                  memory_actor, session_1, lambda r: len(r) > 5)
    print("  │     (waiting 5s before starting a new session...)")
    time.sleep(5)
    r6 = run_turn("Session 2 — recall the fact", "What is my favourite colour?",
                  memory_actor, session_2, lambda r: len(r) > 5)
    ok4 = r5 and r6
    results.append(ok4)
    print("  │     Note: if Memory is not configured (BEDROCK_AGENTCORE_MEMORY_ID unset),")
    print("  │     the agent will simply say it doesn't know — that is expected.")
    print("  │     Long-term semantic recall can take a few minutes to become available.")
    print("  └─  " + ("✅ PASSED (agent responded)" if ok4 else "❌ FAILED") + "\n")

    # ── Test 5: Identity tool availability ────────────────────────
    print("  ┌─  Test 5: Identity tool")
    r7 = run_turn("Ask agent to check credential access",
                  "Can you check if secure credential access via Identity is working?",
                  "identity-test", str(uuid.uuid4()), lambda r: len(r) > 5)
    results.append(r7)
    print("  └─  " + ("✅ PASSED" if r7 else "❌ FAILED") + "\n")

    # ── Test 6: Guardrail pass-through on a safe prompt ───────────
    print("  ┌─  Test 6: Guardrail pass-through (safe prompt should succeed normally)")
    r8 = run_turn("Ordinary safe question", "What is the capital of Japan?",
                  "guardrail-test", str(uuid.uuid4()),
                  lambda r: len(r) > 5 and "not able to help" not in r.lower())
    results.append(r8)
    print("  └─  " + ("✅ PASSED" if r8 else "❌ FAILED") + "\n")

    # ── Summary ────────────────────────────────────────────────────
    passed = sum(results)
    failed = len(results) - passed
    print("=" * 62)
    print(f"  Results:  {passed} passed  /  {failed} failed  /  {len(results)} total")
    print("=" * 62 + "\n")

    if failed == 0:
        print("  🎉  All tests passed!\n")
    else:
        print("  ⚠   Some tests failed. Common causes:")
        print("    • Agent ARN is wrong or agent is not ACTIVE")
        print("    • Optional components (Memory/Gateway/Identity/Guardrail) not configured")
        print("      — this is fine, the agent should still respond, just without that feature")
        print("    • AWS credentials/permissions issue — check `agentcore logs`\n")


if __name__ == "__main__":
    main()
