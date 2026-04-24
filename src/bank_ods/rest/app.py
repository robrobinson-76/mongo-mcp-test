from contextlib import asynccontextmanager

from fastapi import FastAPI

from bank_ods.db.indexes import ensure_indexes
from bank_ods.rest.routers import accounts, transactions, positions, settlements, balances


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await ensure_indexes()
    yield


app = FastAPI(title="Bank ODS REST API", version="0.2.0", lifespan=lifespan)

app.include_router(accounts.router, prefix="/accounts", tags=["accounts"])
app.include_router(transactions.router, prefix="/transactions", tags=["transactions"])
app.include_router(positions.router, prefix="/positions", tags=["positions"])
app.include_router(settlements.router, prefix="/settlements", tags=["settlements"])
app.include_router(balances.router, prefix="/balances", tags=["balances"])
