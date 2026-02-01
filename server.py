import os
import json
import httpx

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route, Mount

from mcp.server.fastmcp import FastMCP  # <-- official MCP SDK


MOCKAPI_BASE_URL = os.environ.get("MOCKAPI_BASE_URL")
if not MOCKAPI_BASE_URL:
    raise RuntimeError("Missing required env var: MOCKAPI_BASE_URL")

MCP_API_KEY = os.environ.get("MCP_API_KEY")  # optional


mcp = FastMCP("MockAPI MCP")


# --- Tools (OpenAI connectors commonly expect search + fetch) ---
@mcp.tool()
async def search(query: str):
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


# --- ASGI apps ---
mcp_sse_app = mcp.sse_app()  # provides /sse and /messages


async def root(_request):
    return JSONResponse(
        {
            "ok": True,
            "mcp_sse": "/sse",
            "note": "Use the /sse URL in ChatGPT Create App.",
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


# --- Optional API key middleware (do NOT block / and /health) ---
if MCP_API_KEY:
    from starlette.middleware.base import BaseHTTPMiddleware

    class ApiKeyMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            if request.url.path in ("/", "/health", "/sse"):
                return await call_next(request)
            if request.headers.get("x-api-key") != MCP_API_KEY:
                return JSONResponse({"error": "unauthorized"}, status_code=401)
            return await call_next(request)

    app.add_middleware(ApiKeyMiddleware)


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
