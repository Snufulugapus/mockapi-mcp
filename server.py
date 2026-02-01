import os
import httpx
from fastmcp import FastMCP

# --- Config ---
MOCKAPI_BASE_URL = os.environ.get("MOCKAPI_BASE_URL")
MCP_API_KEY = os.environ.get("MCP_API_KEY")  # optional

if not MOCKAPI_BASE_URL:
    raise RuntimeError("Missing required env var: MOCKAPI_BASE_URL")

# --- MCP server ---
mcp = FastMCP("MockAPI MCP")


@mcp.tool()
async def get_items():
    """Fetch items from MockAPI (GET collection endpoint)."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(MOCKAPI_BASE_URL)
        r.raise_for_status()
        return r.json()


# This mounts the MCP HTTP endpoint at /mcp (as you already observed)
app = mcp.http_app()

# --- Add normal HTTP endpoints for browser + Railway health checks ---
from starlette.responses import JSONResponse
from starlette.routing import Route


async def root(_request):
    return JSONResponse(
        {
            "ok": True,
            "service": "MockAPI MCP",
            "mcp_endpoint": "/mcp",
            "note": "Use an MCP client (SSE) for /mcp; browsers will not work.",
        }
    )


async def health(_request):
    return JSONResponse({"status": "ok"})


# Ensure these exist even though FastMCP only gives /mcp by default
app.routes.append(Route("/", root, methods=["GET"]))
app.routes.append(Route("/health", health, methods=["GET"]))


# --- Optional API key auth ---
# Important: do NOT require x-api-key for / and /health (so Railway can check health)
if MCP_API_KEY:
    from starlette.middleware.base import BaseHTTPMiddleware

    class ApiKeyMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            if request.url.path in ("/", "/health"):
                return await call_next(request)

            if request.headers.get("x-api-key") != MCP_API_KEY:
                return JSONResponse({"error": "unauthorized"}, status_code=401)

            return await call_next(request)

    app.add_middleware(ApiKeyMiddleware)


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)

