
import httpx
from mcp.server.fastmcp import FastMCP
from code_scanner.config import ServiceConfig

mcp = FastMCP("Code Scanner")
SERVICE_URL = f"http://{ServiceConfig.host}:{ServiceConfig.port}"

@mcp.resource("code-scanner://issues")
async def get_issues() -> str:
    """Get list of current issues found by Code Scanner."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{SERVICE_URL}/issues", timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                return str(data.get("issues", []))
            return f"Error fetching issues: {response.status_code}"
    except httpx.ConnectError:
        return "Error: Code Scanner service is not reachable."
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
async def code_scanner_status() -> str:
    """Get the status of the Code Scanner service."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{SERVICE_URL}/status", timeout=5.0)
            if response.status_code == 200:
                return str(response.json())
            return f"Error fetching status: {response.status_code}"
    except httpx.ConnectError:
        return "Error: Code Scanner service is not reachable."

async def run_mcp_server():
    """Run the MCP server on stdio."""
    await mcp.run_stdio_async()
