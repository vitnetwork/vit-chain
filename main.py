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
from chain.genesis import ensure_genesis

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger("vit-chain")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "VIT Chain Node %s starting — network: %s, chain_id: %d",
        settings.NODE_VERSION, settings.NETWORK, settings.CHAIN_ID,
    )

    # ── 1. Initialise DB schema ──────────────────────────────────────────────
    # Wrapped so the service boots in DEGRADED mode even if the DB is
    # temporarily unavailable. /ping always responds; /health reports state.
    try:
        await init_db()
        logger.info("Database schema ready.")
        app.state.db_ready = True
    except Exception as exc:
        logger.error(
            "Database init failed — node starting in DEGRADED mode: %s", exc
        )
        app.state.db_ready = False

    # ── 2. Seed genesis block (idempotent) ───────────────────────────────────
    if getattr(app.state, "db_ready", False):
        try:
            async with AsyncSessionLocal() as db:
                genesis = await ensure_genesis(db)
                await db.commit()
                logger.info(
                    "Genesis verified: height=%d hash=%s…",
                    genesis.height, genesis.block_hash[:16],
                )
        except Exception as exc:
            logger.error("Genesis seeding failed — chain may be empty: %s", exc)

    # ── 3. Consensus epoch scheduler ─────────────────────────────────────────
    app.state.consensus_task = None
    try:
        from chain.consensus.scheduler import EpochScheduler
        scheduler = EpochScheduler()
        consensus_task = asyncio.create_task(
            scheduler.run(), name="consensus-scheduler"
        )
        app.state.scheduler = scheduler
        app.state.consensus_task = consensus_task
        logger.info("Consensus scheduler started (epoch=%ds).", settings.EPOCH_SECONDS)
    except Exception as exc:
        logger.error("Consensus scheduler failed to start: %s", exc)

    logger.info("VIT Chain Node OPERATIONAL — RPC at POST /rpc")

    yield

    # ── Shutdown ─────────────────────────────────────────────────────────────
    logger.info("Shutting down VIT Chain Node…")
    task = getattr(app.state, "consensus_task", None)
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

# ── Routers ──────────────────────────────────────────────────────────────────
try:
    from chain.rpc.router import router as rpc_router
    app.include_router(rpc_router)
except Exception as _e:
    logger.error("Failed to load RPC router: %s", _e)

try:
    from api.blocks import router as blocks_router
    app.include_router(blocks_router)
except Exception as _e:
    logger.error("Failed to load blocks router: %s", _e)

try:
    from api.transactions import router as txs_router
    app.include_router(txs_router)
except Exception as _e:
    logger.error("Failed to load transactions router: %s", _e)

try:
    from api.accounts import router as accounts_router
    app.include_router(accounts_router)
except Exception as _e:
    logger.error("Failed to load accounts router: %s", _e)

try:
    from api.validators import router as validators_router
    app.include_router(validators_router)
except Exception as _e:
    logger.error("Failed to load validators router: %s", _e)

try:
    from api.status import router as status_router
    app.include_router(status_router)
except Exception as _e:
    logger.error("Failed to load status router: %s", _e)

try:
    from api.peers import router as peers_router
    app.include_router(peers_router)
except Exception as _e:
    logger.error("Failed to load peers router: %s", _e)


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

    return {
        "status":            "healthy" if db_ok else "degraded",
        "network":           settings.NETWORK,
        "chain_id":          settings.CHAIN_ID,
        "version":           settings.NODE_VERSION,
        "db_connected":      db_ok,
        "block_height":      height,
        "active_validators": validator_count,
    }
