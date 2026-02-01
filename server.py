import os
import httpx
from fastmcp import FastMCP

mcp = FastMCP("MockAPI MCP")

MOCKAPI_BASE_URL = os.environ[https://697ea4fad1548030ab641c89.mockapi.io/weekly_digest_report]
MCP_API_KEY = os.environ.get(test_key_456)  # optional but recommended

@mcp.tool()
async def get_items():
    """Fetch items from MockAPI (GET collection endpoint)."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(MOCKAPI_BASE_URL)
        r.raise_for_status()
        return r.json()

app = mcp.http_app()

# Simple auth gate for all HTTP requests
if MCP_API_KEY:
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import JSONResponse

    class ApiKeyMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            if request.headers.get("x-api-key") != MCP_API_KEY:
                return JSONResponse({"error": "unauthorized"}, status_code=401)
            return await call_next(request)

    app.add_middleware(ApiKeyMiddleware)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))

