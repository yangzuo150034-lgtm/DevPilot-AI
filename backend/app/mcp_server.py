"""Read-only MCP stdio adapter for a running DevPilot API. No tool executes code."""

import os

import httpx
from mcp.server.mcpserver import MCPServer

server = MCPServer("DevPilot AI", instructions="Read-only repository search and execution reports.")


def api(path: str):
    from app.core.config import Settings

    settings = Settings()
    token = settings.api_token.get_secret_value()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    with httpx.Client(
        base_url=os.getenv("DEVPILOT_MCP_API_URL", "http://127.0.0.1:8000"),
        headers=headers,
        timeout=60,
    ) as client:
        response = client.get("/api/v1" + path)
        if response.status_code != 200:
            raise ValueError(f"DevPilot API returned HTTP {response.status_code}")
        return response.json()


@server.tool()
def list_repositories() -> list[dict]:
    """List imported immutable repository snapshots."""
    return api("/repositories")


@server.tool()
def search_code(repository_id: str, query: str) -> list[dict]:
    """Retrieve code evidence with paths, line ranges and commit identifiers."""
    from urllib.parse import quote

    if not repository_id.isalnum() or len(repository_id) != 32:
        raise ValueError("Invalid repository ID")
    return api(f"/repositories/{repository_id}/search?q={quote(query[:1000], safe='')}&mode=hybrid")


@server.tool()
def get_task_report(task_id: str) -> dict:
    """Read task state, citations, patch review and actual test results."""
    if not task_id.isalnum() or len(task_id) != 32:
        raise ValueError("Invalid task ID")
    return api(f"/tasks/{task_id}")


if __name__ == "__main__":
    server.run(transport="stdio")
