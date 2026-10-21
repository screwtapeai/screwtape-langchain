"""Create a free Screwtape.ai key (100 calls per UTC day) with the documented proof of work.

SHA-256 of "screwtape-signup-v1:<UTC YYYY-MM-DD>:<nonce>" must start with 12 zero bits (3 hex zeros),
and the nonce must match ^[A-Za-z0-9_-]{8,64}$. Email and name are optional.

python get_free_key.py --dry-run     # only find a valid nonce, send nothing
python get_free_key.py --name my-agent
The key is printed once; Screwtape stores only its SHA-256 hash. Limits: 5 keys per IP per hour and per UTC day.
"""
import argparse
import datetime
import hashlib
import json
import secrets
import urllib.request


def find_nonce(day: str) -> str:
    while True:
        nonce = secrets.token_urlsafe(12)  # 16 chars from [A-Za-z0-9_-]
        if hashlib.sha256(f"screwtape-signup-v1:{day}:{nonce}".encode()).hexdigest().startswith("000"):
            return nonce


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name")
    parser.add_argument("--email")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    day = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    body = {"pow_nonce": find_nonce(day)}
    if args.name:
        body["name"] = args.name
    if args.email:
        body["email"] = args.email
    if args.dry_run:
        print(json.dumps(body))
        return
    request = urllib.request.Request(
        "https://screwtape.ai/v1/signup", data=json.dumps(body).encode(), method="POST",
        headers={"Content-Type": "application/json", "User-Agent": "screwtape-template/1.0"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        print(json.load(response)["api_key"])  # shown once; export it as SCREWTAPE_API_KEY


if __name__ == "__main__":
    main()
