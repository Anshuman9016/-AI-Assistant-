"""
╔══════════════════════════════════════════════════════════════════╗
║  test_local.py  —  Test Your Agent Locally (Before Deploying)  ║
╚══════════════════════════════════════════════════════════════════╗

HOW TO USE
  Window 1:   python agent.py
  Window 2:   python test_local.py
"""

import json
import sys
import time
import urllib.request
import urllib.error

LOCAL_URL = "http://localhost:8080/invocations"

TEST_CASES = [
    {
        "name": "Greeting Test",
        "prompt": "hello",
        "check": lambda r: len(r) > 10,
        "hint": "Expected a greeting response",
    },
    {
        "name": "General Knowledge Test",
        "prompt": "What is Python programming language?",
        "check": lambda r: "python" in r.lower() or "programming" in r.lower(),
        "hint": "Expected answer to mention Python or programming",
    },
    {
        "name": "Internet Search Test (built-in tool)",
        "prompt": "What is the latest news about artificial intelligence today?",
        "check": lambda r: len(r) > 50,
        "hint": "Expected a longer response from web search",
    },
    {
        "name": "Identity Tool Test",
        "prompt": "Can you check if secure credential access is working?",
        "check": lambda r: len(r) > 10,
        "hint": "Expected the agent to mention Identity status (configured or not)",
    },
    {
        "name": "Empty Prompt Test",
        "prompt": "",
        "check": lambda r: len(r) > 5,
        "hint": "Expected a fallback message for empty input",
    },
]


def call_agent(prompt: str, actor_id: str = "test-user", session_id: str = "test-session") -> str:
    body = json.dumps({"prompt": prompt, "actor_id": actor_id, "session_id": session_id}).encode("utf-8")
    req = urllib.request.Request(
        LOCAL_URL, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("response", "")
    except urllib.error.URLError as exc:
        return f"CONNECTION_ERROR: {exc}"


def main() -> None:
    print("=" * 62)
    print("  AI Assistant (Full) — Local Test Suite")
    print("=" * 62)
    print(f"  Target: {LOCAL_URL}\n")

    print("Checking server is running...", end=" ", flush=True)
    test_resp = call_agent("hello")
    if test_resp.startswith("CONNECTION_ERROR"):
        print("❌  FAILED\n")
        print("  Start the server first in another window:")
        print("    python agent.py\n")
        sys.exit(1)
    print("✅  Server is up\n")

    passed, failed = 0, 0

    for i, test in enumerate(TEST_CASES, 1):
        print(f"  [{i}/{len(TEST_CASES)}]  {test['name']}")
        print(f"         Prompt: {repr(test['prompt'])[:60]}")
        print("         Sending...", end=" ", flush=True)

        start = time.time()
        response = call_agent(test["prompt"], session_id=f"test-{i}")
        elapsed = time.time() - start

        if response.startswith("CONNECTION_ERROR"):
            print(f"❌  ERROR\n         {response}\n")
            failed += 1
            continue

        ok = test["check"](response)
        print(f"{'✅  PASSED' if ok else '❌  FAILED'}  ({elapsed:.1f}s)")
        print(f"         Response: {response[:120]}{'...' if len(response) > 120 else ''}")
        if not ok:
            print(f"         ⚠  Hint: {test['hint']}")
        print()

        passed += ok
        failed += not ok

    print("=" * 62)
    print(f"  Results:  {passed} passed  /  {failed} failed  /  {len(TEST_CASES)} total")
    print("=" * 62)
    if failed == 0:
        print("\n  🎉  All tests passed! Ready to deploy with .\\deploy.ps1\n")
    else:
        print("\n  ⚠   Some tests failed — check agent.py's terminal output for errors.\n")


if __name__ == "__main__":
    main()
