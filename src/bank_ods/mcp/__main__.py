import os

from bank_ods.mcp.server import mcp

# MCP_TRANSPORT=stdio  (default) — used with Claude Desktop and local dev
# MCP_TRANSPORT=sse    — used when deployed as a chatbot backend on K8s
transport = os.getenv("MCP_TRANSPORT", "stdio")
mcp.run(transport=transport)
