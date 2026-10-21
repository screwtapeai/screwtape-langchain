# Screwtape.ai for LangChain

An independent judge for your agents. Screwtape isn't tied to any agent framework or AI model provider, so its verdicts are never grading their own work. Every verdict comes with a signed receipt you can verify yourself, which gives you a record you can trust when it matters.

False-consensus check and pass/fail/retry verdicts for LangChain agents. This example adds a **judge step** that routes on the verdict (pass → accept, retry → redo with the judge's reasons, fail → stop) and, where several answers exist, a **consensus step** that flags agreement too thin to trust.

## What it does

1. Your LangChain agent drafts an answer from the evidence you give it.
2. The draft goes to `POST https://screwtape.ai/v1/judge` with the task, the evidence and the criteria.
3. The code routes on `verdict`. It prints `score`, `request_id` and the receipt id, so every decision is traceable.

## Files

- `main.py`: a `create_agent` worker; judge loop; `--consensus` mode (3 samples → `/v1/consensus` → judge the consensus answer)
- `screwtape.py`: a stdlib client (`judge`, `consensus`, `verify_receipt`)
- `get_free_key.py`: proof-of-work signup
- `requirements.txt`
- `.env.example`, `.gitignore`, `LICENSE` (MIT)

## Setup and run

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in the keys and load them, or export them
python main.py
python main.py --consensus
```

## Routing

| Verdict | What the example does |
|---|---|
| `pass` | Return or accept the output |
| `retry` | Send the judge's `reasons` back to the worker and try again, up to a fixed cap |
| `fail` | Stop. Don't spend more calls on an answer the judge says is wrong |

The judge returns `verdict`, `score` (0 to 1), `reasons`, `engine` (`llm`, `deterministic` or `demo`), `request_id`, `retention` and, when signing is on, `receipt`. Consensus returns `consensus_answer`, `agreement_score`, `false_consensus_risk` (`low`, `medium` or `high`), `reasons`, `clusters`, `engine`, `request_id`, `retention` and `receipt`. The fields come from https://screwtape.ai/openapi.json.

## Signed verdict receipts

When receipt signing is on, every `/v1/judge` and `/v1/consensus` response also carries a `receipt` object. The fields are `receipt_id`, `issued_at`, `endpoint`, `request_sha256` (SHA-256 of the normalized request), `verdict`, `score`, `payment`, `alg` (`Ed25519`), `kid` and `signature`. For consensus, `verdict` is `false_consensus_risk` and `score` is `agreement_score`. `payment` shows the key prefix or the x402 transaction, never the key.

- Public keys: https://screwtape.ai/.well-known/screwtape-receipt-keys.json (JWKS-style Ed25519)
- Verify: `POST https://screwtape.ai/v1/receipts/verify` with the raw `receipt` object as the request body, exactly as returned (not wrapped in `{"receipt": ...}`). The response is `{"valid": true}` or `{"valid": false}`. No key is needed and the receipt isn't stored.

```python
from screwtape import judge, verify_receipt

v = judge("State the crew size.", "The crew size was 4.", evidence=["The crew size was 4."])
if "receipt" in v:
    print(v["receipt"]["receipt_id"], verify_receipt(v["receipt"]))
```

Store the receipt next to the output it approved, so a reviewer can later check which request was judged, the verdict it got, and when.

## Get a free key (100 calls per UTC day)

- **In a browser:** https://screwtape.ai/signup/ (email and name are optional, no card). To try judge and consensus with no key first, use https://screwtape.ai/try/ (3 calls per token, about 30 minutes).
- **From code or an agent:** `POST https://screwtape.ai/v1/signup` with a proof of work. The SHA-256 of `screwtape-signup-v1:<UTC YYYY-MM-DD>:<nonce>` must start with 12 zero bits, and the nonce must match `^[A-Za-z0-9_-]{8,64}$`. `python get_free_key.py --name my-agent` does this for you (`--dry-run` only finds the nonce).
- The key is shown **once**. Screwtape stores only its SHA-256 hash. Limits are 5 keys per IP per hour and 5 per UTC day.
- Copy `.env.example` to `.env` (git-ignored) or export `SCREWTAPE_API_KEY`. The code reads the key from the environment and never embeds it.

## x402 pay-per-call (no key)

Without a key, `/v1/judge` and `/v1/consensus` answer **HTTP 402 Payment Required** with x402 v2 terms: **$0.005 USDC per call on Base (`eip155:8453`) or Solana**. The terms are in the base64 `PAYMENT-REQUIRED` header. The JSON body has `x402Version`, `accepts` and `error` at the top level, plus `signup_url`, `pricing_url` and `pricing_json_url`. Auth and payment are checked before the body is validated, so even an empty body gets the 402. This example catches the 402 and prints a hint.

```bash
curl -s -D - -o /dev/null https://screwtape.ai/v1/judge -H "Content-Type: application/json" \
  -d '{"task":"State the crew size.","agent_output":"The crew size was 4."}' \
  | grep -i '^payment-required:' | cut -d' ' -f2 | tr -d '\r' | base64 -d | jq .accepts
```

To pay, an x402 client signs the terms and resends the request with a `PAYMENT-SIGNATURE` header. Payments are verified and settled through a facilitator. Keyless calls can't turn on `retain`. With the `x402` Python package (`pip install "x402[requests,evm]"`, checked with 2.25.0):

```python
import os
from eth_account import Account
from x402 import x402ClientSync
from x402.http.clients import x402_requests
from x402.mechanisms.evm import EthAccountSigner
from x402.mechanisms.evm.exact.register import register_exact_evm_client

client = x402ClientSync()
register_exact_evm_client(client, EthAccountSigner(Account.from_key(os.environ["EVM_PRIVATE_KEY"])))
with x402_requests(client) as session:
    paid = session.post("https://screwtape.ai/v1/judge", json={"task": "State the crew size.", "agent_output": "The crew size was 4.", "evidence": ["The crew size was 4."]})
print(paid.json()["verdict"])
```

Use a dedicated wallet with a small balance, and keep its private key in your secret store, never in this repo. Prepaid packs (Starter $30 for 10,000 calls, Builder $100 for 50,000 calls) are on https://screwtape.ai/pricing/.

## Compatibility notes

- Uses `langchain.agents.create_agent` (LangChain 1.x) and reads the reply from `result["messages"][-1].text`. Swap the `"openai:gpt-4o-mini"` model string for any provider `init_chat_model` supports.
- Samples from one model and one prompt are **not independent**. That's exactly when `false_consensus_risk` comes back high, which is why the consensus answer is still judged against evidence.
- Checked: compiles with langchain 1.4.6. The routing was tested with stubbed calls.

## Links

- Screwtape.ai: https://screwtape.ai/
- API reference: https://screwtape.ai/docs/ · OpenAPI: https://screwtape.ai/openapi.json · For agents: https://screwtape.ai/llms.txt
- MCP server: https://screwtape.ai/mcp (MCP Registry name `ai.screwtape/screwtape`)
- Pricing: https://screwtape.ai/pricing/ · Free key: https://screwtape.ai/signup/
- Source for this example: https://github.com/screwtapeai/screwtape-langchain
- Issues: https://github.com/screwtapeai/screwtape-langchain/issues

## License

MIT. See [LICENSE](LICENSE). Copyright (c) 2026 Screwtape.ai.

---
Screwtape.ai is an agent validation API, not the arXiv paper that is also named Screwtape. This example was checked against the live API on 2026-10-21.
