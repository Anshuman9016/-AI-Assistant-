"""
╔══════════════════════════════════════════════════════════════════╗
║  identity_utils.py  —  AgentCore Identity helpers                ║
╠══════════════════════════════════════════════════════════════════╣
║  Lets the agent securely obtain credentials to call OTHER        ║
║  services on the user's behalf, without embedding secrets in     ║
║  the agent's own code or environment variables.                 ║
╚══════════════════════════════════════════════════════════════════╝

WHAT IDENTITY ADDS
  Without Identity, any credential a tool needs (an API key for a
  third-party service, an OAuth token, etc.) has to be hard-coded
  or passed in as a plain environment variable — which means it is
  visible to anyone who can read the agent's configuration.

  AgentCore Identity solves this with a "workload identity": the
  agent authenticates as itself (not as a human), and asks Identity
  to vend a short-lived credential for a specific downstream
  resource at the moment it is needed. The actual secret is stored
  once, centrally, in an Identity credential provider — never in
  the agent's code.

HOW IT IS USED IN THIS PROJECT
  As a concrete, runnable example, this file vends an API key for
  a demo "quotes" API (a free public API used purely to demonstrate
  the pattern) through an Identity API-key credential provider named
  demo-quotes-api, created by setup_identity.ps1. The pattern is
  identical for any other API-key or OAuth2-based service — only
  the provider name changes.

REQUIRED ENVIRONMENT VARIABLES
  IDENTITY_WORKLOAD_NAME        Workload identity name (setup_identity.ps1)
  IDENTITY_CREDENTIAL_PROVIDER  Credential provider name (setup_identity.ps1)

  If these are not set, get_identity_api_key() returns None and the
  identity_lookup tool reports itself as unavailable — Identity is
  a fully optional add-on, exactly like Gateway and Memory.
"""

import logging
import os

import boto3
from botocore.exceptions import ClientError

log = logging.getLogger("identity_utils")

REGION = os.environ.get("AWS_REGION", "us-east-1")

WORKLOAD_NAME       = os.environ.get("IDENTITY_WORKLOAD_NAME", "")
CREDENTIAL_PROVIDER = os.environ.get("IDENTITY_CREDENTIAL_PROVIDER", "")

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = boto3.client("bedrock-agentcore", region_name=REGION)
    return _client


def identity_enabled() -> bool:
    """Return True if a workload identity + credential provider are configured."""
    return bool(WORKLOAD_NAME and CREDENTIAL_PROVIDER)


def get_identity_api_key() -> str | None:
    """Ask AgentCore Identity to vend the API key for CREDENTIAL_PROVIDER.

    Returns None (and logs a warning) if Identity is not configured or
    the vending call fails. Never raises — a missing credential should
    degrade the relevant tool gracefully, not crash the agent.
    """
    if not identity_enabled():
        log.info("Identity not configured — skipping credential vending (optional).")
        return None

    client = _get_client()

    try:
        resp = client.get_resource_api_key(
            workloadIdentityName=WORKLOAD_NAME,
            resourceCredentialProviderName=CREDENTIAL_PROVIDER,
        )
        return resp.get("apiKey")
    except ClientError as exc:
        log.warning("Could not vend API key via Identity: %s", exc)
        return None
    except Exception as exc:
        log.warning("Unexpected error vending Identity credential: %s", exc)
        return None


def get_workload_access_token() -> str | None:
    """Return a short-lived workload access token identifying THIS agent.

    Useful when a downstream service should authenticate the agent
    itself (rather than vend a separate third-party API key) — for
    example, calling another internal AgentCore-hosted agent.
    """
    if not WORKLOAD_NAME:
        return None

    client = _get_client()
    try:
        resp = client.get_workload_access_token(workloadIdentityName=WORKLOAD_NAME)
        return resp.get("accessToken")
    except ClientError as exc:
        log.warning("Could not obtain workload access token: %s", exc)
        return None
    except Exception as exc:
        log.warning("Unexpected error obtaining workload access token: %s", exc)
        return None
