from contextlib import asynccontextmanager

from fastmcp import FastMCP

from bank_ods.db.indexes import ensure_indexes

mcp = FastMCP("bank-ods")

# Import tools module so all @mcp.tool() decorators run
from bank_ods.mcp import tools  # noqa: E402, F401


@asynccontextmanager
async def lifespan(_):
    await ensure_indexes()
    yield


if __name__ == "__main__":
    mcp.run()
