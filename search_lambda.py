"""
╔══════════════════════════════════════════════════════════════════╗
║  lambda/search_lambda.py  —  Gateway target backend              ║
╠══════════════════════════════════════════════════════════════════╣
║  This is the Lambda function that AgentCore Gateway calls when   ║
║  the agent invokes the Gateway-hosted search tool.                ║
╚══════════════════════════════════════════════════════════════════╝

WHY THIS EXISTS
  AgentCore Gateway does not run arbitrary code itself — it forwards
  each tool call to a backend you control, most commonly a Lambda
  function, then returns the result to the agent as an MCP tool
  response. This file IS that backend for the "gateway_search" tool
  configured by setup_gateway.ps1.

  Note this is intentionally similar to the web_search tool already
  built into agent.py — the point of this file is to demonstrate the
  GATEWAY PATTERN (agent → Gateway → Lambda → external API), not to
  add a materially different capability. In a real project, this
  Lambda would usually call an internal company API instead.

DEPLOYING THIS FUNCTION
  setup_gateway.ps1 packages and deploys this file automatically.
  See README.md Section "Setting Up Gateway" for the manual steps
  if you prefer to run them yourself.

EXPECTED EVENT SHAPE (from Gateway)
  Gateway invokes this Lambda with the tool's input arguments as
  the event payload, e.g.:
      { "query": "latest AWS re:Invent announcements" }

RETURN SHAPE
  Gateway expects a JSON-serialisable value back. A simple string
  or dict is fine — Gateway wraps it into the MCP tool result.
"""

import json
import urllib.request
import urllib.parse


def lambda_handler(event, context):
    """AWS Lambda entrypoint invoked by AgentCore Gateway."""

    query = event.get("query", "").strip()

    if not query:
        return {"error": "No query provided."}

    try:
        results = _duckduckgo_search(query, max_results=5)
    except Exception as exc:
        return {"error": f"Search failed: {exc}"}

    if not results:
        return {"results": "No results found for that query."}

    formatted = []
    for i, r in enumerate(results, 1):
        formatted.append(
            f"[Result {i}] {r['title']}\n{r['body']}\n{r['href']}"
        )

    return {"results": "\n\n".join(formatted)}


def _duckduckgo_search(query: str, max_results: int = 5) -> list[dict]:
    """Minimal dependency-free DuckDuckGo HTML search.

    Lambda's default runtime does not include the `ddgs` package
    used by agent.py, and adding a Lambda layer for it is extra
    setup. This lightweight fallback uses DuckDuckGo's HTML
    endpoint directly with only the standard library, keeping the
    Lambda simple to deploy for this demonstration.

    For production use, prefer packaging `ddgs` (or a licensed
    search API) as a Lambda layer instead of scraping HTML.
    """
    url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query})
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

    with urllib.request.urlopen(req, timeout=10) as resp:
        html = resp.read().decode("utf-8", errors="ignore")

    # Very small, tolerant parse — good enough for a demo Lambda.
    results = []
    blocks = html.split('class="result__body"')[1:max_results + 1]
    for block in blocks:
        title = _extract_between(block, 'class="result__a"', "</a>")
        snippet = _extract_between(block, 'class="result__snippet"', "</a>")
        results.append({
            "title": _strip_tags(title)[:200],
            "body": _strip_tags(snippet)[:300],
            "href": "See DuckDuckGo search results for this query.",
        })
    return results


def _extract_between(text: str, start_marker: str, end_marker: str) -> str:
    try:
        start = text.index(start_marker)
        rest = text[start + len(start_marker):]
        end = rest.index(end_marker)
        return rest[:end]
    except ValueError:
        return ""


def _strip_tags(text: str) -> str:
    out = []
    in_tag = False
    for ch in text:
        if ch == "<":
            in_tag = True
        elif ch == ">":
            in_tag = False
        elif not in_tag:
            out.append(ch)
    return "".join(out).replace("&amp;", "&").strip(" >\"'")
