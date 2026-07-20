"""
api/registry.py — VIT Service Registry endpoint.

Returns all known VIT Network service URLs from configuration.
Priority: environment variables → defaults from render.yaml.

Other services can GET /api/registry on startup to discover endpoints
without hardcoding URLs. Environment variables always override the registry.
"""
from fastapi import APIRouter
from chain.config import settings

router = APIRouter(prefix="/api", tags=["Registry"])


@router.get("/registry")
async def service_registry():
    """
    Returns all live VIT Network service endpoints.
    
    Configuration priority per service:
    1. Environment variable (e.g. VIT_STORAGE_URL)
    2. This registry response
    3. Local service defaults
    """
    return {
        "schema_version": "1.0",
        "network": settings.NETWORK,
        "chain_id": settings.CHAIN_ID,
        "services": {
            "vit_chain": {
                "url": "https://vit-chain.onrender.com",
                "health": "https://vit-chain.onrender.com/health",
                "ping":   "https://vit-chain.onrender.com/ping",
                "rpc":    "https://vit-chain.onrender.com/rpc",
                "env_var": "VIT_CHAIN_URL",
                "status": "primary",
            },
            "vit_storage": {
                "url": settings.VIT_STORAGE_URL or "https://vit-storage-4trt.onrender.com",
                "health": f"{settings.VIT_STORAGE_URL or 'https://vit-storage-4trt.onrender.com'}/health",
                "env_var": "VIT_STORAGE_URL",
                "status": "primary",
            },
            "vit_ai": {
                "url": settings.VIT_AI_URL or "https://vit-ai.onrender.com",
                "health": f"{settings.VIT_AI_URL or 'https://vit-ai.onrender.com'}/health",
                "env_var": "VIT_AI_URL",
                "status": "primary",
            },
            "vitnetwork": {
                "url": "https://vitnetwork-nls4.onrender.com",
                "health": "https://vitnetwork-nls4.onrender.com/health",
                "env_var": "VIT_NETWORK_URL",
                "status": "primary",
            },
        },
        "env_override_instructions": (
            "Set VIT_CHAIN_URL / VIT_STORAGE_URL / VIT_AI_URL / VIT_NETWORK_URL "
            "as environment variables to override this registry."
        ),
    }
