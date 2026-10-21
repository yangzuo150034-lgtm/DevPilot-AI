import asyncio
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def test_mcp_stdio_publishes_only_readonly_tools():
    async def scenario():
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "app.mcp_server"],
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        async with stdio_client(parameters) as (read, write):
            async with ClientSession(read, write) as client:
                await client.initialize()
                tools = await client.list_tools()
                assert {tool.name for tool in tools.tools} == {
                    "list_repositories",
                    "search_code",
                    "get_task_report",
                }

    asyncio.run(scenario())
