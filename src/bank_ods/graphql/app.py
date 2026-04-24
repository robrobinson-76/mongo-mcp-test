from contextlib import asynccontextmanager

from ariadne import ScalarType, make_executable_schema
from ariadne.asgi import GraphQL
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from bank_ods.db.indexes import ensure_indexes
from bank_ods.graphql.sdl import generate_sdl
from bank_ods.graphql.resolvers import query

datetime_scalar = ScalarType("DateTime")


@datetime_scalar.serializer
def serialize_datetime(value):
    return value if isinstance(value, str) else str(value)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await ensure_indexes()
    yield


def _build_graphql_app() -> GraphQL:
    type_defs = generate_sdl()
    schema = make_executable_schema(type_defs, query, datetime_scalar)
    return GraphQL(schema, debug=True)


def create_app() -> FastAPI:
    fast = FastAPI(title="Bank ODS GraphQL API", version="0.2.0", lifespan=lifespan)
    graphql_app = _build_graphql_app()
    fast.mount("/graphql", graphql_app)

    @fast.get("/")
    async def root():
        return {"message": "GraphQL available at /graphql"}

    return fast


app = create_app()
