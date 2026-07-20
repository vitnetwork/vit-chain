# VIT Chain Node

**Standalone Proof-of-Storage blockchain node for VIT Network.**

| Parameter | Value |
|-----------|-------|
| Chain ID | **7764** (`0x1e54`) |
| Network (testnet) | **vit-testnet** |
| Block time | **15 seconds** |
| Consensus | **Proof of Storage + Oracle Consensus** |
| Currency | **VIT** (18 decimal precision) |
| RPC | `POST /rpc` (JSON-RPC 2.0) |
| Explorer | `GET /api/blocks` |

---

## MetaMask Setup

Add VIT Chain to MetaMask manually:

| Field | Value |
|-------|-------|
| Network Name | VIT Chain Testnet |
| New RPC URL | `https://vit-chain.onrender.com/rpc` |
| Chain ID | `7764` |
| Currency Symbol | `VIT` |
| Block Explorer URL | `https://vit-chain.onrender.com/docs` |

---

## Architecture

```
POST /rpc          — JSON-RPC 2.0 (MetaMask compatible)
GET  /health       — Node health + chain height
GET  /status       — Full chain status
GET  /api/blocks   — Block explorer API
GET  /api/txs      — Transaction lookup
GET  /api/accounts — Account balances
GET  /api/validators — Validator set + reputation
WS   /api/peer     — P2P gossip WebSocket
```

### Consensus (Proof of Storage)

Every 15 seconds:
1. **Challenge**: Node generates a storage challenge for each active validator
2. **Response window**: 10 seconds for validators to respond
3. **Aggregation**: Results collected; consensus weight calculated
4. **Block production**: If weight ≥ 0.67, the local validator produces a block
5. **Slashing**: Validators with ≥ 50 consecutive missed slots are slashed

### Slashing rules

| Reason | Penalty |
|--------|---------|
| `DOWNTIME` (50 missed slots) | 5% stake |
| `DOUBLE_SIGN` | 20% stake + jail |
| `INVALID_BLOCK` | 10% stake |

---

## Required Environment Variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `GENESIS_TREASURY_KEY` | Private key hex for genesis treasury wallet |
| `VIT_VALIDATOR_KEY` | Private key hex for block signing |
| `GENESIS_PROPOSER_ADDRESS` | Address derived from VIT_VALIDATOR_KEY |
| `GENESIS_VALIDATORS` | `address:stake:name,...` list |
| `NETWORK` | `testnet` or `mainnet` |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | (none) | Redis for pub/sub; in-memory fallback if unset |
| `EPOCH_SECONDS` | `15` | Consensus epoch length |
| `SLASHING_DOWNTIME_SLOTS` | `50` | Consecutive misses before slash |
| `VIT_BOOTSTRAP_WS_URL` | (none) | Bootstrap peer WebSocket URL |
| `VIT_BOOTSTRAP_HTTP_URL` | (none) | Bootstrap peer HTTP URL |
| `VIT_STORAGE_URL` | (none) | vit-storage service URL |
| `VIT_AI_URL` | (none) | vit-ai oracle service URL |

---

## Local Development

```bash
# 1. Clone
git clone https://github.com/vitnetwork/vit-chain.git
cd vit-chain

# 2. Install
pip install -r requirements.txt

# 3. Configure (SQLite works locally — no Postgres needed)
export DATABASE_URL="sqlite+aiosqlite:///./vitchain.db"
export GENESIS_TREASURY_KEY="<your_32_byte_hex_key>"
export VIT_VALIDATOR_KEY="<your_validator_key>"
export NETWORK="testnet"

# 4. Run
uvicorn main:app --reload --port 7764
```

Open `http://localhost:7764/docs` to explore the API.

---

## Generating a Wallet

```python
from chain.crypto.ecdsa import generate_keypair
from chain.crypto.address import public_key_to_address

priv, pub = generate_keypair()
address = public_key_to_address(pub)
print("Private key:", priv)   # → set as GENESIS_TREASURY_KEY / VIT_VALIDATOR_KEY
print("Address:    ", address) # → set as GENESIS_PROPOSER_ADDRESS
```

---

## Deployment (Render)

1. Fork / connect `vitnetwork/vit-chain` to Render
2. Create a **PostgreSQL** database in Render; copy the connection string to `DATABASE_URL`
3. Set all required secrets in the Render dashboard
4. Deploy — the service auto-seeds genesis on first boot

---

*VIT Network — Verifiable Intelligence. Universal Trust.*
