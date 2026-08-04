"""
tests/test_api.py — HTTP API tests for VIT Chain node.

Exercises the FastAPI endpoints using TestClient with an in-memory SQLite
database so no external services are required.
"""
import os
import pytest
from fastapi.testclient import TestClient

# Force SQLite for tests
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_chain.db")
os.environ.setdefault("CHAIN_ID",      "7764")
os.environ.setdefault("NETWORK",       "testnet")
os.environ.setdefault("LOG_LEVEL",     "WARNING")
os.environ.setdefault("EPOCH_SECONDS", "15")
os.environ.setdefault("P2P_ENABLED",   "false")
os.environ.setdefault("GENESIS_VALIDATORS", "")

from main import app  # noqa: E402

client = TestClient(app)


class TestHealthEndpoints:
    def test_ping(self):
        r = client.get("/ping")
        assert r.status_code == 200
        data = r.json()
        assert data.get("status") == "ok"

    def test_health(self):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert "chain_id" in data or "status" in data

    def test_version(self):
        r = client.get("/version")
        assert r.status_code == 200


class TestBlockEndpoints:
    def test_list_blocks(self):
        r = client.get("/api/blocks")
        assert r.status_code == 200
        data = r.json()
        # Response is list or dict with blocks key
        assert isinstance(data, (list, dict))

    def test_get_latest_block(self):
        r = client.get("/api/blocks/latest")
        # 200 if genesis exists, 404 if no blocks yet — both are valid
        assert r.status_code in (200, 404)

    def test_get_block_by_height_not_found(self):
        r = client.get("/api/blocks/999999")
        assert r.status_code == 404

    def test_get_block_by_invalid_hash(self):
        r = client.get("/api/blocks/hash/0xdeadbeef")
        assert r.status_code in (200, 404)


class TestValidatorEndpoints:
    def test_list_validators(self):
        r = client.get("/api/validators")
        assert r.status_code == 200
        data = r.json()
        assert "validators" in data
        assert isinstance(data["validators"], list)

    def test_get_validator_not_found(self):
        r = client.get("/api/validators/0x0000000000000000000000000000000000000000")
        assert r.status_code == 404

    def test_register_validator_missing_fields(self):
        r = client.post("/api/validators/register", json={})
        assert r.status_code == 422  # Validation error

    def test_register_validator(self):
        payload = {
            "address": "0x" + "ab" * 20,
            "name": "test-node",
            "node_id": "node_test_001",
            "stake": "100000",
        }
        r = client.post("/api/validators/register", json=payload)
        # 201 Created or 400 if already exists
        assert r.status_code in (201, 200, 400)


class TestTransactionEndpoints:
    def test_get_tx_not_found(self):
        r = client.get("/api/txs/0x" + "ff" * 32)
        assert r.status_code == 404

    def test_submit_tx_invalid(self):
        r = client.post("/api/txs", json={})
        assert r.status_code == 422

    def test_mempool(self):
        r = client.get("/api/mempool")
        assert r.status_code == 200


class TestAccountEndpoints:
    def test_get_account_not_found(self):
        r = client.get("/api/accounts/0x" + "cc" * 20)
        assert r.status_code == 404

    def test_get_account_transactions(self):
        r = client.get("/api/accounts/0x" + "cc" * 20 + "/transactions")
        assert r.status_code in (200, 404)


class TestStatusAndPeers:
    def test_status(self):
        r = client.get("/api/status")
        assert r.status_code == 200
        data = r.json()
        assert "chain_id" in data or "network" in data

    def test_peers(self):
        r = client.get("/api/peers")
        assert r.status_code == 200

    def test_registry(self):
        r = client.get("/api/registry")
        assert r.status_code == 200


class TestChallengeEndpoints:
    def test_pending_challenges_no_validator(self):
        r = client.get("/api/challenges/pending")
        # Should return 200 with empty list if no validator param required,
        # or 422 if validator query param is required
        assert r.status_code in (200, 422)

    def test_challenge_stats(self):
        r = client.get("/api/challenges/stats")
        assert r.status_code == 200
