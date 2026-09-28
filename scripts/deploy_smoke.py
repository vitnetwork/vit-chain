"""Verify the public chain deployment has connected, persisted state."""
import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE_URL = os.getenv("VIT_CHAIN_URL", "https://vit-chain.onrender.com").rstrip("/")
MAX_ATTEMPTS = 18
RETRY_SECONDS = 10


def get_json(path: str) -> tuple[int, dict]:
    request = Request(f"{BASE_URL}{path}", headers={"Accept": "application/json"})
    with urlopen(request, timeout=15) as response:
        payload = json.loads(response.read())
        if not isinstance(payload, dict):
            raise TypeError(f"{path} returned a non-object response")
        return response.status, payload


def main() -> None:
    last_failure = "health endpoint has not returned"
    health = {}
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            _, health = get_json("/health")
            block_height = health.get("block_height")
            if health.get("db_connected") is True and isinstance(block_height, int) and block_height > 0:
                break
            last_failure = (
                "database is disconnected or persisted block height is zero "
                f"(db_connected={health.get('db_connected')}, block_height={block_height})"
            )
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            last_failure = f"health check failed ({type(exc).__name__})"
        if attempt < MAX_ATTEMPTS:
            time.sleep(RETRY_SECONDS)
    else:
        raise SystemExit(f"VIT Chain deployment is not ready after {MAX_ATTEMPTS} attempts: {last_failure}")

    _, status = get_json("/api/status")
    if status.get("block_height") != health["block_height"]:
        raise SystemExit("VIT Chain health and status report different block heights")

    _, blocks = get_json("/api/blocks?limit=1")
    if not blocks.get("blocks") or blocks.get("total", 0) < 1:
        raise SystemExit("VIT Chain explorer returned no persisted blocks")

    print(
        "VIT Chain deployment healthy: "
        f"db_connected=true, block_height={health['block_height']}, "
        f"active_validators={health.get('active_validators', 0)}, explorer_blocks={blocks['total']}"
    )


if __name__ == "__main__":
    main()