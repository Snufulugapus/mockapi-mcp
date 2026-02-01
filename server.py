import os
import json
import httpx

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route, Mount

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings


# ----------------------------
# Env
# ----------------------------
MOCKAPI_BASE_URL = os.environ.get("MOCKAPI_BASE_URL")
if not MOCKAPI_BASE_URL:
    raise RuntimeError("Missing required env var: MOCKAPI_BASE_URL")

# Set this in Railway to your public hostname (no scheme, no path), e.g.:
# RAILWAY_PUBLIC_DOMAIN = "my-service-production.up.railway.app"
RAILWAY_PUBLIC_DOMAIN = os.environ.get("RAILWAY_PUBLIC_DOMAIN")

# Optional (note: ChatGPT connector creation typically won't send this)
MCP_API_KEY = os.environ.get("MCP_API_KEY")


# ----------------------------
# MCP server with host allowlist (fixes "Invalid Host Header")
# ----------------------------
allowed_hosts = [
    "localhost:*",
    "127.0.0.1:*",
    "healthcheck.railway.app:*",
]
allowed_origins = []

if RAILWAY_PUBLIC_DOMAIN:
    allowed_hosts.append(f"{RAILWAY_PUBLIC_DOMAIN}:*")
    allowed_origins.append(f"https://{RAILWAY_PUBLIC_DOMAIN}")

mcp = FastMCP(
    "MockAPI MCP",
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=allowed_hosts,
        allowed_origins=allowed_origins,
    ),
)


# ----------------------------
# Tools (ChatGPT connectors commonly expect search + fetch)
# ----------------------------
@mcp.tool()
async def search(query: str):
    # Minimal implementation: one "document" representing your MockAPI collection.
    results = [
        {
            "id": "mockapi-items",
            "title": f"MockAPI items matching: {query}",
            "url": MOCKAPI_BASE_URL,
        }
    ]
    return {"content": [{"type": "text", "text": json.dumps({"results": results})}]}


@mcp.tool()
async def fetch(id: str):
    if id != "mockapi-items":
        doc = {
            "id": id,
            "title": "Unknown id",
            "text": f"No document found for id={id}",
            "url": MOCKAPI_BASE_URL,
            "metadata": {"error": "not_found"},
        }
        return {"content": [{"type": "text", "text": json.dumps(doc)}]}

    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(MOCKAPI_BASE_URL)
        r.raise_for_status()
        data = r.json()

    doc = {
        "id": id,
        "title": "MockAPI items",
        "text": json.dumps(data, indent=2),
        "url": MOCKAPI_BASE_URL,
        "metadata": {"source": "mockapi"},
    }
    return {"content": [{"type": "text", "text": json.dumps(doc)}]}


# Optional extra tool
@mcp.tool()
async def get_items():
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(MOCKAPI_BASE_URL)
        r.raise_for_status()
        return r.json()


# ----------------------------
# ASGI app: mount MCP SSE transport + add browser/health routes
# ----------------------------
mcp_sse_app = mcp.sse_app()  # provides /sse (text/event-stream) and /messages/*


async def root(_request):
    return JSONResponse(
        {
            "ok": True,
            "mcp_sse": "/sse",
            "note": "Use https://<your-domain>/sse in ChatGPT Create App.",
            "railway_public_domain_env": bool(RAILWAY_PUBLIC_DOMAIN),
        }
    )


async def health(_request):
    return JSONResponse({"status": "ok"})


app = Starlette(
    routes=[
        Route("/", root, methods=["GET"]),
        Route("/health", health, methods=["GET"]),
        Mount("/", app=mcp_sse_app),
    ]
)


# ----------------------------
# Optional API key (do NOT block /, /health, /sse, /messages during connector creation)
# ----------------------------
if MCP_API_KEY:
    from starlette.middleware.base import BaseHTTPMiddleware

    class ApiKeyMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            # allow unauthenticated for health + connector bootstrapping paths
            if request.url.path in ("/", "/health") or request.url.path.startswith(
                ("/sse", "/messages")
            ):
                return await call_next(request)

            if request.headers.get("x-api-key") != MCP_API_KEY:
                return JSONResponse({"error": "unauthorized"}, status_code=401)

            return await call_next(request)

    app.add_middleware(ApiKeyMiddleware)


# ----------------------------
# Local run
# ----------------------------
if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
