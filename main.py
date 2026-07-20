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

    # 1. Initialise DB schema
    await init_db()
    logger.info("Database schema ready.")

    # 2. Seed genesis block (idempotent)
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

    # 3. Start consensus epoch scheduler as a background task
    from chain.consensus.scheduler import EpochScheduler
    scheduler = EpochScheduler()
    consensus_task = asyncio.create_task(scheduler.run(), name="consensus-scheduler")
    app.state.scheduler = scheduler
    app.state.consensus_task = consensus_task
    logger.info("Consensus scheduler started (epoch=%ds).", settings.EPOCH_SECONDS)

    logger.info("VIT Chain Node OPERATIONAL — RPC at POST /rpc")

    yield

    # Shutdown
    logger.info("Shutting down VIT Chain Node…")
    consensus_task.cancel()
    try:
        await consensus_task
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
from chain.rpc.router import router as rpc_router
from api.blocks import router as blocks_router
from api.transactions import router as txs_router
from api.accounts import router as accounts_router
from api.validators import router as validators_router
from api.status import router as status_router
from api.peers import router as peers_router

app.include_router(rpc_router)
app.include_router(blocks_router)
app.include_router(txs_router)
app.include_router(accounts_router)
app.include_router(validators_router)
app.include_router(status_router)
app.include_router(peers_router)


# ── Core endpoints ────────────────────────────────────────────────────────────
@app.get("/ping", tags=["Health"])
async def ping():
    return {"status": "ok", "chain_id": settings.CHAIN_ID, "network": settings.NETWORK}


@app.get("/health", tags=["Health"])
async def health():
    from sqlalchemy import text
    db_ok = False
    height = 0
    validator_count = 0
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
            db_ok = True
            from chain.core.chain import VITChain
            chain = VITChain()
            height = await chain.get_height(db)
            from chain.consensus.registry import ValidatorRegistry
            reg = ValidatorRegistry()
            validators = await reg.get_active_validators(db)
            validator_count = len(validators)
    except Exception as exc:
        logger.debug("Health check DB error: %s", exc)

    return {
        "status": "healthy" if db_ok else "degraded",
        "network": settings.NETWORK,
        "chain_id": settings.CHAIN_ID,
        "version": settings.NODE_VERSION,
        "db_connected": db_ok,
        "block_height": height,
        "active_validators": validator_count,
    }
