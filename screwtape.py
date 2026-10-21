"""Small Screwtape.ai client (Python stdlib only).

Reads SCREWTAPE_API_KEY from the environment. Without a key, judge and consensus
answer HTTP 402 with x402 payment terms; see the README.
Fields follow https://screwtape.ai/openapi.json.
"""
import json
import os
import urllib.error
import urllib.request

API = "https://screwtape.ai"
USER_AGENT = "screwtape-integration-example/1.0"


def _post(path: str, payload: dict, auth: bool = True) -> dict:
    headers = {"Content-Type": "application/json", "User-Agent": USER_AGENT}
    key = os.environ.get("SCREWTAPE_API_KEY")
    if auth and key:
        headers["Authorization"] = "Bearer " + key
    request = urllib.request.Request(API + path, data=json.dumps(payload).encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)
    except urllib.error.HTTPError as err:
        if err.code == 402:
            raise SystemExit(
                "402 Payment Required: set SCREWTAPE_API_KEY (free key, 100 calls per UTC day) "
                "or pay $0.005 USDC per call with x402 on Base or Solana. See README."
            ) from None
        raise SystemExit(f"Screwtape {err.code}: {err.read().decode()[:300]}") from None


def judge(task: str, agent_output: str, evidence=None, criteria=None) -> dict:
    """POST /v1/judge.

    Returns verdict (pass|fail|retry), score (0-1), reasons, engine, request_id,
    retention, and a signed receipt when signing is configured on the server.
    """
    body = {"task": task, "agent_output": agent_output}
    if evidence:
        body["evidence"] = evidence
    if criteria:
        body["criteria"] = criteria
    return _post("/v1/judge", body)


def consensus(task: str, answers: list[dict]) -> dict:
    """POST /v1/consensus with 2-16 {agent_id?, output}.

    Returns consensus_answer, agreement_score, false_consensus_risk (low|medium|high),
    reasons, clusters, engine, request_id, retention, and a receipt when signing is configured.
    """
    return _post("/v1/consensus", {"task": task, "answers": answers})


def verify_receipt(receipt: dict) -> bool:
    """POST /v1/receipts/verify. Free, no key needed, and the receipt is not stored."""
    return bool(_post("/v1/receipts/verify", receipt, auth=False).get("valid"))
