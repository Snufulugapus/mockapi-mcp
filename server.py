import os
import json
import httpx

from fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route, Mount

MOCKAPI_BASE_URL = os.environ.get("MOCKAPI_BASE_URL")
if not MOCKAPI_BASE_URL:
    raise RuntimeError("Missing required env var: MOCKAPI_BASE_URL")

mcp = FastMCP("MockAPI MCP")


# --- REQUIRED for ChatGPT connectors: search + fetch ---
@mcp.tool()
async def search(query: str):
    """
    Return search results.
    OpenAI expects one content item with type 'text' containing JSON string:
    {"results":[{"id","title","url"}]}
    """
    # Minimal: one synthetic "collection" result, plus you can add smarter matching later.
    results = [
        {
            "id": "mockapi-items",
            "title": f"MockAPI items matching: {query}",
            "url": MOCKAPI_BASE_URL,
        }
    ]
    return {
        "content": [
            {"type": "text", "text": json.dumps({"results": results})}
        ]
    }


@mcp.tool()
async def fetch(id: str):
    """
    Return full contents for a search result.
    OpenAI expects one content item with type 'text' containing JSON string:
    {"id","title","text","url","metadata"(optional)}
    """
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


# Optional extra tool (fine to keep)
@mcp.tool()
async def get_items():
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(MOCKAPI_BASE_URL)
        r.raise_for_status()
        return r.json()


# --- SSE transport app (this is what ChatGPT is expecting) ---
mcp_sse_app = mcp.sse_app()

# Add normal HTTP routes for browser + Railway health
async def root(_request):
    return JSONResponse(
        {
            "ok": True,
            "mcp_sse": "/sse",
            "note": "Use the /sse URL in ChatGPT Create App (Developer Mode).",
        }
    )

async def health(_request):
    return JSONResponse({"status": "ok"})

app = Starlette(
    routes=[
        Route("/", root, methods=["GET"]),
        Route("/health", health, methods=["GET"]),
        Mount("/", app=mcp_sse_app),  # provides /sse and /messages/...
    ],
)
