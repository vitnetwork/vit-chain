"""
VIT Chain Node — main.py
Standalone FastAPI service for VIT Chain (Chain ID 7764).
Proof-of-Storage consensus, JSON-RPC 2.0, P2P gossip.
"""
import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from chain.config import settings
from chain.database import init_db, AsyncSessionLocal
from chain.startup_log import errors as _startup_errors, capture as _capture_error

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger("vit-chain")


async def _boot() -> None:
    """
    Run all heavyweight startup work in a background task so uvicorn
    binds the port and /ping is reachable immediately.

    Render's health check fires as soon as the port is open.  If this
    code ran synchronously inside lifespan (before yield), Render's
    30-second health-check window would expire during DB init / genesis
    crypto, causing update_failed on every deploy.
    """
    logger.info(
        "VIT Chain Node %s booting — network: %s, chain_id: %d",
        settings.NODE_VERSION, settings.NETWORK, settings.CHAIN_ID,
    )

    # ── 1. Initialise DB schema ────────────────────────────────────────
    try:
        await init_db()
        logger.info("Database schema ready.")
        _boot.db_ready = True
    except Exception as exc:
        logger.error("Database init failed — node starting in DEGRADED mode: %s", exc)
        _boot.db_ready = False

    # ── 2. Seed genesis block (idempotent) ────────────────────────────
    if getattr(_boot, "db_ready", False):
        try:
            from chain.genesis import ensure_genesis  # lazy — avoids import-time crypto crash
            async with AsyncSessionLocal() as db:
                genesis = await ensure_genesis(db)
                await db.commit()
                logger.info(
                    "Genesis verified: height=%d hash=%s…",
                    genesis.height, genesis.block_hash[:16],
                )
        except Exception as exc:
            logger.error("Genesis seeding failed — chain may be empty: %s", exc)

    # ── 3. Consensus epoch scheduler ─────────────────────────────────
    try:
        from chain.consensus.scheduler import EpochScheduler
        scheduler = EpochScheduler()
        consensus_task = asyncio.create_task(
            scheduler.run(), name="consensus-scheduler"
        )
        _boot.scheduler = scheduler
        _boot.consensus_task = consensus_task
        logger.info("Consensus scheduler started (epoch=%ds).", settings.EPOCH_SECONDS)
    except Exception as exc:
        logger.error("Consensus scheduler failed to start: %s", exc)

    logger.info("VIT Chain Node OPERATIONAL — RPC at POST /rpc")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start all heavyweight init in the background — /ping is reachable immediately.
    # This prevents Render's 30-second health check from timing out during DB/genesis boot.
    boot_task = asyncio.create_task(_boot(), name="vit-chain-boot")

    # Propagate boot state to app.state once the task finishes (non-blocking for requests)
    async def _propagate_state():
        try:
            await boot_task
        except Exception as exc:
            logger.error("Boot task failed: %s", exc)
        app.state.db_ready = getattr(_boot, "db_ready", False)
        app.state.scheduler = getattr(_boot, "scheduler", None)
        app.state.consensus_task = getattr(_boot, "consensus_task", None)

    asyncio.create_task(_propagate_state(), name="propagate-boot-state")

    yield  # ← uvicorn serves /ping immediately; boot continues in background

    # ── Shutdown ──────────────────────────────────────────────────────
    logger.info("Shutting down VIT Chain Node…")
    boot_task.cancel()
    task = getattr(app.state, "consensus_task", None) or getattr(_boot, "consensus_task", None)
    if task and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    logger.info("VIT Chain Node stopped.")


app = FastAPI(
    title="VIT Chain Node",
    description=(
        f"VIT Network — Chain ID {settings.CHAIN_ID} ({settings.NETWORK}). "
        "Proof-of-Storage consensus. JSON-RPC 2.0 compatible."
    ),
    version=settings.NODE_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
try:
    from chain.rpc.router import router as rpc_router
    app.include_router(rpc_router)
except Exception as _e:
    _capture_error("rpc_router", _e)
    logger.error("Failed to load RPC router: %s", _e)

try:
    from api.blocks import router as blocks_router
    app.include_router(blocks_router)
except Exception as _e:
    _capture_error("blocks_router", _e)
    logger.error("Failed to load blocks router: %s", _e)

try:
    from api.transactions import router as txs_router
    app.include_router(txs_router)
except Exception as _e:
    _capture_error("transactions_router", _e)
    logger.error("Failed to load transactions router: %s", _e)

try:
    from api.accounts import router as accounts_router
    app.include_router(accounts_router)
except Exception as _e:
    _capture_error("accounts_router", _e)
    logger.error("Failed to load accounts router: %s", _e)

try:
    from api.validators import router as validators_router
    app.include_router(validators_router)
except Exception as _e:
    _capture_error("validators_router", _e)
    logger.error("Failed to load validators router: %s", _e)

try:
    from api.status import router as status_router
    app.include_router(status_router)
except Exception as _e:
    _capture_error("status_router", _e)
    logger.error("Failed to load status router: %s", _e)

try:
    from api.peers import router as peers_router
    app.include_router(peers_router)
except Exception as _e:
    _capture_error("peers_router", _e)
    logger.error("Failed to load peers router: %s", _e)

try:
    from api.registry import router as registry_router
    app.include_router(registry_router)
except Exception as _e:
    _capture_error("registry_router", _e)
    logger.error("Failed to load registry router: %s", _e)


# ── Core endpoints ────────────────────────────────────────────────────────────
@app.get("/ping", tags=["Health"])
async def ping():
    """Liveness probe — always 200, no DB dependency."""
    return {
        "status": "ok",
        "chain_id": settings.CHAIN_ID,
        "network":  settings.NETWORK,
        "version":  settings.NODE_VERSION,
    }


@app.get("/health", tags=["Health"])
async def health():
    """Deep readiness check — reports DB connectivity and chain state."""
    from sqlalchemy import text
    db_ok = False
    height = 0
    validator_count = 0
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
            db_ok = True
            from chain.core.chain import VITChain
            _chain = VITChain()
            height = await _chain.get_height(db)
            from chain.consensus.registry import ValidatorRegistry
            reg = ValidatorRegistry()
            validators = await reg.get_active_validators(db)
            validator_count = len(validators)
    except Exception as exc:
        logger.debug("Health check DB error: %s", exc)

    boot_done = getattr(_boot, "db_ready", None) is not None
    return {
        "status":            "healthy" if db_ok else ("booting" if not boot_done else "degraded"),
        "network":           settings.NETWORK,
        "chain_id":          settings.CHAIN_ID,
        "version":           settings.NODE_VERSION,
        "db_connected":      db_ok,
        "block_height":      height,
        "active_validators": validator_count,
    }


@app.get("/api/startup-errors", tags=["Debug"])
async def startup_errors():
    """Return router import errors captured at startup."""
    return _startup_errors
