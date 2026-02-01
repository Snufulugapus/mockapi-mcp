import os
import json
import httpx

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route, Mount

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings


MOCKAPI_BASE_URL = os.environ.get("MOCKAPI_BASE_URL")
if not MOCKAPI_BASE_URL:
    raise RuntimeError("Missing required env var: MOCKAPI_BASE_URL")

# IMPORTANT: disable host header protection on Railway to avoid 421 Invalid Host Header
# (You can re-enable later with an accurate allowed_hosts list.)
mcp = FastMCP(
    "MockAPI MCP",
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=False
    ),
)

# ---- Tools (ChatGPT connector flow typically needs search + fetch) ----
@mcp.tool()
async def search(query: str):
    results = [
        {"id": "mockapi-items", "title": f"MockAPI items matching: {query}", "url": MOCKAPI_BASE_URL}
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

# ---- Mount SSE transport (this is what ChatGPT expects) ----
mcp_sse_app = mcp.sse_app()  # provides /sse and /messages/*

async def root(_request):
    return JSONResponse(
        {"ok": True, "mcp_sse": "/sse", "note": "Paste https://<domain>/sse into ChatGPT Create App."}
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

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
