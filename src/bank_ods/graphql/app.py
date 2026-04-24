from contextlib import asynccontextmanager

from ariadne import ScalarType, make_executable_schema
from ariadne.asgi import GraphQL
from fastapi import FastAPI

from bank_ods.config import DEBUG, LOG_LEVEL
from bank_ods.db.indexes import ensure_indexes
from bank_ods.graphql.sdl import generate_sdl
from bank_ods.graphql.resolvers import query
from bank_ods.logging_config import RequestLoggingMiddleware, configure_logging

datetime_scalar = ScalarType("DateTime")


@datetime_scalar.serializer
def serialize_datetime(value):
    return value if isinstance(value, str) else str(value)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    configure_logging(LOG_LEVEL)
    await ensure_indexes()
    yield


def _build_graphql_app() -> GraphQL:
    type_defs = generate_sdl()
    schema = make_executable_schema(type_defs, query, datetime_scalar)
    return GraphQL(schema, debug=DEBUG)


def create_app() -> FastAPI:
    fast = FastAPI(title="Bank ODS GraphQL API", version="0.2.0", lifespan=lifespan)
    fast.add_middleware(RequestLoggingMiddleware)

    graphql_app = _build_graphql_app()
    fast.mount("/graphql", graphql_app)

    @fast.get("/health", tags=["ops"])
    async def health():
        return {"status": "ok"}

    @fast.get("/")
    async def root():
        return {"message": "GraphQL available at /graphql"}

    return fast


app = create_app()
